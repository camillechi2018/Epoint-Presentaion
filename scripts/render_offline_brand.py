"""Build an editable, brand-consistent PPTX without the Git knowledge base.

Input is a model-authored page plan; business facts must come from the user's material.
This renderer intentionally does not claim to reproduce any source template.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from io import BytesIO
import json
import math
import re
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt
from audit_new_drawn_palette import audit as audit_palette
from audit_brand_palette_source import locked_colors
from audit_component_color_independence import audit as audit_color_independence
from audit_logo import audit as audit_logo
from materialize_component_colors import freeze_uniform_deck
from normalize_fonts import normalize
from fallback_rules import fallback_type, fallback_catalog
from free_composition import render_free_page


SKILL = Path(__file__).resolve().parents[1]
PROFILE = SKILL / "assets" / "brand" / "brand-baseline.json"
LOGO_CONFIG = SKILL / "assets" / "brand" / "logo-config.json"
LAYOUT_SPEC = SKILL / "assets" / "layouts" / "offline-core.json"
COMPOSITION_RULES = SKILL / "assets" / "style-kits" / "composition-rules.json"
VALID_TYPES = {"cover", "section", "bullets", "cards", "process", "comparison", "metrics",
               "assertion_evidence", "priority_grid", "evidence_matrix", "problem_solution_outcome",
               "layered_architecture", "longform_metric", "data_table", "milestone_timeline",
               "image_case", "comparison_chart", "target_actual_gap", "decision_matrix",
               "responsibility_swimlane", "free_composition", "closing"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rgb(value: str) -> RGBColor:
    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError(f"颜色值无效：{value}")
    return RGBColor.from_string(value.upper())


def color(shape, value: str, line: str | None = None):
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(value)
    if line:
        shape.line.color.rgb = rgb(line)
    else:
        shape.line.fill.background()


def text_box(slide, value: str, x: float, y: float, w: float, h: float,
             size: float, ink: str, font: str, *, bold=False, align=PP_ALIGN.LEFT,
             valign=MSO_ANCHOR.MIDDLE, margin=0.0):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    for i, line in enumerate(str(value).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        p.space_before = p.space_after = Pt(0)
        p.line_spacing = 1.14
        p.font.name = font
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = rgb(ink)
    return box


def rectangle(slide, x: float, y: float, w: float, h: float, fill: str,
              border: str | None = None, rounded=False):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    color(shape, fill, border)
    if rounded:
        try:
            shape.adjustments[0] = 0.12
        except (IndexError, ValueError):
            pass
    return shape


def connector(slide, x1, y1, x2, y2, ink, width=1.0):
    shape = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
        Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    shape.line.color.rgb = rgb(ink)
    shape.line.width = Pt(width)
    return shape


def remove_shadow_effects(slide):
    """Prevent PowerPoint theme effect styles from adding implicit shadows."""
    for shape in slide.shapes:
        element = shape._element
        # python-pptx assigns effectRef idx=2 to new shapes. This theme slot
        # contains an outer shadow even when no shadow was requested in code.
        for effect_ref in element.xpath(".//a:effectRef"):
            effect_ref.set("idx", "0")
        for shadow in element.xpath(".//a:outerShdw | .//a:innerShdw | .//a:prstShdw"):
            shadow.getparent().remove(shadow)


def display_units(value: str) -> int:
    return sum(2 if ord(ch) > 255 else 1 for ch in value)


def resolved_variant(page: dict, kind: str) -> str:
    """Keep density and relation variants inside their existing layout IDs."""
    variant = page.get("variant", "auto")
    rules = read_json(COMPOSITION_RULES)["body_variants"]
    if kind == "bullets":
        allowed = set(rules["bullets"]["allowed"])
        if variant not in allowed:
            raise ValueError(f"bullets variant 不支持：{variant}")
        if variant != "auto":
            return variant
        if "featured_index" in page:
            return "lead"
        items = page.get("items", [])
        if len(items) >= rules["bullets"]["compact_min_items"] or any(
                display_units(str(x if isinstance(x, str) else x.get("text") or x.get("title") or ""))
                > rules["bullets"]["compact_long_item_units"] for x in items):
            return "compact"
        if len(items) <= rules["bullets"]["spacious_max_items"]:
            return "spacious"
        return "balanced"
    if kind == "metrics":
        allowed = set(rules["metrics"]["allowed"])
        if variant not in allowed:
            raise ValueError(f"metrics variant 不支持：{variant}")
        if variant != "auto":
            return variant
        if len(page.get("items", [])) == 1:
            return "hero"
        return "lead_support" if "featured_index" in page else "grid"
    if kind == "cards":
        allowed = {"auto", "grid", "columns", "stat_rows"}
        if variant not in allowed:
            raise ValueError(f"cards variant 不支持：{variant}")
        if variant != "auto":
            return variant
        return "columns" if len(page.get("items", [])) in (2, 3) else "grid"
    if kind == "process":
        allowed = {"auto", "cards", "rail"}
        if variant not in allowed:
            raise ValueError(f"process variant 不支持：{variant}")
        if variant != "auto":
            return variant
        items = page.get("items", [])
        short = all(display_units(str(item.get("body", ""))) <= 22 for item in items)
        return "rail" if 3 <= len(items) <= 5 and short else "cards"
    if kind == "priority_grid":
        allowed = {"auto", "side", "top"}
        if variant not in allowed:
            raise ValueError(f"priority_grid variant 不支持：{variant}")
        if variant != "auto":
            return variant
        support = page.get("support", [])
        return "top" if len(support) == 4 and all(
            display_units(str(item.get("body", ""))) <= 30 for item in support) else "side"
    if kind == "milestone_timeline":
        allowed = {"auto", "horizontal", "vertical"}
        if variant not in allowed:
            raise ValueError(f"milestone_timeline variant 不支持：{variant}")
        if variant != "auto":
            return variant
        return "vertical" if len(page.get("milestones", [])) >= 5 else "horizontal"
    if kind in {"comparison", "data_table", "image_case"}:
        selected = page.get("variant", "standard")
        if selected not in set(rules[kind]["allowed"]):
            raise ValueError(f"{kind} variant 不支持：{selected}")
        return selected
    return ""


def validate_fallback(page: dict, kind: str, n: int):
    rules = fallback_catalog()
    if kind not in rules:
        raise ValueError(f"第 {n} 页托底版式未登记：{kind}")
    cap = rules[kind]["capacity"]
    if display_units(page["title"]) > cap["title_units_max"]:
        raise ValueError(f"第 {n} 页结论过长，请拆页或改用短标题")
    if kind == "assertion_evidence":
        data = page.get("series")
        if not isinstance(data, list) or not cap["series_min"] <= len(data) <= cap["series_max"]:
            raise ValueError(f"第 {n} 页需要 {cap['series_min']}–{cap['series_max']} 个真实连续数值")
        if not str(page.get("data_source", "")).strip():
            raise ValueError(f"第 {n} 页趋势证据缺少 data_source")
        for item in data:
            if (not isinstance(item, dict) or not str(item.get("label", "")).strip()
                or type(item.get("value")) not in (int, float)
                or not math.isfinite(item["value"]) or not 0 <= item["value"] <= 99999
                or display_units(str(item["label"])) > 12):
                raise ValueError(f"第 {n} 页趋势证据需要非负数值与简短时期标签")
        if display_units(str(page.get("unit", ""))) > 12:
            raise ValueError(f"第 {n} 页单位过长")
        if display_units(str(page.get("summary", ""))) > 70:
            raise ValueError(f"第 {n} 页趋势摘要超出安全容量")
        if display_units(str(page["data_source"])) > 95:
            raise ValueError(f"第 {n} 页数据来源超出单行安全容量")
    elif kind == "priority_grid":
        lead, support = page.get("lead"), page.get("support")
        if not isinstance(lead, dict) or not isinstance(support, list) or not cap["support_min"] <= len(support) <= cap["support_max"]:
            raise ValueError(f"第 {n} 页需要一个主信息和 {cap['support_min']}–{cap['support_max']} 个辅助信息")
        if (display_units(str(lead.get("title", ""))) > 20
            or not str(lead.get("title", "")).strip()
            or not str(lead.get("body", "")).strip()
            or display_units(str(lead.get("body", ""))) > 75):
            raise ValueError(f"第 {n} 页主信息超出容量或缺少标题")
        for item in support:
            if (not isinstance(item, dict) or not str(item.get("title", "")).strip()
                or not str(item.get("body", "")).strip()
                or display_units(str(item["title"])) > 18
                or display_units(str(item.get("body", ""))) > (30 if len(support) == 3 else 65)):
                raise ValueError(f"第 {n} 页辅助信息超出容量或缺少标题")
        if resolved_variant(page, kind) == "top" and any(
                display_units(str(item.get("body", ""))) > 30 for item in support):
            raise ValueError(f"第 {n} 页顶部主次配方的支撑正文过长，请改用 side")
    elif kind == "evidence_matrix":
        sections = page.get("sections")
        if not isinstance(sections, list) or not cap["sections_min"] <= len(sections) <= cap["sections_max"]:
            raise ValueError(f"第 {n} 页需要 {cap['sections_min']}–{cap['sections_max']} 个证据区")
        for i, item in enumerate(sections):
            body_cap = 105 if i == 0 else (34 if len(sections) == 4 else 65)
            if (not isinstance(item, dict) or not str(item.get("title", "")).strip()
                or not str(item.get("body", "")).strip()
                or display_units(str(item["title"])) > 20
                or display_units(str(item.get("body", ""))) > body_cap):
                raise ValueError(f"第 {n} 页证据区超出容量或缺少标题")
    elif kind == "problem_solution_outcome":
        for key in ("problem", "solution", "outcome"):
            item = page.get(key)
            if (not isinstance(item, dict) or not str(item.get("title", "")).strip()
                or not str(item.get("body", "")).strip()
                or display_units(str(item["title"])) > 18
                or display_units(str(item["body"])) > cap["stage_body_units_max"]):
                raise ValueError(f"第 {n} 页 {key} 需要简短标题和正文；超长内容请拆页")
    elif kind == "layered_architecture":
        layers = page.get("layers")
        if not isinstance(layers, list) or not cap["layers_min"] <= len(layers) <= cap["layers_max"]:
            raise ValueError(f"第 {n} 页层级数量须为 {cap['layers_min']}–{cap['layers_max']}")
        for layer in layers:
            if (not isinstance(layer, dict) or not str(layer.get("title", "")).strip()
                or display_units(str(layer["title"])) > 16
                or not isinstance(layer.get("items"), list)
                or not 1 <= len(layer["items"]) <= cap["items_per_layer_max"]
                or any(not isinstance(item, str) or not item.strip() or display_units(item) > 20
                       for item in layer["items"])):
                raise ValueError(f"第 {n} 页每层需要简短名称和 1–4 个同级对象")
    elif kind == "longform_metric":
        paragraphs, metric = page.get("paragraphs"), page.get("metric")
        if (not isinstance(paragraphs, list)
            or not cap["paragraphs_min"] <= len(paragraphs) <= cap["paragraphs_max"]
            or any(not isinstance(p, str) or not p.strip()
                   or display_units(p) > cap["paragraph_units_max"] for p in paragraphs)):
            raise ValueError(f"第 {n} 页长文需要 2–3 段真实内容，各段不超过容量")
        if (not isinstance(metric, dict) or not str(metric.get("value", "")).strip()
            or not str(metric.get("label", "")).strip()
            or not str(metric.get("source", "")).strip()
            or display_units(str(metric["value"])) > 12
            or display_units(str(metric["label"])) > 26
            or display_units(str(metric["source"])) > 85):
            raise ValueError(f"第 {n} 页关键数字需要数值、说明和来源")
    elif kind == "data_table":
        if page.get("variant") not in (None, "standard", "action_tracker"):
            raise ValueError(f"第 {n} 页表格变体不受支持")
        if page.get("variant") == "action_tracker":
            actions = page.get("actions")
            if not isinstance(actions, list) or not 2 <= len(actions) <= 6:
                raise ValueError(f"第 {n} 页行动跟踪需要 2–6 条记录")
            for item in actions:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(key), str) or not item[key].strip() or display_units(item[key]) > limit
                    for key, limit in (("issue", 26), ("action", 38), ("owner", 16), ("due", 18), ("status", 12))
                ):
                    raise ValueError(f"第 {n} 页行动记录缺少问题、措施、负责人、期限或状态，或文字过长")
            return
        columns, rows = page.get("columns"), page.get("rows")
        if not isinstance(columns, list) or not cap["columns_min"] <= len(columns) <= cap["columns_max"]:
            raise ValueError(f"第 {n} 页表格列数须为 2–6")
        if not isinstance(rows, list) or not cap["rows_min"] <= len(rows) <= cap["rows_max"]:
            raise ValueError(f"第 {n} 页表格行数须为 1–8")
        if any(not isinstance(c, str) or not c.strip() or display_units(c) > cap["cell_units_max"] for c in columns):
            raise ValueError(f"第 {n} 页表头必须为简短文字")
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns) or any(
                    not isinstance(cell, (str, int, float)) or display_units(str(cell)) > cap["cell_units_max"]
                    for cell in row):
                raise ValueError(f"第 {n} 页表格行须与表头列数一致且单元格内容简短")
        if display_units(str(page.get("data_source", ""))) > 85:
            raise ValueError(f"第 {n} 页表格数据来源过长")
    elif kind == "milestone_timeline":
        items = page.get("milestones")
        if not isinstance(items, list) or not cap["milestones_min"] <= len(items) <= cap["milestones_max"]:
            raise ValueError(f"第 {n} 页里程碑需 3–6 项")
        for item in items:
            if (not isinstance(item, dict) or not str(item.get("date", "")).strip()
                or not str(item.get("title", "")).strip()
                or display_units(str(item["date"])) > cap["date_units_max"]
                or display_units(str(item["title"])) > cap["item_title_units_max"]
                or display_units(str(item.get("body", ""))) > cap["body_units_max"]):
                raise ValueError(f"第 {n} 页里程碑缺少日期/标题或内容过长")
        resolved_variant(page, kind)
    elif kind == "image_case":
        if page.get("variant") not in (None, "standard", "annotated"):
            raise ValueError(f"第 {n} 页图文案例变体不受支持")
        image = Path(str(page.get("image_path", "")))
        if (not image.is_absolute() or not image.is_file()
            or image.suffix.lower() not in {".png", ".jpg", ".jpeg"}
            or image.stat().st_size > 20_000_000):
            raise ValueError(f"第 {n} 页案例图片须为存在的本地 PNG/JPG 文件且不超过 20 MB")
        try:
            with Image.open(image) as probe:
                probe.verify()
        except OSError as exc:
            raise ValueError(f"第 {n} 页案例图片无法读取：{image}") from exc
        annotated = page.get("variant") == "annotated"
        for key, limit in (("case_title", cap["case_title_units_max"]),
                           ("takeaway", cap["takeaway_units_max"])) + (() if annotated else (("body", cap["body_units_max"]),)):
            if not str(page.get(key, "")).strip() or display_units(str(page[key])) > limit:
                raise ValueError(f"第 {n} 页案例 {key} 缺失或过长")
        if annotated:
            marks = page.get("annotations")
            if not isinstance(marks, list) or not 1 <= len(marks) <= 3:
                raise ValueError(f"第 {n} 页截图标注需要 1–3 个来源明确的点")
            for mark in marks:
                if (not isinstance(mark, dict) or not str(mark.get("label", "")).strip()
                    or display_units(str(mark["label"])) > 44
                    or any(type(mark.get(key)) not in (int, float) or not math.isfinite(mark[key])
                           or not 0.05 <= mark[key] <= 0.95 for key in ("x", "y"))):
                    raise ValueError(f"第 {n} 页截图标注需提供简短说明与 0–1 范围内的真实位置")
        if display_units(str(page.get("image_caption", ""))) > cap["caption_units_max"]:
            raise ValueError(f"第 {n} 页图片说明过长")
    elif kind == "comparison_chart":
        categories, series = page.get("categories"), page.get("series")
        if not isinstance(categories, list) or not cap["categories_min"] <= len(categories) <= cap["categories_max"]:
            raise ValueError(f"第 {n} 页对比图需要 2–5 个类别")
        if not isinstance(series, list) or not cap["series_min"] <= len(series) <= cap["series_max"]:
            raise ValueError(f"第 {n} 页对比图需要 1–2 组数据")
        if not str(page.get("data_source", "")).strip() or display_units(str(page["data_source"])) > 85:
            raise ValueError(f"第 {n} 页对比图需要简短的数据来源")
        if any(not isinstance(c, str) or not c.strip() or display_units(c) > cap["label_units_max"] for c in categories):
            raise ValueError(f"第 {n} 页对比图类别名称过长")
        for group in series:
            values = group.get("values") if isinstance(group, dict) else None
            if (not isinstance(group, dict) or not str(group.get("name", "")).strip()
                or display_units(str(group["name"])) > 16
                or not isinstance(values, list) or len(values) != len(categories)
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 99999 for v in values)):
                raise ValueError(f"第 {n} 页对比图系列名称或数值无效")
        if display_units(str(page.get("unit", ""))) > 12:
            raise ValueError(f"第 {n} 页对比图单位过长")
    elif kind == "target_actual_gap":
        if any(type(page.get(key)) not in (int, float) or not math.isfinite(page[key])
               or not 0 <= page[key] <= 999_999_999 for key in ("target", "actual")):
            raise ValueError(f"第 {n} 页目标和实际必须是同口径非负数值")
        for key, limit in (("unit", cap["unit_units_max"]), ("period", cap["period_units_max"]),
                           ("gap_reason", cap["reason_units_max"]), ("data_source", cap["source_units_max"])):
            if not str(page.get(key, "")).strip() or display_units(str(page[key])) > limit:
                raise ValueError(f"第 {n} 页 {key} 缺失或超过容量")
    elif kind == "decision_matrix":
        criteria, options = page.get("criteria"), page.get("options")
        if not isinstance(criteria, list) or not cap["criteria_min"] <= len(criteria) <= cap["criteria_max"]:
            raise ValueError(f"第 {n} 页需要 2–4 项评价标准")
        if not isinstance(options, list) or not cap["options_min"] <= len(options) <= cap["options_max"]:
            raise ValueError(f"第 {n} 页需要 2–4 个备选方案")
        if any(not isinstance(x, str) or not x.strip() or display_units(x) > cap["label_units_max"] for x in criteria):
            raise ValueError(f"第 {n} 页评价标准名称无效")
        for item in options:
            if (not isinstance(item, dict) or not str(item.get("name", "")).strip()
                or display_units(str(item["name"])) > cap["label_units_max"]
                or not isinstance(item.get("scores"), list) or len(item["scores"]) != len(criteria)
                or any(type(score) is not int or not 1 <= score <= 5 for score in item["scores"])):
                raise ValueError(f"第 {n} 页各方案必须按同一标准提供 1–5 的整数评分")
        if not str(page.get("data_source", "")).strip() or display_units(str(page["data_source"])) > cap["source_units_max"]:
            raise ValueError(f"第 {n} 页决策矩阵缺少评分来源")
        recommended = page.get("recommended_index")
        if recommended is not None and (type(recommended) is not int or not 0 <= recommended < len(options)
                                       or not str(page.get("decision_reason", "")).strip()
                                       or display_units(str(page["decision_reason"])) > 90):
            raise ValueError(f"第 {n} 页建议方案须有有效序号及材料中的理由")
    elif kind == "responsibility_swimlane":
        phases, lanes = page.get("phases"), page.get("lanes")
        if not isinstance(phases, list) or not cap["phases_min"] <= len(phases) <= cap["phases_max"]:
            raise ValueError(f"第 {n} 页需要 2–5 个有序阶段")
        if not isinstance(lanes, list) or not cap["lanes_min"] <= len(lanes) <= cap["lanes_max"]:
            raise ValueError(f"第 {n} 页需要 2–4 个角色泳道")
        if any(not isinstance(x, str) or not x.strip() or display_units(x) > cap["label_units_max"] for x in phases):
            raise ValueError(f"第 {n} 页阶段名称无效")
        for lane in lanes:
            tasks = lane.get("tasks") if isinstance(lane, dict) else None
            if (not isinstance(lane, dict) or not str(lane.get("role", "")).strip()
                or display_units(str(lane["role"])) > cap["label_units_max"]
                or not isinstance(tasks, list) or len(tasks) != len(phases)
                or not any(str(task).strip() for task in tasks)
                or any(not isinstance(task, str) or display_units(task) > cap["task_units_max"] for task in tasks)):
                raise ValueError(f"第 {n} 页每个角色须按阶段提供真实任务或留空")
        if any(not any(lane["tasks"][i].strip() for lane in lanes) for i in range(len(phases))):
            raise ValueError(f"第 {n} 页不能有完全空白的阶段")


def validate_page(page: dict, n: int):
    if not isinstance(page, dict):
        raise ValueError(f"第 {n} 页必须是对象")
    kind = fallback_type(page)
    if kind not in VALID_TYPES:
        raise ValueError(f"第 {n} 页类型不支持：{kind}")
    title = page.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"第 {n} 页缺少 title")
    limit = 38 if kind in {"cover", "closing"} else (42 if kind in fallback_catalog() else 32)
    if display_units(title) > limit:
        raise ValueError(f"第 {n} 页标题超出离线安全容量（{limit} 宽度单位），请拆行或重拟页面结构")
    if kind == "cover":
        for field, cap in (("subtitle", 80), ("meta", 70)):
            if display_units(str(page.get(field, ""))) > cap:
                raise ValueError(f"第 {n} 页 {field} 超出离线安全容量")
    if kind == "closing":
        for field, cap in (("subtitle", 80), ("contact", 70)):
            if display_units(str(page.get(field, ""))) > cap:
                raise ValueError(f"第 {n} 页封底 {field} 超出离线安全容量")
    if kind == "section" and display_units(str(page.get("subtitle", ""))) > 80:
        raise ValueError(f"第 {n} 页章节副标题超出离线安全容量")
    items = page.get("items", [])
    if kind in {"bullets", "cards", "process", "metrics"}:
        if not isinstance(items, list) or not items:
            raise ValueError(f"第 {n} 页需要非空 items")
        cap = {"bullets": 6, "cards": 6, "process": 5, "metrics": 4}[kind]
        if len(items) > cap:
            raise ValueError(f"第 {n} 页最多支持 {cap} 项；请由模型拆页或重新编排")
        for j, item in enumerate(items, 1):
            if kind == "bullets":
                content = item if isinstance(item, str) else str(item.get("text") or item.get("title") or "") if isinstance(item, dict) else ""
                if not content.strip() or display_units(content) > 110:
                    raise ValueError(f"第 {n} 页第 {j} 项超出离线安全容量；请精简或拆页")
            elif kind in {"cards", "process"}:
                if not isinstance(item, dict) or not str(item.get("title", "")).strip():
                    raise ValueError(f"第 {n} 页第 {j} 项需要 title")
                title_cap = 20 if kind == "cards" else 14
                body_cap = 70 if kind == "cards" else 38
                if display_units(str(item["title"])) > title_cap or display_units(str(item.get("body", ""))) > body_cap:
                    raise ValueError(f"第 {n} 页第 {j} 项超出离线安全容量；请精简或拆页")
            else:
                if not isinstance(item, dict) or not str(item.get("label", "")).strip() or "value" not in item:
                    raise ValueError(f"第 {n} 页第 {j} 项需要 label 和 value")
                if display_units(str(item["label"])) > 18 or display_units(str(item["value"])) > 16:
                    raise ValueError(f"第 {n} 页第 {j} 项指标超出离线安全容量")
        if kind in {"bullets", "metrics"}:
            variant = resolved_variant(page, kind)
            featured = page.get("featured_index")
            if featured is not None and (type(featured) is not int or not 0 <= featured < len(items)):
                raise ValueError(f"第 {n} 页 featured_index 须为有效的从 0 开始的项序号")
            if kind == "bullets":
                if variant == "spacious" and len(items) > 3:
                    raise ValueError(f"第 {n} 页宽松要点最多 3 项")
                if variant == "lead" and (len(items) < 2 or featured is None):
                    raise ValueError(f"第 {n} 页主次要点需要至少 2 项与 featured_index")
                if variant == "lead":
                    main = items[featured]
                    main_text = main if isinstance(main, str) else str(main.get("text") or main.get("title") or "")
                    if display_units(main_text) > 56:
                        raise ValueError(f"第 {n} 页主次要点的重点文字过长，请精简或改用 balanced")
            elif variant == "hero" and len(items) != 1:
                raise ValueError(f"第 {n} 页单个大数字只接受 1 项指标")
            elif variant == "lead_support" and (len(items) < 2 or featured is None):
                raise ValueError(f"第 {n} 页主次指标需要至少 2 项与 featured_index")
            elif variant == "lead_support" and display_units(str(items[featured]["value"])) > 12:
                raise ValueError(f"第 {n} 页主指标数值过长，请换 grid 或精简单位")
        if kind == "cards":
            variant = resolved_variant(page, kind)
            if variant == "columns" and len(items) not in (2, 3):
                raise ValueError(f"第 {n} 页开放分栏变体只接受 2 或 3 项")
            if variant == "stat_rows" and len(items) != 6:
                raise ValueError(f"第 {n} 页六项分组变体只接受 6 项")
        if kind == "process":
            variant = resolved_variant(page, kind)
            if variant == "rail" and len(items) < 3:
                raise ValueError(f"第 {n} 页开放轨道流程至少需要 3 步")
    if kind == "comparison":
        if page.get("variant") not in (None, "standard", "before_after"):
            raise ValueError(f"第 {n} 页对比变体不受支持")
        if not isinstance(page.get("left"), dict) or not isinstance(page.get("right"), dict):
            raise ValueError(f"第 {n} 页 comparison 需要 left 和 right 对象")
        for side in ("left", "right"):
            item = page[side]
            if display_units(str(item.get("title", ""))) > 30 or display_units(str(item.get("body", ""))) > 130:
                raise ValueError(f"第 {n} 页 {side} 对比内容超出离线安全容量")
        if page.get("variant") == "before_after":
            if (not str(page.get("change_summary", "")).strip()
                or display_units(str(page["change_summary"])) > 72
                or any(display_units(str(page[side].get("body", ""))) > 95 for side in ("left", "right"))):
                raise ValueError(f"第 {n} 页前后对比须有简短变化说明，且两侧正文不能过长")
    if kind in fallback_catalog():
        validate_fallback(page, kind, n)
    return kind


def add_logo(slide, layout: dict, theme: dict, *, dark=False, content_header=False, tech_header=False):
    config = read_json(LOGO_CONFIG)
    appearance = "white" if dark else theme["logo_appearance"]
    svg_name = config["assets"][config["default"]["variant"]][appearance]
    png = (LOGO_CONFIG.parent / svg_name).with_suffix(".png")
    if not png.is_file():
        raise FileNotFoundError(f"离线品牌 Logo 缺失：{png}")
    if content_header:
        header_key = "tech_content_header" if tech_header else "content_header"
        x, y, width, height = layout[header_key]["logo_box_inches"]
        pic = slide.shapes.add_picture(str(png), Inches(x), Inches(y), width=Inches(width), height=Inches(height))
    else:
        width = config["default"]["width_pt"] / 72
        x = layout["canvas"]["width_inches"] - layout["canvas"]["margin_inches"] - width
        pic = slide.shapes.add_picture(str(png), Inches(x), Inches(layout["logo_anchor"]["top_inches"]), width=Inches(width))
    pic.name = f"brand:logo:{config['default']['variant']}:{appearance}"
    return pic


def add_content_atmosphere(slide, layout: dict, theme_name: str, theme: dict):
    """Add editable diffuse circles behind every new-drawn content element."""
    spec = layout["content_atmosphere"]
    if not spec["enabled"]:
        return
    for number, item in enumerate(spec["circles_by_theme"][theme_name], 1):
        role = item["color_role"]
        opacity = item["opacity"]
        if role not in {"primary", "secondary", "tertiary", "soft"} or not 0 < opacity <= 0.15:
            raise ValueError("正文弥散层只能使用已锁定主题色和低不透明度")
        shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, *(Inches(value) for value in item["box_inches"]))
        shape.name = f"brand:atmosphere:{number}"
        color(shape, theme[role])
        solid = shape._element.spPr.solidFill
        alpha = OxmlElement("a:alpha")
        alpha.set("val", str(round(opacity * 100000)))
        solid.srgbClr.append(alpha)
        effects = OxmlElement("a:effectLst")
        soft_edge = OxmlElement("a:softEdge")
        soft_edge.set("rad", str(Pt(spec["blur_pt"])))
        effects.append(soft_edge)
        shape._element.spPr.append(effects)


def add_tech_content_header(slide, layout: dict):
    """Reuse the original editable header group and its embedded images."""
    spec = layout["tech_content_header"]
    asset = (SKILL / spec["asset"]).resolve()
    if not asset.is_relative_to(SKILL) or not asset.is_file():
        raise FileNotFoundError(f"科技风本地标题栏缺失：{asset}")
    source_slide = Presentation(str(asset)).slides[0]
    groups = [shape for shape in source_slide.shapes if shape.shape_type == 6]
    if len(groups) != 1:
        raise ValueError("科技风标题栏组件应恰好包含一个图形组")
    element = deepcopy(groups[0]._element)
    for blip in element.xpath(".//a:blip"):
        rid = blip.get(qn("r:embed"))
        if rid:
            image_part = source_slide.part.related_part(rid)
            _, new_rid = slide.part.get_or_add_image_part(BytesIO(image_part.blob))
            blip.set(qn("r:embed"), new_rid)
    slide.shapes._spTree.insert_element_before(element, "p:extLst")


def base_slide(pres: Presentation, profile: dict, layout: dict, theme: dict, index: int,
               *, dark=False, header=None):
    slide = pres.slides.add_slide(pres.slide_layouts[6])
    background = theme["canvas"] if not dark else theme["closing_canvas"]
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(background)
    if header:
        # PowerPoint may discard a slide background when InsertFromFile clones
        # the source design. A native bottom rectangle preserves the canvas.
        canvas = rectangle(slide, 0, 0, layout["canvas"]["width_inches"],
                           layout["canvas"]["height_inches"], background)
        canvas.name = "brand:canvas"
        theme_name = next(name for name, values in profile["themes"].items() if values is theme)
        tech_header = theme_name == "deep-blue-tech"
        if tech_header:
            add_tech_content_header(slide, layout)
        else:
            add_content_atmosphere(slide, layout, theme_name, theme)
    else:
        tech_header = False
    add_logo(slide, layout, theme, dark=dark, content_header=bool(header), tech_header=tech_header)
    if header:
        spec = layout["tech_content_header"] if tech_header else layout["content_header"]
        ink = theme["neutral"]["white"] if (dark or tech_header) else theme[spec["title_color_role"]]
        title = text_box(slide, header, *spec["title_box_inches"], spec["title_size_pt"],
                         ink, profile["typography"]["heading"], bold=not tech_header,
                         align=PP_ALIGN.CENTER if tech_header else PP_ALIGN.LEFT)
        title.name = "brand:content-title"
        if not tech_header:
            x1, y1, length, _ = spec["rule_inches"]
            rule = connector(slide, x1, y1, x1 + length, y1, theme["primary"], spec["rule_width_pt"])
            rule.name = "brand:content-rule"
        text_box(slide, f"{index:02d}", 12.15, 7.0, 0.5, 0.28, 10,
                 theme["muted"] if not dark else theme["neutral"]["on_dark_muted"], profile["typography"]["latin_numeric"], align=PP_ALIGN.RIGHT)
    return slide


def render_assertion_evidence(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    series = page["series"]
    unit = str(page.get("unit", ""))
    first, last = series[0]["value"], series[-1]["value"]
    delta = last - first
    fmt = lambda value: f"{value:g}"
    summary = str(page.get("summary") or f"{series[0]['label']} {fmt(first)}{unit}，{series[-1]['label']} {fmt(last)}{unit}")
    if display_units(summary) > 70:
        raise ValueError(f"第 {index} 页趋势摘要超出安全容量")
    text_box(slide, summary, 0.78, 1.59, 10.75, 0.65,
             18, theme["muted"], body)
    chart_left, chart_right, chart_top, chart_bottom = 1.18, 9.10, 2.93, 6.32
    max_value = max(row["value"] for row in series)
    raw_step = max(0.001, max_value * 1.1 / 4)
    magnitude = 10 ** math.floor(math.log10(raw_step))
    step = next((magnitude * factor for factor in (1, 2, 2.5, 4, 5, 10)
                 if magnitude * factor >= raw_step), magnitude * 10)
    scale_max = step * 4
    y_coord = lambda value: chart_bottom - value / scale_max * (chart_bottom - chart_top)
    for step in range(5):
        value = scale_max * step / 4
        y = y_coord(value)
        connector(slide, chart_left, y, chart_right, y, theme["border"], 0.65)
        text_box(slide, fmt(value), 0.52, y - 0.15, 0.56, 0.28,
                 10, theme["muted"], profile["typography"]["latin_numeric"], align=PP_ALIGN.RIGHT)
    xs = [1.47 + (8.58 - 1.47) * i / (len(series) - 1) for i in range(len(series))]
    for i, (row, x) in enumerate(zip(series, xs)):
        y = y_coord(row["value"])
        if i:
            connector(slide, xs[i-1], y_coord(series[i-1]["value"]), x, y, theme["primary"], 2.7)
        mark = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x-0.075), Inches(y-0.075), Inches(0.15), Inches(0.15))
        color(mark, theme["surface"], theme["primary"])
        mark.line.width = Pt(2)
        text_box(slide, fmt(row["value"]), x-0.37, y-0.48, 0.74, 0.30,
                 16, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
        text_box(slide, row["label"], x-0.53, 6.43, 1.06, 0.31,
                 11, theme["muted"], body, align=PP_ALIGN.CENTER)
    connector(slide, 9.53, 3.08, 9.53, 6.34, theme["border"], 1.0)
    sign = "+" if delta > 0 else ""
    text_box(slide, f"{sign}{fmt(delta)}", 9.91, 3.51, 2.45, 0.78,
             38, theme["primary"], head, bold=True)
    text_box(slide, f"变化量（{unit}）" if unit else "变化量", 9.93, 4.39, 2.35, 0.42,
             18, theme["text"], head, bold=True)
    rectangle(slide, 9.93, 5.01, 2.4, 0.028, theme["primary"])
    direction = "下降" if delta < 0 else "上升" if delta > 0 else "持平"
    text_box(slide, f"{len(series)} 个时期连续展示\n末期相较首期{direction}",
             9.93, 5.27, 2.42, 0.86, 15, theme["muted"], body)
    text_box(slide, "数据来源：" + str(page["data_source"]), 0.78, 7.01, 11.8, 0.23,
             10, theme["muted"], body)
    return slide


def render_priority_grid(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    lead, support = page["lead"], page["support"]
    if resolved_variant(page, "priority_grid") == "top":
        rectangle(slide, 0.72, 1.69, 11.83, 1.82, theme["soft"], theme["border"])
        rectangle(slide, 0.72, 1.69, 0.09, 1.82, theme["primary"])
        text_box(slide, "核心结论", 1.05, 1.91, 3.5, 0.34,
                 15, theme["primary"], head, bold=True)
        text_box(slide, str(lead["title"]), 1.05, 2.37, 4.23, 0.75,
                 27, theme["text"], head, bold=True)
        text_box(slide, str(lead["body"]), 5.42, 2.18, 6.73, 1.03,
                 19, theme["text"], body, valign=MSO_ANCHOR.MIDDLE)
        count = len(support)
        gap = 0.18
        box_w = (11.83 - gap * (count - 1)) / count
        for i, item in enumerate(support):
            x = 0.72 + i * (box_w + gap)
            rectangle(slide, x, 3.86, box_w, 2.03, theme["surface"], theme["border"])
            rectangle(slide, x, 3.86, box_w, 0.06, theme["primary"])
            text_box(slide, f"{i+1:02d}", x + 0.20, 4.10, box_w - 0.40, 0.38,
                     15, theme["primary"], head, bold=True)
            text_box(slide, str(item["title"]), x + 0.20, 4.58, box_w - 0.40, 0.43,
                     18, theme["text"], head, bold=True)
            text_box(slide, str(item["body"]), x + 0.20, 5.15, box_w - 0.40, 0.55,
                     15, theme["muted"], body, valign=MSO_ANCHOR.TOP)
        return slide
    rectangle(slide, 0.72, 1.57, 5.02, 4.92, theme["soft"], theme["border"])
    rectangle(slide, 0.72, 1.57, 0.11, 4.92, theme["primary"])
    text_box(slide, "核心结论", 1.09, 1.93, 4.20, 0.35,
             15, theme["primary"], head, bold=True)
    text_box(slide, str(lead["title"]), 1.09, 2.42, 4.20, 1.15,
             29, theme["text"], head, bold=True)
    text_box(slide, str(lead.get("body", "")), 1.09, 3.92, 4.17, 1.72,
             19, theme["text"], body, valign=MSO_ANCHOR.TOP)
    count = len(support)
    row_count = 2 if count in (2, 4) else 3
    col_count = 2 if count == 4 else 1
    gap = 0.18
    box_w = (6.48 - gap * (col_count - 1)) / col_count
    box_h = (4.92 - gap * (row_count - 1)) / row_count
    for i, item in enumerate(support):
        x = 5.96 + (i % col_count) * (box_w + gap)
        y = 1.57 + (i // col_count) * (box_h + gap)
        rectangle(slide, x, y, box_w, box_h, theme["surface"], theme["border"])
        text_box(slide, f"{i+1:02d}", x+0.20, y+0.13, 0.53, 0.39,
                 15, theme["primary"], profile["typography"]["latin_numeric"], bold=True)
        text_box(slide, str(item["title"]), x+0.20, y+0.58, box_w-0.40, 0.44,
                 18, theme["text"], head, bold=True)
        text_box(slide, str(item.get("body", "")), x+0.20, y+1.08,
                 box_w-0.40, max(0.4, box_h-1.28), 15 if count == 4 else 17,
                 theme["muted"], body, valign=MSO_ANCHOR.TOP)
    return slide


def render_evidence_matrix(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    sections = page["sections"]
    locations = [(0.72, 1.64, 6.13, 4.90)]
    gap = 0.15
    right_h = (4.90 - gap * (len(sections)-2)) / (len(sections)-1)
    locations += [(7.04, 1.64+i*(right_h+gap), 5.52, right_h) for i in range(len(sections)-1)]
    for i, (item, (x, y, w, h)) in enumerate(zip(sections, locations)):
        rectangle(slide, x, y, w, h, theme["surface"], theme["border"])
        rectangle(slide, x, y, w, 0.055, theme["primary"] if i == 0 else theme["secondary"])
        text_box(slide, "主证据" if i == 0 else f"证据 {i+1:02d}", x+0.22, y+0.22, w-0.44, 0.31,
                 13, theme["primary"], head, bold=True)
        compact = len(sections) == 4 and i > 0
        text_box(slide, str(item["title"]), x+0.22, y+(0.77 if i == 0 else 0.44 if compact else 0.57), w-0.44,
                 0.65 if i == 0 else 0.38 if compact else 0.42, 25 if i == 0 else 18,
                 theme["text"], head, bold=True)
        text_box(slide, str(item.get("body", "")), x+0.22, y+(1.68 if i == 0 else 0.89 if compact else 1.06),
                 w-0.44, h-(2.0 if i == 0 else 1.01 if compact else 1.2), 20 if i == 0 else 14 if compact else 15,
                 theme["muted"], body, valign=MSO_ANCHOR.TOP)
    source = str(page.get("data_source", "")).strip()
    if source:
        text_box(slide, "资料来源：" + source, 0.75, 6.86, 11.4, 0.28,
                 10, theme["muted"], body)
    return slide


def render_problem_solution_outcome(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    for i, (key, label) in enumerate((("problem", "问题"), ("solution", "方案"), ("outcome", "结果"))):
        item = page[key]
        x = 0.74 + i * 4.21
        rectangle(slide, x, 1.65, 3.86, 0.055, theme["primary"] if i == 1 else theme["border"])
        text_box(slide, f"0{i+1}  {label}", x, 1.92, 3.7, 0.42, 15,
                 theme["primary"], head, bold=True)
        text_box(slide, item["title"], x, 2.60, 3.70, 0.82, 23,
                 theme["text"], head, bold=True)
        text_box(slide, item["body"], x, 3.75, 3.70, 2.12, 18,
                 theme["muted"], body, valign=MSO_ANCHOR.TOP)
        if i < 2:
            connector(slide, x + 3.87, 3.06, x + 4.14, 3.06, theme["primary"], 1.3)
    return slide


def render_layered_architecture(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    layers = page["layers"]
    top, bottom, gap = 1.55, 6.56, 0.20
    row_h = (bottom - top - gap * (len(layers) - 1)) / len(layers)
    for i, layer in enumerate(layers):
        y = top + i * (row_h + gap)
        rectangle(slide, 0.73, y, 2.05, row_h, theme["primary"] if i == 0 else theme["soft"])
        text_box(slide, layer["title"], 0.92, y+0.17, 1.68, row_h-0.34, 18,
                 theme["neutral"]["white"] if i == 0 else theme["text"], head, bold=True)
        items = layer["items"]
        cell_gap = 0.14
        cell_w = (9.55 - cell_gap * (len(items) - 1)) / len(items)
        for j, item in enumerate(items):
            x = 3.02 + j * (cell_w + cell_gap)
            rectangle(slide, x, y, cell_w, row_h, theme["surface"], theme["border"])
            text_box(slide, item, x+0.14, y+0.14, cell_w-0.28, row_h-0.28,
                     17, theme["text"], body, align=PP_ALIGN.CENTER)
        if i < len(layers)-1:
            connector(slide, 7.76, y+row_h, 7.76, y+row_h+gap, theme["primary"], 1.5)
    return slide


def render_longform_metric(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    paragraphs = page["paragraphs"]
    box_h = 4.80 / len(paragraphs)
    for i, paragraph in enumerate(paragraphs):
        y = 1.69 + i * box_h
        rectangle(slide, 0.76, y+0.12, 0.055, box_h-0.33, theme["border"])
        text_box(slide, paragraph, 0.98, y, 7.20, box_h-0.13,
                 18, theme["text"], body, valign=MSO_ANCHOR.TOP)
    metric = page["metric"]
    connector(slide, 8.56, 1.67, 8.56, 6.42, theme["border"], 1.0)
    text_box(slide, metric["value"], 8.94, 2.16, 3.38, 1.16,
             43, theme["primary"], head, bold=True)
    text_box(slide, metric["label"], 8.96, 3.43, 3.16, 0.80,
             19, theme["text"], head, bold=True)
    rectangle(slide, 8.96, 4.51, 2.95, 0.035, theme["primary"])
    text_box(slide, "来源：" + metric["source"], 8.96, 4.77, 3.24, 1.20,
             13, theme["muted"], body, valign=MSO_ANCHOR.TOP)
    return slide


def render_data_table(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    tracker = page.get("variant") == "action_tracker"
    columns = ["问题 / 风险", "对应措施", "责任人", "完成期限", "当前状态"] if tracker else page["columns"]
    rows = [[item[key] for key in ("issue", "action", "owner", "due", "status")]
            for item in page["actions"]] if tracker else page["rows"]
    x0, y0, total_w = 0.74, 1.64, 11.85
    header_h = 0.62
    row_h = min(0.69, 4.82 / len(rows))
    weights = [2.2, 4.3, 1.45, 2.25, 1.65] if tracker else [1.30] + [1.0] * (len(columns) - 1)
    widths = [total_w * weight / sum(weights) for weight in weights]
    for row_idx, cells in enumerate([columns] + rows):
        y = y0 if row_idx == 0 else y0 + header_h + (row_idx - 1) * row_h
        h = header_h if row_idx == 0 else row_h
        x = x0
        for col_idx, (value, w) in enumerate(zip(cells, widths)):
            fill = theme["primary"] if row_idx == 0 else theme["surface"] if row_idx % 2 else theme["soft"]
            rectangle(slide, x, y, w, h, fill, theme["border"])
            ink = theme["neutral"]["white"] if row_idx == 0 else theme["text"]
            text_box(slide, str(value), x + 0.14, y + 0.05, w - 0.28, h - 0.10,
                     15 if row_idx == 0 else 14 if len(rows) >= 7 else 16,
                     ink, head if row_idx == 0 else body, bold=row_idx == 0)
            x += w
    source = str(page.get("data_source", "")).strip()
    if source:
        text_box(slide, "资料来源：" + source, x0, 6.95, 11.45, 0.25, 10, theme["muted"], body)
    return slide


def render_milestone_timeline(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    items = page["milestones"]
    n = len(items)
    if resolved_variant(page, "milestone_timeline") == "vertical":
        first_y, row_h = 1.63, 4.94 / n
        connector(slide, 2.82, first_y + row_h / 2, 2.82,
                  first_y + (n - 0.5) * row_h, theme["primary"], 1.8)
        for i, item in enumerate(items):
            y = first_y + i * row_h
            text_box(slide, item["date"], 0.84, y + 0.10, 1.63, 0.42,
                     16, theme["primary"], head, bold=True, align=PP_ALIGN.RIGHT)
            node = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(2.72), Inches(y + row_h / 2 - 0.10),
                                          Inches(0.20), Inches(0.20))
            color(node, theme["primary"])
            text_box(slide, item["title"], 3.27, y + 0.03, 2.55, 0.42,
                     17, theme["text"], head, bold=True)
            text_box(slide, str(item.get("body", "")), 5.70, y + 0.03, 6.42, 0.58,
                     15, theme["muted"], body, valign=MSO_ANCHOR.TOP)
            if i < n - 1:
                connector(slide, 3.27, y + row_h - 0.08, 12.20, y + row_h - 0.08,
                          theme["border"], 0.8)
        return slide
    cell_w = 11.84 / n
    centers = [0.75 + (i + 0.5) * cell_w for i in range(n)]
    connector(slide, centers[0], 3.12, centers[-1], 3.12, theme["border"], 2.0)
    for i, (item, x) in enumerate(zip(items, centers)):
        color_value = theme["primary"] if i == n - 1 else theme["secondary"] if i % 2 else theme["primary"]
        text_box(slide, item["date"], x - cell_w / 2 + 0.08, 2.12, cell_w - 0.16, 0.47,
                 17 if n <= 4 else 14, color_value, head, bold=True, align=PP_ALIGN.CENTER)
        mark = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - 0.11), Inches(3.01), Inches(0.22), Inches(0.22))
        color(mark, color_value)
        connector(slide, x, 3.23, x, 3.48, color_value, 1.2)
        text_box(slide, item["title"], x - cell_w / 2 + 0.09, 3.63, cell_w - 0.18, 0.68,
                 19 if n <= 4 else 16, theme["text"], head, bold=True, align=PP_ALIGN.CENTER)
        text_box(slide, str(item.get("body", "")), x - cell_w / 2 + 0.13, 4.41, cell_w - 0.26, 1.38,
                 16 if n <= 4 else 13, theme["muted"], body, valign=MSO_ANCHOR.TOP,
                 align=PP_ALIGN.CENTER)
    return slide


def render_image_case(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    x, y, w, h = 0.74, 1.64, 6.13, 4.90
    rectangle(slide, x, y, w, h, theme["surface"], theme["border"])
    image_path = Path(page["image_path"])
    with Image.open(image_path) as image:
        aspect = image.width / image.height
    max_w, max_h = w - 0.18, h - 0.18
    pic_w = min(max_w, max_h * aspect)
    pic_h = pic_w / aspect
    pic = slide.shapes.add_picture(str(image_path), Inches(x + (w - pic_w) / 2),
                                   Inches(y + (h - pic_h) / 2), width=Inches(pic_w), height=Inches(pic_h))
    pic.name = "case:source-image"
    caption = str(page.get("image_caption", "")).strip()
    if caption:
        text_box(slide, caption, x, 6.68, w, 0.31, 11, theme["muted"], body)
    text_box(slide, page["case_title"], 7.22, 1.89, 5.05, 0.82,
             27, theme["text"], head, bold=True)
    rectangle(slide, 7.22, 2.82, 2.12, 0.04, theme["primary"])
    if page.get("variant") == "annotated":
        for i, mark in enumerate(page["annotations"], 1):
            px = x + (w - pic_w) / 2 + pic_w * mark["x"] - 0.16
            py = y + (h - pic_h) / 2 + pic_h * mark["y"] - 0.16
            pin = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(px), Inches(py), Inches(0.32), Inches(0.32))
            color(pin, theme["primary"], theme["neutral"]["white"])
            text_box(slide, str(i), px, py + 0.01, 0.32, 0.29, 12,
                     theme["neutral"]["white"], head, bold=True, align=PP_ALIGN.CENTER)
            row_y = 3.02 + (i - 1) * 0.79
            badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(7.22), Inches(row_y + 0.08), Inches(0.32), Inches(0.32))
            color(badge, theme["primary"])
            text_box(slide, str(i), 7.22, row_y + 0.08, 0.32, 0.29, 12,
                     theme["neutral"]["white"], head, bold=True, align=PP_ALIGN.CENTER)
            text_box(slide, mark["label"], 7.72, row_y, 4.55, 0.64,
                     16, theme["text"], body, valign=MSO_ANCHOR.TOP)
        rectangle(slide, 7.22, 5.63, 5.06, 0.86, theme["soft"])
        rectangle(slide, 7.22, 5.63, 0.07, 0.86, theme["primary"])
        text_box(slide, page["takeaway"], 7.48, 5.76, 4.55, 0.60,
                 16, theme["text"], head, bold=True)
        return slide
    text_box(slide, page["body"], 7.22, 3.13, 5.02, 1.75,
             18, theme["muted"], body, valign=MSO_ANCHOR.TOP)
    rectangle(slide, 7.22, 5.25, 5.06, 1.12, theme["soft"])
    rectangle(slide, 7.22, 5.25, 0.07, 1.12, theme["primary"])
    text_box(slide, page["takeaway"], 7.48, 5.43, 4.55, 0.78,
             17, theme["text"], head, bold=True)
    return slide


def render_comparison_chart(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    categories, series = page["categories"], page["series"]
    unit = str(page.get("unit", ""))
    text_box(slide, "同口径数值对比" + (f"（{unit}）" if unit else ""),
             0.76, 1.44, 5.0, 0.38, 16, theme["muted"], body)
    for i, group in enumerate(series):
        key_color = theme["primary"] if i == 0 else theme["secondary"]
        rectangle(slide, 8.02 + i * 2.10, 1.47, 0.17, 0.17, key_color)
        text_box(slide, group["name"], 8.26 + i * 2.10, 1.39, 1.88, 0.34,
                 13, theme["text"], body)
    values = [v for group in series for v in group["values"]]
    scale = max(max(values), 1)
    n = len(categories)
    row_h = 4.79 / n
    for i, category in enumerate(categories):
        top = 1.92 + i * row_h
        text_box(slide, category, 0.78, top + 0.14, 2.12, max(0.43, row_h - 0.20),
                 16, theme["text"], head, bold=True)
        for j, group in enumerate(series):
            value = group["values"][i]
            bar_y = top + 0.08 + j * (0.32 if len(series) == 2 else 0)
            if len(series) == 1:
                bar_y = top + 0.24
            color_value = theme["primary"] if j == 0 else theme["secondary"]
            width = 7.25 * value / scale
            if width > 0:
                rectangle(slide, 3.08, bar_y, width, 0.22, color_value)
            text_box(slide, f"{value:g}", min(10.47, 3.17 + width), bar_y - 0.04, 1.02, 0.30,
                     13, theme["text"], body)
        if i < n - 1:
            connector(slide, 0.76, top + row_h, 12.47, top + row_h, theme["border"], 0.6)
    text_box(slide, "数据来源：" + page["data_source"], 0.76, 6.99, 11.50, 0.25,
             10, theme["muted"], body)
    return slide


def render_target_actual_gap(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    number = lambda value: f"{value:,.2f}".rstrip("0").rstrip(".")
    target, actual = page["target"], page["actual"]
    for x, label, value, ink in ((0.75, "目标", target, theme["primary"]),
                                 (6.83, "实际", actual, theme["secondary"])):
        rectangle(slide, x, 1.70, 5.72, 2.45, theme["surface"], theme["border"])
        rectangle(slide, x, 1.70, 5.72, 0.10, ink)
        text_box(slide, label, x + 0.30, 2.01, 2.3, 0.46, 21, theme["muted"], head)
        text_box(slide, number(value), x + 0.30, 2.56, 4.63, 0.92, 42, theme["text"], head, bold=True)
        text_box(slide, page["unit"], x + 4.80, 3.10, 0.65, 0.36, 16, theme["muted"], body)
    delta = actual - target
    sign = "+" if delta > 0 else ""
    rectangle(slide, 0.75, 4.45, 11.80, 0.67, theme["soft"])
    text_box(slide, f"{page['period']}　实际－目标：{sign}{number(delta)} {page['unit']}",
             1.02, 4.56, 11.0, 0.42, 20, theme["primary"], head, bold=True)
    text_box(slide, "偏差说明", 0.80, 5.44, 2.13, 0.46, 21, theme["primary"], head, bold=True)
    text_box(slide, page["gap_reason"], 2.77, 5.40, 9.55, 0.96,
             18, theme["text"], body, valign=MSO_ANCHOR.TOP)
    text_box(slide, "资料来源：" + page["data_source"], 0.76, 6.98, 11.5, 0.25,
             10, theme["muted"], body)
    return slide


def render_decision_matrix(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    criteria, options = page["criteria"], page["options"]
    left, top, total = 0.76, 1.64, 11.80
    first = 2.32
    col_w = (total - first) / len(options)
    row_h = 0.70
    recommended = page.get("recommended_index")
    rectangle(slide, left, top, first, row_h, theme["primary"])
    text_box(slide, "评价标准", left + 0.18, top + 0.09, first - 0.30, 0.48,
             18, theme["neutral"]["white"], head, bold=True)
    for j, option in enumerate(options):
        x = left + first + j * col_w
        rectangle(slide, x, top, col_w, row_h,
                  theme["primary"] if j == recommended else theme["soft"], theme["border"])
        text_box(slide, option["name"], x + 0.14, top + 0.08, col_w - 0.28, 0.52,
                 18, theme["neutral"]["white"] if j == recommended else theme["text"],
                 head, bold=True, align=PP_ALIGN.CENTER)
    for i, criterion in enumerate(criteria):
        y = top + row_h * (i + 1)
        rectangle(slide, left, y, first, row_h, theme["surface"], theme["border"])
        text_box(slide, criterion, left + 0.18, y + 0.08, first - 0.30, 0.52,
                 17, theme["text"], body)
        for j, option in enumerate(options):
            x = left + first + j * col_w
            rectangle(slide, x, y, col_w, row_h,
                      theme["soft"] if j == recommended else theme["surface"], theme["border"])
            text_box(slide, str(option["scores"][i]), x + 0.12, y + 0.09, col_w - 0.24, 0.50,
                     20, theme["primary"] if j == recommended else theme["text"],
                     head, bold=j == recommended, align=PP_ALIGN.CENTER)
    y = top + row_h * (len(criteria) + 1)
    rectangle(slide, left, y, first, row_h, theme["soft"], theme["border"])
    text_box(slide, "总分", left + 0.18, y + 0.09, first - 0.3, 0.50, 18,
             theme["text"], head, bold=True)
    for j, option in enumerate(options):
        x = left + first + j * col_w
        rectangle(slide, x, y, col_w, row_h, theme["soft"], theme["border"])
        text_box(slide, str(sum(option["scores"])), x + 0.12, y + 0.09, col_w - 0.24, 0.50,
                 21, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
    if recommended is not None:
        text_box(slide, f"建议：{options[recommended]['name']}。{page['decision_reason']}",
                 0.78, 6.24, 11.65, 0.50, 16, theme["text"], body)
    text_box(slide, "评分来源：" + page["data_source"], 0.78, 6.98, 11.48, 0.25,
             10, theme["muted"], body)
    return slide


def render_responsibility_swimlane(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    phases, lanes = page["phases"], page["lanes"]
    x0, y0, role_w, total_w = 0.75, 1.68, 1.90, 11.82
    phase_w = (total_w - role_w) / len(phases)
    header_h = 0.70
    row_h = 4.50 / len(lanes)
    rectangle(slide, x0, y0, role_w, header_h, theme["primary"])
    text_box(slide, "角色 / 阶段", x0 + 0.16, y0 + 0.10, role_w - 0.28, 0.48,
             16, theme["neutral"]["white"], head, bold=True)
    for j, phase in enumerate(phases):
        x = x0 + role_w + j * phase_w
        rectangle(slide, x, y0, phase_w, header_h, theme["soft"], theme["border"])
        text_box(slide, f"{j+1:02d} {phase}", x + 0.12, y0 + 0.10, phase_w - 0.24, 0.48,
                 17 if len(phases) <= 4 else 15, theme["primary"], head, bold=True,
                 align=PP_ALIGN.CENTER)
    for i, lane in enumerate(lanes):
        y = y0 + header_h + i * row_h
        rectangle(slide, x0, y, role_w, row_h, theme["soft"], theme["border"])
        text_box(slide, lane["role"], x0 + 0.16, y + 0.12, role_w - 0.28, row_h - 0.24,
                 18, theme["text"], head, bold=True)
        for j, task in enumerate(lane["tasks"]):
            x = x0 + role_w + j * phase_w
            rectangle(slide, x, y, phase_w, row_h, theme["surface"], theme["border"])
            if task.strip():
                rectangle(slide, x + 0.09, y + 0.13, 0.055, row_h - 0.26, theme["primary"])
                text_box(slide, task, x + 0.22, y + 0.15, phase_w - 0.34, row_h - 0.30,
                         16 if len(phases) <= 4 else 14, theme["text"], body,
                         valign=MSO_ANCHOR.TOP)
    return slide


def render_bullets(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    items = [item if isinstance(item, str) else str(item.get("text") or item.get("title"))
             for item in page["items"]]
    variant = resolved_variant(page, "bullets")
    if variant == "lead":
        featured = page["featured_index"]
        lead = items[featured]
        rest = [value for i, value in enumerate(items) if i != featured]
        rectangle(slide, 0.76, 1.62, 11.82, 1.43, theme["soft"])
        rectangle(slide, 0.76, 1.62, 0.11, 1.43, theme["primary"])
        text_box(slide, "本页重点", 1.10, 1.77, 2.1, 0.31, 14,
                 theme["primary"], head, bold=True)
        text_box(slide, lead, 1.10, 2.11, 10.98, 0.68, 25,
                 theme["text"], head, bold=True)
        row_h = min(0.84, 3.18 / len(rest))
        y = 3.38
        for value in rest:
            rectangle(slide, 0.81, y + (row_h - 0.13) / 2, 0.13, 0.13, theme["primary"])
            text_box(slide, value, 1.12, y, 11.0, row_h, 19, theme["text"], body)
            y += row_h + 0.09
        return slide
    if variant == "spacious":
        row_h = 1.15
        gap = 0.30
        y = 1.73 + (3 - len(items)) * 0.28
        size = 24
    elif variant == "compact":
        row_h = min(0.72, 4.82 / len(items))
        gap = 0.08
        y = 1.49
        size = 18
    else:
        row_h = min(0.82, 4.75 / len(items))
        gap = 0.12
        y = 1.53
        size = 21
    for value in items:
        marker_size = 0.17 if variant == "spacious" else 0.13
        rectangle(slide, 0.78, y + (row_h - marker_size) / 2,
                  marker_size, marker_size, theme["primary"])
        text_box(slide, value, 1.12, y, 11.0, row_h, size, theme["text"], body)
        y += row_h + gap
    return slide


def render_metrics(pres, page, index, profile, layout, theme):
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    head, body = profile["typography"]["heading"], profile["typography"]["body"]
    items, variant = page["items"], resolved_variant(page, "metrics")
    if variant == "hero":
        item = items[0]
        text_box(slide, str(item["value"]), 0.86, 1.87, 11.55, 1.66,
                 68, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
        rectangle(slide, 4.35, 3.78, 4.64, 0.05, theme["primary"])
        text_box(slide, str(item["label"]), 2.00, 4.02, 9.34, 0.80,
                 27, theme["text"], head, bold=True, align=PP_ALIGN.CENTER)
    elif variant == "lead_support":
        featured = page["featured_index"]
        main = items[featured]
        support = [item for i, item in enumerate(items) if i != featured]
        rectangle(slide, 0.72, 1.62, 5.63, 4.86, theme["soft"])
        rectangle(slide, 0.72, 1.62, 0.10, 4.86, theme["primary"])
        text_box(slide, str(main["value"]), 1.10, 2.45, 4.92, 1.18,
                 54, theme["primary"], head, bold=True)
        text_box(slide, str(main["label"]), 1.12, 3.83, 4.80, 0.76,
                 24, theme["text"], head, bold=True)
        gap = 0.18
        h = (4.86 - gap * (len(support) - 1)) / len(support)
        for i, item in enumerate(support):
            y = 1.62 + i * (h + gap)
            rectangle(slide, 6.57, y, 5.98, h, theme["surface"], theme["border"])
            text_box(slide, str(item["value"]), 6.89, y + 0.15, 2.25, h - 0.30,
                     28, theme["primary"], head, bold=True)
            text_box(slide, str(item["label"]), 9.25, y + 0.16, 2.87, h - 0.32,
                     17, theme["text"], body)
    else:
        gap = 0.25
        w = (11.9 - gap * (len(items)-1)) / len(items)
        for i, item in enumerate(items):
            x = 0.7 + i * (w + gap)
            rectangle(slide, x, 2.08, w, 3.32, theme["surface"], theme["border"], rounded=True)
            text_box(slide, str(item["value"]), x + 0.15, 2.72, w - 0.3, 0.9,
                     33, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
            text_box(slide, str(item["label"]), x + 0.15, 3.80, w - 0.3, 0.65,
                     19, theme["text"], body, align=PP_ALIGN.CENTER)
    source = str(page.get("data_source", "")).strip()
    if source:
        text_box(slide, "数据来源：" + source, 0.76, 6.94, 11.25, 0.30,
                 10, theme["muted"], body)
    return slide


def render_page(pres, page, index, profile, layout, theme):
    kind = validate_page(page, index)
    head = profile["typography"]["heading"]
    body = profile["typography"]["body"]
    if kind == "assertion_evidence":
        slide = render_assertion_evidence(pres, page, index, profile, layout, theme)
    elif kind == "priority_grid":
        slide = render_priority_grid(pres, page, index, profile, layout, theme)
    elif kind == "evidence_matrix":
        slide = render_evidence_matrix(pres, page, index, profile, layout, theme)
    elif kind == "problem_solution_outcome":
        slide = render_problem_solution_outcome(pres, page, index, profile, layout, theme)
    elif kind == "layered_architecture":
        slide = render_layered_architecture(pres, page, index, profile, layout, theme)
    elif kind == "longform_metric":
        slide = render_longform_metric(pres, page, index, profile, layout, theme)
    elif kind == "data_table":
        slide = render_data_table(pres, page, index, profile, layout, theme)
    elif kind == "milestone_timeline":
        slide = render_milestone_timeline(pres, page, index, profile, layout, theme)
    elif kind == "image_case":
        slide = render_image_case(pres, page, index, profile, layout, theme)
    elif kind == "comparison_chart":
        slide = render_comparison_chart(pres, page, index, profile, layout, theme)
    elif kind == "target_actual_gap":
        slide = render_target_actual_gap(pres, page, index, profile, layout, theme)
    elif kind == "decision_matrix":
        slide = render_decision_matrix(pres, page, index, profile, layout, theme)
    elif kind == "responsibility_swimlane":
        slide = render_responsibility_swimlane(pres, page, index, profile, layout, theme)
    elif kind == "free_composition":
        slide = render_free_page(pres, page, index, profile, layout, theme,
                                 (base_slide, rectangle, text_box, color))
    elif kind == "cover":
        slide = base_slide(pres, profile, layout, theme, index)
        spec = layout["cover"]
        rectangle(slide, *spec["stripe"], theme["primary"])
        text_box(slide, page["title"], *spec["title"], 42, theme["text"], head, bold=True)
        rectangle(slide, *spec["title_rule"], theme["primary"])
        subtitle = str(page.get("subtitle", "")).strip()
        if subtitle:
            text_box(slide, subtitle, *spec["subtitle"], 21, theme["muted"], body)
        if page.get("show_slogan"):
            text_box(slide, profile["brand_copy"]["slogan"], *spec["slogan"], 15, theme["primary"], body)
        if page.get("show_stock_code"):
            text_box(slide, profile["brand_copy"]["stock_code"], *spec["stock_code"],
                     12, theme["muted"], profile["typography"]["latin_numeric"])
        meta = str(page.get("meta", "")).strip()
        if meta:
            text_box(slide, meta, *spec["meta"], 14, theme["muted"], body)
    elif kind == "closing":
        slide = base_slide(pres, profile, layout, theme, index, dark=True)
        spec = layout["closing"]
        rectangle(slide, *spec["accent_rule"], theme["secondary"])
        text_box(slide, page["title"], *spec["title"], 43, theme["neutral"]["white"], head, bold=True)
        subtitle = str(page.get("subtitle", "")).strip()
        if subtitle:
            text_box(slide, subtitle, *spec["subtitle"], 21, theme["neutral"]["white"], body)
        contact = str(page.get("contact", "")).strip()
        if contact:
            text_box(slide, contact, *spec["contact"], 14, theme["neutral"]["white"], body)
    elif kind == "section":
        slide = base_slide(pres, profile, layout, theme, index)
        rectangle(slide, 0.68, 2.05, 0.16, 2.35, theme["primary"])
        text_box(slide, page["title"], 1.15, 2.20, 10.7, 1.2, 40, theme["text"], head, bold=True)
        if page.get("subtitle"):
            text_box(slide, page["subtitle"], 1.17, 3.55, 10.4, 0.75, 21, theme["muted"], body)
    elif kind == "bullets":
        slide = render_bullets(pres, page, index, profile, layout, theme)
    elif kind == "cards":
        slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
        items = page["items"]
        variant = resolved_variant(page, "cards")
        if variant == "columns":
            # Two or three equal ideas share one baseline without empty card backings.
            gap = 0.31
            width = (11.9 - (len(items) - 1) * gap) / len(items)
            for i, item in enumerate(items):
                x = 0.72 + i * (width + gap)
                rectangle(slide, x, 2.10, width, 0.09, theme["primary"])
                text_box(slide, f"{i + 1:02d}", x, 2.44, 0.65, 0.55,
                         29, theme["primary"], head, bold=True)
                text_box(slide, str(item["title"]), x, 3.12, width - 0.12, 0.65,
                         23, theme["text"], head, bold=True)
                text_box(slide, str(item.get("body", "")), x, 4.00, width - 0.20, 1.50,
                         18, theme["text"], body, valign=MSO_ANCHOR.TOP)
            return slide
        if variant == "stat_rows":
            # Six short facts form two open rows instead of another set of framed cards.
            gap = 0.32
            width = (11.9 - 2 * gap) / 3
            for i, item in enumerate(items):
                row, col = divmod(i, 3)
                x = 0.72 + col * (width + gap)
                y = 1.79 + row * 2.32
                rectangle(slide, x, y, width, 0.045, theme["primary"])
                text_box(slide, str(item["title"]), x + 0.06, y + 0.26, width - 0.18, 0.72,
                         26, theme["primary"], head, bold=True)
                text_box(slide, str(item.get("body", "")), x + 0.06, y + 1.08,
                         width - 0.18, 0.92, 17, theme["text"], body,
                         valign=MSO_ANCHOR.TOP)
            return slide
        rules = read_json(COMPOSITION_RULES)
        row_counts = rules["card_grid"][str(len(items))]
        geo = rules["geometry_inches"]
        # Estimate lines using the narrowest card on this page. A short item
        # must not inherit a tall, mostly empty card from a denser variant.
        narrowest_w = min((geo["right"] - geo["left"] - geo["column_gap"] * (count - 1)) / count
                          for count in row_counts)
        line_units = max(18, int((narrowest_w - 0.55) * 8.2))
        max_lines = max(max(1, math.ceil(display_units(str(item.get("body", ""))) / line_units))
                        for item in items)
        heights = (geo["short_card_height"], geo["normal_card_height"], geo["long_card_height"])
        cell_h = min(heights[min(max_lines, 3) - 1], geo["max_row_height"])
        total_h = len(row_counts) * cell_h + (len(row_counts) - 1) * geo["row_gap"]
        y_start = max(geo["content_top"], (1.45 + 6.55 - total_h) / 2)
        offset = 0
        for row_index, count in enumerate(row_counts):
            cell_w = (geo["right"] - geo["left"] - geo["column_gap"] * (count - 1)) / count
            y = y_start + row_index * (cell_h + geo["row_gap"])
            for column in range(count):
                item = items[offset + column]
                x = geo["left"] + column * (cell_w + geo["column_gap"])
                rectangle(slide, x, y, cell_w, cell_h, theme["surface"], theme["border"])
                # A short accent marks the heading without turning the card into a sidebar.
                rectangle(slide, x - 0.025, y + 0.20, 0.055, 0.43, theme["primary"])
                text_box(slide, str(item["title"]), x + 0.32, y + 0.18, cell_w - 0.55, 0.47,
                         21, theme["primary"], head, bold=True)
                text_box(slide, str(item.get("body", "")), x + 0.32, y + 0.78,
                         cell_w - 0.55, cell_h - 0.96, 17, theme["text"], body,
                         valign=MSO_ANCHOR.TOP)
            offset += count
    elif kind == "process":
        slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
        items = page["items"]
        if resolved_variant(page, "process") == "rail":
            gap = 0.24
            w = (11.9 - gap * (len(items) - 1)) / len(items)
            centers = [0.7 + i * (w + gap) + w / 2 for i in range(len(items))]
            connector(slide, centers[0], 3.07, centers[-1], 3.07, theme["primary"], 1.8)
            for i, (item, cx) in enumerate(zip(items, centers)):
                x = cx - w / 2
                text_box(slide, f"{i+1:02d}", x + 0.09, 2.12, w - 0.18, 0.57,
                         27, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
                node = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - 0.105), Inches(2.965),
                                              Inches(0.21), Inches(0.21))
                color(node, theme["primary"])
                text_box(slide, str(item["title"]), x + 0.08, 3.48, w - 0.16, 0.60,
                         20 if len(items) <= 4 else 18, theme["text"], head,
                         bold=True, align=PP_ALIGN.CENTER)
                text_box(slide, str(item.get("body", "")), x + 0.08, 4.25,
                         w - 0.16, 1.12, 16, theme["muted"], body,
                         valign=MSO_ANCHOR.TOP, align=PP_ALIGN.CENTER)
            return slide
        gap = 0.24
        w = (11.9 - gap * (len(items)-1)) / len(items)
        max_body_units = max(display_units(str(item.get("body", ""))) for item in items)
        compact = max_body_units <= 22
        h = 2.22 if compact else 2.88
        y = 2.34 if compact else 2.15
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("title"):
                raise ValueError(f"第 {index} 页 process 第 {i+1} 项需要 title")
            x = 0.7 + i * (w + gap)
            rectangle(slide, x, y, w, h, theme["surface"], theme["border"])
            rectangle(slide, x, y, w, 0.13, theme["primary"])
            text_box(slide, f"{i+1:02d}", x + 0.17, y + 0.27, w - 0.34, 0.55,
                     26, theme["primary"], head, bold=True)
            text_box(slide, str(item["title"]), x + 0.17, y + (0.86 if compact else 1.0), w - 0.34, 0.58,
                     20, theme["text"], head, bold=True)
            text_box(slide, str(item.get("body", "")), x + 0.17, y + (1.48 if compact else 1.66),
                     w - 0.34, 0.56 if compact else 1.05,
                     16, theme["muted"], body, valign=MSO_ANCHOR.TOP)
            if i + 1 < len(items):
                text_box(slide, "›", x + w + 0.015, y + 1.1, gap - 0.025, 0.5,
                         22, theme["primary"], head, bold=True, align=PP_ALIGN.CENTER)
    elif kind == "comparison":
        slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
        before_after = page.get("variant") == "before_after"
        max_body_units = max(display_units(str(page[side].get("body", ""))) for side in ("left", "right"))
        compact = max_body_units <= 68
        box_y = 2.00 if compact else 1.65
        box_h = 2.62 if compact else (3.69 if before_after else 4.55)
        for side, x in (("left", 0.72), ("right", 6.79)):
            item = page[side]
            rectangle(slide, x, box_y, 5.78, box_h,
                      theme["surface"], theme["border"])
            rectangle(slide, x, box_y, 5.78, 0.12, theme["primary"] if side == "left" else theme["secondary"])
            text_box(slide, str(item.get("title", "")), x + 0.33, box_y + 0.37, 5.15, 0.60,
                     24, theme["primary"], head, bold=True)
            text_box(slide, str(item.get("body", "")), x + 0.33, box_y + 1.20, 5.15,
                     1.12 if compact else (1.94 if before_after else 2.85),
                     19, theme["text"], body, valign=MSO_ANCHOR.TOP)
        if before_after:
            summary_y = 5.04 if compact else 5.60
            rectangle(slide, 0.72, summary_y, 11.85, 1.01, theme["soft"])
            rectangle(slide, 0.72, summary_y, 0.07, 1.01, theme["primary"])
            text_box(slide, "变化", 0.99, summary_y + 0.18, 0.92, 0.43,
                     19, theme["primary"], head, bold=True)
            text_box(slide, page["change_summary"], 1.98, summary_y + 0.15, 10.18, 0.62,
                     18, theme["text"], body)
    else:  # metrics
        slide = render_metrics(pres, page, index, profile, layout, theme)
    if page.get("notes"):
        slide.notes_slide.notes_text_frame.text = str(page["notes"])
    return slide


def render(plan: dict, output: Path):
    profile = read_json(PROFILE)
    layout = read_json(LAYOUT_SPEC)
    if layout.get("schema_version") != "1.0" or profile.get("schema_version") != "1.0":
        raise ValueError("离线品牌或版式配置版本不受支持")
    if layout.get("visual_effects", {}).get("shadows") != "none":
        raise ValueError("离线版式必须明确禁用阴影")
    theme_name = plan.get("theme", "blue")
    if theme_name not in profile["themes"]:
        raise ValueError(f"离线主题不可用：{theme_name}")
    locked_colors(theme_name)
    theme = profile["themes"][theme_name]
    pages = plan.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages 必须是非空列表")
    pages = list(pages)
    auto_added = []
    if plan.get("complete_deck", True):
        raise ValueError("完整演示稿的封面、目录、章节页和封底必须来自知识库；离线出稿仅支持 complete_deck:false 的内容页")
    if any(not isinstance(page, dict) or page.get("type") in ("cover", "directory", "section", "closing") for page in pages):
        raise ValueError("离线出稿仅支持内容页；封面、目录、章节页和封底必须来自知识库")
    pres = Presentation()
    pres.slide_width = Inches(layout["canvas"]["width_inches"])
    pres.slide_height = Inches(layout["canvas"]["height_inches"])
    for n, page in enumerate(pages, 1):
        page_number = page.get("_deck_page_number", n)
        if type(page_number) is not int or page_number < 1:
            raise ValueError(f"第 {n} 页整稿页码无效")
        slide = render_page(pres, page, page_number, profile, layout, theme)
        remove_shadow_effects(slide)
    output.parent.mkdir(parents=True, exist_ok=True)
    pres.save(output)
    role_overrides = {
        "dk1": theme["neutral"]["black"], "lt1": theme["neutral"]["white"],
        "dk2": theme["text"], "lt2": theme["canvas"],
        "accent1": theme["primary"], "accent2": theme["secondary"],
        "accent3": theme["tertiary"], "accent4": theme["primary"],
        "accent5": theme["secondary"], "accent6": theme["tertiary"],
        "hlink": theme["primary"], "folHlink": theme["secondary"],
    }
    freeze_uniform_deck(output, output, role_overrides=role_overrides)
    # All editable slides use the same CJK/Latin typefaces, including guided
    # pages that are later inserted beside knowledge-base template pages.
    normalize(output, output)
    color_report = audit_color_independence(output)
    if not color_report["passed"]:
        raise RuntimeError("新绘页面仍引用母版颜色槽")
    palette_report = audit_palette(output, theme_name)
    if not palette_report["passed"]:
        raise RuntimeError("新绘页面使用了主题变量之外的颜色：" +
                           str([(item["page"], item["unexpected_colors"])
                                for item in palette_report["slides"] if not item["passed"]]))
    logo_report = audit_logo(output, require_every_slide=True, theme=theme_name)
    if not logo_report["passed"]:
        raise RuntimeError("新绘页面 Logo 外观与所选风格不符：" + str(logo_report["issues"]))
    check = Presentation(output)
    checks = []
    for n, slide in enumerate(check.slides, 1):
        logos = [s for s in slide.shapes if s.name.startswith("brand:logo:")]
        atmosphere_spec = layout["content_atmosphere"]
        atmosphere = [s for s in slide.shapes if s.name.startswith("brand:atmosphere:")]
        tech_header = theme_name == "deep-blue-tech"
        expected_atmosphere = [] if tech_header else atmosphere_spec["circles_by_theme"][theme_name]
        shapes_in_order = list(slide.shapes)
        if (not shapes_in_order or shapes_in_order[0].name != "brand:canvas"
            or shapes_in_order[0].fill.fore_color.rgb != rgb(theme["canvas"])
            or len(atmosphere) != len(expected_atmosphere)
            or shapes_in_order[1:1+len(atmosphere)] != atmosphere):
            raise RuntimeError(f"第 {n} 页底层弥散形状缺失或层级错误")
        if tech_header and (len(shapes_in_order) < 2 or shapes_in_order[1].shape_type != 6):
            raise RuntimeError(f"第 {n} 页科技风标题栏原生图形组缺失")
        for shape, item in zip(atmosphere, expected_atmosphere):
            alpha = shape._element.xpath("./p:spPr/a:solidFill/a:srgbClr/a:alpha")
            soft_edge = shape._element.xpath("./p:spPr/a:effectLst/a:softEdge")
            if (shape.shape_type != 1 or shape.fill.fore_color.rgb != rgb(theme[item["color_role"]])
                or len(alpha) != 1 or alpha[0].get("val") != str(round(item["opacity"] * 100000))
                or len(soft_edge) != 1 or soft_edge[0].get("rad") != str(Pt(atmosphere_spec["blur_pt"]))):
                raise RuntimeError(f"第 {n} 页弥散形状的主题色、透明度或柔边参数异常")
        header_spec = layout["tech_content_header"] if tech_header else layout["content_header"]
        titles = [s for s in slide.shapes if s.name == "brand:content-title"]
        rules = [s for s in slide.shapes if s.name == "brand:content-rule"]
        if len(titles) != 1 or len(rules) != (0 if tech_header else 1):
            raise RuntimeError(f"第 {n} 页缺少统一正文页眉")
        if not tech_header and abs(titles[0].left - rules[0].left) > 1000:
            raise RuntimeError(f"第 {n} 页标题与分隔线左边缘未对齐")
        if titles[0].text != pages[n-1]["title"]:
            raise RuntimeError(f"第 {n} 页标题未使用统一页眉")
        expected_boxes = [(titles[0], header_spec["title_box_inches"])]
        if not tech_header:
            expected_boxes.append((rules[0], header_spec["rule_inches"]))
        if len(logos) == 1:
            expected_boxes.append((logos[0], header_spec["logo_box_inches"]))
        for shape, expected in expected_boxes:
            actual = (shape.left, shape.top, shape.width, shape.height)
            if any(abs(value - Inches(target)) > 1000 for value, target in zip(actual, expected)):
                raise RuntimeError(f"第 {n} 页统一页眉尺寸或位置偏移：{shape.name}")
        title_font = titles[0].text_frame.paragraphs[0].font
        expected_title_color = theme["neutral"]["white"] if tech_header else theme[header_spec["title_color_role"]]
        if (title_font.size != Pt(header_spec["title_size_pt"])
            or title_font.color.rgb != rgb(expected_title_color)
            or (not tech_header and rules[0].line.color.rgb != rgb(theme["primary"]))):
            raise RuntimeError(f"第 {n} 页统一页眉字体或颜色偏移")
        text_shapes = [s for s in slide.shapes if s.has_text_frame and s.text.strip()]
        if len(logos) != 1 or not text_shapes:
            raise RuntimeError(f"第 {n} 页 Logo 或可编辑文本检查失败")
        if any(ref.get("idx") != "0" for shape in slide.shapes
               for ref in shape._element.xpath(".//a:effectRef")):
            raise RuntimeError(f"第 {n} 页仍有主题效果引用")
        if any(shape._element.xpath(".//a:outerShdw | .//a:innerShdw | .//a:prstShdw")
               for shape in slide.shapes):
            raise RuntimeError(f"第 {n} 页仍有阴影效果")
        page_type = fallback_type(pages[n-1])
        checks.append({"page": n, "type": page_type,
                       "variant": resolved_variant(pages[n-1], page_type) if page_type in {"bullets", "cards", "process", "priority_grid", "milestone_timeline", "metrics", "comparison", "data_table", "image_case"} else None,
                       "image_source_path": str(pages[n-1]["image_path"]) if page_type == "image_case" else None,
                       "logo_count": len(logos), "atmosphere_shapes": len(atmosphere),
                       "editable_text_shapes": len(text_shapes)})
    return {"schema_version": "1.0", "mode": "skill_offline_brand",
            "status": "draft_pending_review", "theme": theme_name,
            "brand_profile": "brand-baseline", "layout_profile": layout["id"],
            "shadow_policy": "none",
            "palette_policy": "brand_variables_only",
            "auto_added": auto_added,
            "library_used": False, "slide_count": len(checks), "slides": checks,
            "manual_review_required": ["PowerPoint 实际文字边界和视觉节奏", "业务事实和图片来源", "品牌规范确认"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True, help="逐页内容与布局计划 JSON")
    ap.add_argument("--out", type=Path, required=True, help="输出 PPTX")
    ap.add_argument("--report", type=Path, help="审计报告 JSON；默认与 PPTX 同名")
    ap.add_argument("--theme", choices=("blue", "red", "deep-blue-tech"), help="覆盖输入计划中的主题")
    args = ap.parse_args()
    report = args.report or args.out.with_suffix(".audit.json")
    for target in (args.out, report):
        if target.exists():
            ap.error(f"输出已存在：{target}")
    try:
        plan = read_json(args.input)
        if args.theme:
            plan["theme"] = args.theme
        result = render(plan, args.out)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"pptx": str(args.out), "report": str(report),
                          "slides": result["slide_count"], "theme": result["theme"]}, ensure_ascii=False))
    except (KeyError, ValueError, FileNotFoundError, RuntimeError) as exc:
        ap.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()

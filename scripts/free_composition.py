"""Validated, model-authored body geometry using only the locked brand tokens."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches


COLOR_ROLES = {"canvas", "surface", "text", "muted", "primary", "secondary",
               "tertiary", "soft", "border", "neutral.black", "neutral.white",
               "neutral.light_gray", "neutral.mid_gray", "neutral.dark_gray",
               "neutral.on_dark_muted"}
KINDS = {"text", "rect", "ellipse", "line", "image"}


def _role(theme: dict, name: str) -> str:
    if name not in COLOR_ROLES:
        raise ValueError(f"自由编排使用了未登记的颜色角色：{name}")
    if name.startswith("neutral."):
        return theme["neutral"][name.split(".", 1)[1]]
    return theme[name]


def _num(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"自由编排 {label} 必须是有限数值")
    return float(value)


def _box(element: dict, n: int):
    x, y, w, h = (_num(element.get(key), f"元素 {n} 的 {key}") for key in ("x", "y", "w", "h"))
    if x < 0.65 or y < 1.32 or w < 0.04 or h < 0.02 or x + w > 12.70 or y + h > 6.90:
        raise ValueError(f"自由编排元素 {n} 超出正文安全区域")
    return x, y, w, h


def validate_free_layout(page: dict, theme: dict, typography: dict):
    layout = page.get("free_layout")
    if not isinstance(layout, dict) or not isinstance(layout.get("elements"), list):
        raise ValueError("自由编排需要 free_layout.elements 数组")
    elements = layout["elements"]
    if not 2 <= len(elements) <= 30:
        raise ValueError("自由编排需包含 2–30 个元素")
    if not isinstance(layout.get("rationale"), str) or not layout["rationale"].strip():
        raise ValueError("自由编排需要记录排版理由 rationale")
    text_boxes = []
    for n, element in enumerate(elements, 1):
        if not isinstance(element, dict) or element.get("kind") not in KINDS:
            raise ValueError(f"自由编排元素 {n} 类型不受支持")
        kind = element["kind"]
        x, y, w, h = _box(element, n)
        for key in ("color_role", "border_role"):
            if key in element:
                _role(theme, element[key])
        if kind == "text":
            value = element.get("text")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"自由编排文本元素 {n} 缺少内容")
            if len(value) > 300:
                raise ValueError(f"自由编排文本元素 {n} 超出 300 字")
            size = _num(element.get("size_pt", typography["body_pt"]), f"元素 {n} 字号")
            if not 14 <= size <= 32:
                raise ValueError(f"自由编排文本元素 {n} 字号超出 14–32 pt")
            if element.get("font_role", "body") not in {"body", "heading", "latin_numeric"}:
                raise ValueError(f"自由编排文本元素 {n} 字体角色不受支持")
            if element.get("align", "left") not in {"left", "center", "right"}:
                raise ValueError(f"自由编排文本元素 {n} 对齐方式不受支持")
            # Conservative Chinese-width estimate; long copy must be split before rendering.
            lines = value.split("\n")
            chars_per_line = max(1, int(w * 72 / (size * 1.05)))
            estimated_lines = sum(max(1, math.ceil(len(line) / chars_per_line)) for line in lines)
            if estimated_lines * size * 1.35 / 72 > h:
                raise ValueError(f"自由编排文本元素 {n} 预计溢出；请扩框、精简或拆页")
            text_boxes.append((n, x, y, w, h))
        elif kind == "image":
            source = element.get("source_path")
            if not isinstance(source, str) or not source.strip() or not Path(source).is_file():
                raise ValueError(f"自由编排图片元素 {n} 缺少存在的来源文件")
            if Path(source).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                raise ValueError(f"自由编排图片元素 {n} 仅接受 PNG/JPEG 来源")
            with Image.open(source) as image:
                image.verify()
        elif kind == "line":
            if not 0.01 <= h <= 0.12:
                raise ValueError(f"自由编排线条元素 {n} 高度超出范围")
        if kind != "image" and "color_role" not in element:
            raise ValueError(f"自由编排元素 {n} 缺少颜色角色")
    if not text_boxes:
        raise ValueError("自由编排至少需要一个可编辑正文文本")
    for i, a in enumerate(text_boxes):
        for b in text_boxes[i + 1:]:
            overlap_w = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
            overlap_h = min(a[2] + a[4], b[2] + b[4]) - max(a[2], b[2])
            if overlap_w > 0.03 and overlap_h > 0.03:
                raise ValueError(f"自由编排文本元素 {a[0]} 与 {b[0]} 重叠")
    return layout


def render_free_page(pres, page, index, profile, layout, theme, helpers):
    base_slide, rectangle, text_box, color = helpers
    spec = validate_free_layout(page, theme, profile["typography"])
    slide = base_slide(pres, profile, layout, theme, index, header=page["title"])
    # Draw backgrounds first; all editable text stays above decorative shapes.
    for element in spec["elements"]:
        kind = element["kind"]
        if kind == "text":
            continue
        x, y, w, h = (element[key] for key in ("x", "y", "w", "h"))
        if kind in {"rect", "line"}:
            rectangle(slide, x, y, w, h, _role(theme, element["color_role"]),
                      _role(theme, element["border_role"]) if element.get("border_role") else None,
                      rounded=bool(element.get("rounded", False)) if kind == "rect" else False)
        elif kind == "ellipse":
            shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
            color(shape, _role(theme, element["color_role"]),
                  _role(theme, element["border_role"]) if element.get("border_role") else None)
        elif kind == "image":
            source = Path(element["source_path"]).resolve()
            with Image.open(source) as image:
                ratio = image.width / image.height
            draw_w, draw_h = (min(w, h * ratio), min(h, w / ratio))
            slide.shapes.add_picture(str(source), Inches(x + (w - draw_w) / 2),
                                     Inches(y + (h - draw_h) / 2),
                                     width=Inches(draw_w), height=Inches(draw_h))
    for element in spec["elements"]:
        if element["kind"] != "text":
            continue
        x, y, w, h = (element[key] for key in ("x", "y", "w", "h"))
        role = element.get("font_role", "body")
        text_box(slide, element["text"], x, y, w, h,
                 element.get("size_pt", profile["typography"]["body_pt"]),
                 _role(theme, element["color_role"]), profile["typography"][role],
                 bold=bool(element.get("bold", False)),
                 align={"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                        "right": PP_ALIGN.RIGHT}[element.get("align", "left")],
                 valign=MSO_ANCHOR.TOP)
    return slide

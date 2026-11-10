"""Append the 85-page deep-blue technology style to the existing knowledge base.

Keeps original component IDs and source files untouched. The import is repeatable:
existing tech records are replaced by the same source-page IDs, never duplicated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from shutil import copy2
import subprocess
import sys

from lxml import etree
from pptx import Presentation

VERSION = "1.0.0-draft"
STYLE = "deep-blue-tech"
PREFIX = "tech-"
SOURCE_NAME = "tech"
EXPECTED_PAGES = 85
THEME = {
    "dk1": "000000", "lt1": "FFFFFF", "dk2": "44546A", "lt2": "E7E6E6",
    "accent1": "0F96FF", "accent2": "70D9FF", "accent3": "0FFFE8",
    "accent4": "026DCE", "accent5": "E25B2F", "accent6": "70AD47",
}
COVER = {
    1: ("tech-ai", "high", "center-right", ["AI", "digital", "crystal"]),
    2: ("tech-launch", "high", "center", ["launch", "neon", "geometric"]),
    3: ("future-landscape", "medium-high", "upper-center", ["vision", "landscape"]),
    4: ("tech-infrastructure", "high", "center", ["compute", "light-trail"]),
    5: ("speaker-intro", "medium-high", "upper-center", ["speaker", "stage"]),
}
CLOSING = {
    82: ("orbit-ring", "medium", ["vision", "calm"]),
    83: ("tech-stage", "high", ["launch", "stage"]),
    84: ("minimal-tech", "medium", ["minimal", "line"]),
    85: ("ribbon-light", "medium-high", ["stage", "light-trail"]),
}
COUNT_CANDIDATES = {
    9: (6, [2, 3, 4, 5, 6], "grid-3x2"),
    49: (6, [2, 3, 4, 5, 6], "grid-3x2"),
    69: (6, [2, 3, 4, 5, 6], "schedule-rows"),
    51: (6, [2, 3, 4, 5, 6], "six-pillars"),
    6: (5, [3, 4, 5], "directory-columns"),
    38: (4, [2, 3, 4], "process-columns"),
    54: (4, [2, 3, 4], "grid-2x2"),
    64: (5, [3, 4, 5], "timeline-straight"),
}
RELATIONS = {
    "navigation": {6, 7, 8, 9, 10},
    "section": {11, 12, 13, 14, 15},
    "process": {21, 28, 31, 32, 36, 38, 45, 49, 50, 51, 54, 56},
    "cycle": {42, 44, 46, 58, 81},
    "timeline": {63, 64, 65, 66},
    "comparison": {26, 27, 29, 40},
    "hierarchy": {16, 17, 18, 22, 30, 52, 57, 59, 60, 61, 62, 77, 78, 79, 80},
    "metrics": {53, 68, 73, 74, 75, 76},
    "schedule": {69},
}
MOTION_A = {6, 7, 8, 9, 10, 21, 22, 28, 31, 32, 36, 38, 39, 41, 42, 44,
            45, 46, 49, 50, 51, 53, 54, 56, 57, 58, 61, 62, 63, 64, 65, 66, 69}
MOTION_B = set(range(1, 6)) | set(range(11, 16)) | {16, 17, 18, 19, 20, 25, 29,
            30, 67, 68, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85}


def dump(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path):
    h = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_with_path(shapes, ancestors=()):
    for shape in shapes:
        yield shape, ancestors
        if shape.shape_type == 6:
            yield from walk_with_path(shape.shapes, ancestors + (shape.shape_id,))


def descendants(group):
    ids = []
    for shape, _ in walk_with_path(group.shapes):
        ids.append(shape.shape_id)
    return ids


def page_role(page):
    if page <= 5: return "cover"
    if page <= 10: return "directory"
    if page <= 15: return "section"
    if page >= 82: return "closing"
    if page in (67, 68, 70, 71, 72, 73, 74, 75, 76): return "data-chart"
    if page == 69: return "schedule"
    return "content"


def relation(page):
    if page <= 5: return "visual-story"
    if page >= 82: return "closing-message"
    if page in (67, 70, 71, 72, 73, 74, 75, 76): return "data-chart"
    for name, pages in RELATIONS.items():
        if page in pages: return name
    return "parallel-points"


def entry_id(page):
    return f"{page_role(page)}-tech-{page:03d}"


def typography_role(shape, page):
    text = shape.text.strip()
    if not re.search(r"[\u3400-\u9fff]", text): return "latin_numeric"
    sizes = [r.font.size.pt for p in shape.text_frame.paragraphs for r in p.runs if r.font.size]
    top = shape.top / 6858000
    if page <= 5 or page >= 82: return "chinese_display" if max(sizes or [0]) >= 24 else "chinese_body"
    if max(sizes or [0]) >= 24 or (top < .2 and len(text) <= 24): return "chinese_heading"
    return "chinese_body"


def picture_hash(shape):
    try: return sha256(shape.image.blob).hexdigest()
    except Exception: return None


def inspect_page(slide, page, logo_hash):
    fields = []
    objects = {"charts": [], "tables": [], "images": []}
    tree = []
    for z, (shape, path) in enumerate(walk_with_path(slide.shapes)):
        shape_data = {
            "shape_id": shape.shape_id, "shape_name": shape.name,
            "shape_type": int(shape.shape_type), "group_path": list(path),
            "z_order_recursive": z,
            "local_bounds_emu": [shape.left, shape.top, shape.width, shape.height],
        }
        if shape.has_text_frame and shape.text.strip():
            text = shape.text.strip()
            font_role = typography_role(shape, page)
            fields.append({
                "field": f"text_{shape.shape_id}", "shape_id": shape.shape_id,
                "shape_name": shape.name, "type": "text", "group_path": list(path),
                "source_text": text, "source_sample_chars": len(text),
                "max_chars": max(24, int(len(text) * 1.5)),
                "typography_role": font_role, "semantic_role": "provisional",
                "bounds_emu_local": shape_data["local_bounds_emu"],
            })
            shape_data["text_preview"] = text[:80]
            shape_data["typography_role"] = font_role
        if shape.shape_type == 13:
            image_hash = picture_hash(shape)
            image_role = "brand_logo_locked" if image_hash == logo_hash else (
                "cover_visual_layer" if page <= 5 else "source_media_unclassified")
            objects["images"].append({
                "shape_id": shape.shape_id, "shape_name": shape.name,
                "sha256": image_hash, "semantic_role": image_role,
                "group_path": list(path), "bounds_emu_local": shape_data["local_bounds_emu"],
            })
            shape_data["image_sha256"] = image_hash
            shape_data["semantic_role"] = image_role
        if shape.has_chart:
            objects["charts"].append({"shape_id": shape.shape_id, "shape_name": shape.name,
                                      "group_path": list(path), "categories_max": 12, "series_max": 5})
        if shape.has_table:
            objects["tables"].append({"shape_id": shape.shape_id, "shape_name": shape.name,
                                      "rows": len(shape.table.rows), "columns": len(shape.table.columns)})
        tree.append(shape_data)
    return fields, objects, tree


def item_group_candidates(slide, page, slide_width, slide_height):
    result = {"status": "provisional_requires_manual_object_review", "source_count": None,
              "target_counts": [], "units": [], "shared_shape_ids": []}
    if page not in COUNT_CANDIDATES: return result
    source_count, target_counts, geometry = COUNT_CANDIDATES[page]
    result.update(source_count=source_count, target_counts=target_counts, geometry_family=geometry)
    if page in (9, 49):
        rows = [s for s in slide.shapes if s.shape_type == 6 and
                s.width > slide_width * .7 and .2 < s.top / slide_height < .8]
        rows.sort(key=lambda s: s.top)
        for row in rows:
            children = [s for s in row.shapes if s.shape_type == 6]
            children.sort(key=lambda s: s.left)
            for child in children:
                result["units"].append({"root_shape_id": child.shape_id,
                                         "source_shape_ids": [child.shape_id] + descendants(child),
                                         "parent_group_id": row.shape_id})
        result["shared_shape_ids"] = [s.shape_id for s in slide.shapes if s.shape_type != 13 and
                                      s.shape_id not in {x["parent_group_id"] for x in result["units"]}]
    elif page == 69:
        backgrounds = [s for s in slide.shapes if s.shape_type == 1 and
                       s.width > slide_width * .7 and .3 <= s.top / slide_height < .9]
        backgrounds.sort(key=lambda s: s.top)
        background_ids = {s.shape_id for s in backgrounds}
        for bg in backgrounds:
            y0, y1 = bg.top, bg.top + bg.height
            related = [s.shape_id for s in slide.shapes if s.shape_id not in background_ids
                       and s.height < bg.height * 2 and y0 <= s.top + s.height // 2 < y1]
            result["units"].append({"root_shape_id": bg.shape_id,
                                     "source_shape_ids": [bg.shape_id] + related})
    elif page == 51:
        pillars = [s for s in slide.shapes if s.shape_type == 5 and
                   .1 < s.width / slide_width < .2 and .2 < s.top / slide_height < .4
                   and s.height / slide_height > .4]
        pillars.sort(key=lambda s: s.left)
        shared = {280, 293, 276, 277, 329, 21, 3}
        for pillar in pillars:
            center = pillar.left + pillar.width / 2
            related = [s.shape_id for s in slide.shapes if s.shape_id not in shared
                       and s.shape_id != pillar.shape_id and s.width / slide_width <= .22
                       and abs((s.left + s.width / 2) - center) / slide_width < .075
                       and .28 < s.top / slide_height < .9]
            result["units"].append({"root_shape_id": pillar.shape_id,
                                     "source_shape_ids": [pillar.shape_id] + related})
        result["shared_shape_ids"] = sorted(shared)
    result["auto_grouped_count"] = len(result["units"])
    return result


def ensure_previews(source: Path, destination: Path, previous_hash: str | None, current_hash: str):
    expected = [destination / f"P{n:03d}.png" for n in range(1, EXPECTED_PAGES + 1)]
    if previous_hash == current_hash and all(p.is_file() for p in expected): return
    script = Path(__file__).with_name("export_source_previews.ps1")
    result = subprocess.run(["pwsh", "-NoProfile", "-File", str(script),
                             "-InputPath", str(source), "-OutputDir", str(destination)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode: raise RuntimeError("科技风预览导出失败：" + result.stderr.strip())
    if not all(p.is_file() for p in expected): raise RuntimeError("科技风 85 页预览不完整")


def integrate(root: Path, source: Path, update_manifest=True):
    root = root.resolve(); source = source.resolve()
    if not source.is_file(): raise FileNotFoundError(source)
    deck = Presentation(source)
    if len(deck.slides) != EXPECTED_PAGES: raise ValueError("科技风来源必须为 85 页")
    if abs(deck.slide_width / deck.slide_height - 16 / 9) > .001:
        raise ValueError("科技风来源不是 16:9")
    old_source = root / "sources" / "tech.pptx"
    old_hash = digest(old_source) if old_source.is_file() else None
    source_hash = digest(source)
    previews = root / "source-previews" / "tech"
    ensure_previews(source, previews, old_hash, source_hash)
    old_source.parent.mkdir(parents=True, exist_ok=True)
    if old_source != source: copy2(source, old_source)
    catalog_path, page_path = root / "catalog.json", root / "source-pages.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    source_pages = json.loads(page_path.read_text(encoding="utf-8"))
    catalog["layouts"] = [e for e in catalog["layouts"] if e.get("style_family") != STYLE]
    source_pages = [e for e in source_pages if e.get("source") != SOURCE_NAME]
    frequency = Counter(picture_hash(s) for slide in deck.slides for s, _ in walk_with_path(slide.shapes)
                        if s.shape_type == 13)
    logo_hash, logo_count = frequency.most_common(1)[0]
    if logo_count != 71: raise ValueError(f"科技风品牌图预期出现 71 次，实际 {logo_count}")
    entries = []
    for page, slide in enumerate(deck.slides, 1):
        eid = entry_id(page); role = page_role(page)
        fields, objects, tree = inspect_page(slide, page, logo_hash)
        logo_shapes = [x for x in objects["images"] if x["semantic_role"] == "brand_logo_locked"]
        if len(logo_shapes) > 1: raise ValueError(f"P{page:03d} 来源 Logo 重复")
        directory = root / "layouts" / eid
        dump(directory / "bindings.json", {"schema_version": "1.0", "fields": fields,
                                           "objects": objects, "review": "visual index only; field semantics provisional"})
        dump(directory / "shape-tree.json", {"source_page": page, "recursive_shapes": tree,
                                            "all_bounds_are_group_local": True})
        groups = item_group_candidates(slide, page, deck.slide_width, deck.slide_height)
        dump(directory / "item-groups.json", groups)
        rules = {"cardinality_mode": "fixed_until_validated", "supported_counts": [],
                 "source_count": groups["source_count"], "candidate_counts": groups["target_counts"],
                 "reflow_status": "not_implemented", "grouping_status": groups["status"]}
        dump(directory / "layout_rules.json", rules)
        suitability = "A" if page in MOTION_A else "B" if page in MOTION_B else "C"
        dump(directory / "motion.json", {"source_animation": False, "source_transition": False,
                                         "motion_suitability": suitability, "status": "static",
                                         "eligible_groups": [], "brand_static": True,
                                         "final_state_complete": True})
        all_text = [f["source_text"] for f in fields]
        (directory / "spec.md").write_text(
            f"# {eid}\n\n来源：深蓝科技风 P{page:03d}；角色：{role}；关系初标：{relation(page)}。\n"
            f"\n递归对象：{len(tree)}；文本字段：{len(fields)}；图片：{len(objects['images'])}；"
            f"图表：{len(objects['charts'])}；源 Logo：{'有' if logo_shapes else '无'}。\n"
            f"\n原稿主题示例：{' / '.join(all_text[:3])[:150]}。源稿示例事实不进入新项目。"
            f"\n\n项数／字段／动效均待人工复核；原生 PPTX 可编辑结构保留。\n", encoding="utf-8")
        entry = {"id": eid, "version": VERSION, "collection": "new-template-covers" if role == "cover" else
                 "new-template-closing" if role == "closing" else "new-template-content",
                 "style_family": STYLE, "color_family": "deep-blue", "role": role,
                 "information_relation": relation(page), "classification_status": "visual_initial",
                 "family_id": f"tech-{relation(page)}-{page:03d}", "source": "sources/tech.pptx",
                 "example": "sources/tech.pptx", "source_page": page,
                 "source_mapping": {"tech": page}, "bindings": f"layouts/{eid}/bindings.json",
                 "spec": f"layouts/{eid}/spec.md", "layout_rules": f"layouts/{eid}/layout_rules.json",
                 "motion": f"layouts/{eid}/motion.json", "shape_tree": f"layouts/{eid}/shape-tree.json",
                 "item_groups": f"layouts/{eid}/item-groups.json",
                 "preview": f"source-previews/tech/P{page:03d}.png", "themes": [STYLE],
                 "status": "draft_pending_review", "capacity": {"body_slots": len(fields),
                 "item_title_slots": groups["source_count"] or 0, "cell_max_chars": 20},
                 "shape_count": len(tree), "media_status": "unreviewed",
                 "html_support": "not_implemented", "motion_support": "source_static",
                 "motion_suitability": suitability, "cardinality_status": "not_implemented",
                 "brand_policy": "default_logo; source asset locked"}
        if logo_shapes:
            entry.update(source_logo_present=True, source_logo_shape_id=logo_shapes[0]["shape_id"],
                         source_logo_asset_sha256=logo_hash)
        else: entry["source_logo_present"] = False
        if role == "cover":
            style, impact, area, tags = COVER[page]
            layers = []
            for position, (shape, path) in enumerate(walk_with_path(slide.shapes)):
                if shape.shape_type != 13 or picture_hash(shape) == logo_hash: continue
                file = root / "cover-assets" / "tech" / f"P{page:03d}-layer{len(layers)+1:02d}.{shape.image.ext}"
                file.parent.mkdir(parents=True, exist_ok=True); file.write_bytes(shape.image.blob)
                layers.append({"shape_id": shape.shape_id, "source_group_path": list(path),
                               "z_order_recursive": position, "image": file.relative_to(root).as_posix(),
                               "sha256": digest(file), "bounds_emu_local": [shape.left, shape.top, shape.width, shape.height],
                               "full_bleed": shape.width >= deck.slide_width * .95 and shape.height >= deck.slide_height * .95})
            if not any(layer["full_bleed"] for layer in layers):
                raise ValueError(f"P{page:03d} 没有可定位的封面底图")
            primary = next(layer for layer in layers if layer["full_bleed"])
            entry.update(style=style, visual_impact=impact, title_area_hint=area,
                         subject_tags=tags, background_image=primary["image"],
                         background_layers=layers, cover_match_status="original_only_pending_review",
                         stock_code_default=None, slogan_locked=None,
                         composite_required=len(layers) > 1)
            dump(root / "cover-assets" / "tech" / f"P{page:03d}-layers.json",
                 {"source_page": page, "layers": layers, "source_logo_shape_id": entry.get("source_logo_shape_id"),
                  "status": "visual_review_required"})
        if role == "closing":
            style, impact, tags = CLOSING[page]
            entry.update(style=style, visual_impact=impact, subject_tags=tags,
                         closing_match_status="original_plus_logo_pending_review")
            dump(root / "closing-assets" / "tech" / f"P{page:03d}-composition.json",
                 {"source_page": page, "editable_shape_ids": [x["shape_id"] for x in tree],
                  "picture_count": len(objects["images"]), "default_logo": True,
                  "logo_anchor_status": "pending_visual_review", "status": "visual_review_required"})
        entries.append(entry)
        source_pages.append({"source": SOURCE_NAME, "page": page, "component_id": eid,
                             "variant": STYLE, "source_pptx": "sources/tech.pptx",
                             "extraction_status": "indexed"})
    catalog["layouts"].extend(entries)
    catalog["physical_pages"] = len(source_pages)
    catalog["component_entries"] = len(catalog["layouts"])
    dump(catalog_path, catalog); dump(page_path, source_pages)
    source_manifest_path = root / "source-manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_manifest["sources"][SOURCE_NAME] = {"filename": source.name,
                                                 "sha256": source_hash, "page_count": EXPECTED_PAGES,
                                                 "style_family": STYLE}
    dump(source_manifest_path, source_manifest)
    dump(root / "themes" / "new-template-deep-blue-tech.json", {
        "id": STYLE, "status": "provisional", "source_theme": "ppt/theme/theme1.xml",
        "color_slots": THEME,
        "semantic_roles": {"brand_primary": "accent1", "tech_cyan": "accent2",
                           "tech_teal": "accent3", "tech_blue": "accent4",
                           "canvas_deep": "requires_background_media_audit"},
        "logo_color_policy": "locked; never recolor logo",
        "gradients_svg_charts": "per-object mapping pending"})
    dump(root / "typography" / "deep-blue-tech.json", {
        "id": STYLE, "status": "provisional_requires_render_review",
        "source_theme_major": {"latin": "OPPOSans R", "east_asian": "锐字锐线怒放黑简1.0"},
        "source_theme_minor": {"latin": "OPPOSans R", "east_asian": "OPPOSans R"},
        "roles": {"chinese_display": "Microsoft YaHei", "chinese_heading": "Microsoft YaHei",
                  "chinese_body": "Microsoft YaHei", "latin_numeric": "Arial"},
        "rule": "preserve source font size and line spacing; inspect line wraps after replacement"})
    readme = root / "README.md"
    line = "\n新增 03 深蓝科技风 85 页，使用同一知识库内独立 `style_family=deep-blue-tech`；5 封面与 4 封底独立索引。当前仅完成来源和结构初拆，项数、动效、HTML 和换色仍待逐页验收。\n"
    content = readme.read_text(encoding="utf-8")
    if "新增 03 深蓝科技风 85 页" not in content: readme.write_text(content.rstrip() + "\n" + line, encoding="utf-8")
    prototype_line = "P09 六宫格目录、P49 六项清单、P69 形状排期已各有 2–6 项可编辑 PPTX 与逐项淡入内部原型；15 档均未完成真实放映和正式验收，不进入常规选择。P51 仍仅完成六项字段归属。\n"
    content = readme.read_text(encoding="utf-8")
    if "P09 六宫格目录、P49 六项清单" not in content:
        readme.write_text(content.rstrip() + "\n\n" + prototype_line, encoding="utf-8")
    pillars_line = "P51 六立柱页已补 2–6 项可编辑 PPTX 与逐项淡入内部原型，中心数字按实际项数生成；真实放映和长文压力仍待验收。\n"
    content = readme.read_text(encoding="utf-8")
    if "P51 六立柱页已补" not in content:
        readme.write_text(content.rstrip() + "\n\n" + pillars_line, encoding="utf-8")
    from build_tech_gallery import build as build_tech_gallery
    build_tech_gallery(root)
    from curate_tech_repetition import curate as curate_tech_repetition
    curate_tech_repetition(root, update_manifest=False)
    from curate_tech_semantics import curate as curate_tech_semantics
    curate_tech_semantics(root, update_manifest=False)
    from curate_tech_process import curate as curate_tech_process
    curate_tech_process(root, update_manifest=False)
    from curate_tech_pptx_pool import curate as curate_tech_pptx_pool
    curate_tech_pptx_pool(root, update_manifest=False)
    from finalize_tech_pptx_pool import finalize as finalize_tech_pptx_pool
    finalize_tech_pptx_pool(root, update_manifest=False)
    from extend_tech_static_pool import extend as extend_tech_static_pool
    extend_tech_static_pool(root, update_manifest=False)
    from extend_tech_static_pool_batch3 import extend as extend_tech_static_pool_batch3
    extend_tech_static_pool_batch3(root, update_manifest=False)
    from extend_tech_static_pool_batch4 import extend as extend_tech_static_pool_batch4
    extend_tech_static_pool_batch4(root, update_manifest=False)
    from extend_tech_static_pool_batch5 import extend as extend_tech_static_pool_batch5
    extend_tech_static_pool_batch5(root, update_manifest=False)
    from extend_tech_static_pool_batch6 import extend as extend_tech_static_pool_batch6
    extend_tech_static_pool_batch6(root, update_manifest=False)
    from build_tech_color_inventory import build as build_tech_color_inventory
    build_tech_color_inventory(root, update_manifest=False)
    from build_tech_source_audit import build as build_tech_source_audit
    build_tech_source_audit(root, update_manifest=False)
    from mark_tech_html_prototype import mark as mark_tech_html_prototype
    mark_tech_html_prototype(root, update_manifest=False)
    if update_manifest:
        files = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob("*")
                 if p.is_file() and ".git" not in p.parts and p.name not in
                 ("knowledge-manifest.json", "audit-report.json", "blank.pptx", "blank-red.pptx")
                 and "source-pages" not in p.relative_to(root).parts}
        dump(root / "knowledge-manifest.json", {"schema_version": "1.0", "version": VERSION,
                                                "status": "draft_pending_review", "file_count": len(files),
                                                "files": files})
    return {"source_page_count": EXPECTED_PAGES, "tech_entries": len(entries),
            "physical_pages": len(source_pages), "component_entries": len(catalog["layouts"]),
            "source_sha256": source_hash, "source_logo_count": logo_count}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(integrate(args.library, args.source), ensure_ascii=False, indent=2))


if __name__ == "__main__": main()

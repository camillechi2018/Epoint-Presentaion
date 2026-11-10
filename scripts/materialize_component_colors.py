"""Bake a selected template page's theme colors into its editable components.

OOXML requires a theme part, so it is retained for file compatibility. Visible
slide, layout, master, and chart color references no longer depend on it.
"""
import argparse
import json
import os
import time
import posixpath
import tempfile
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as ET

from audit_theme_integrity import A, P, related, slide_parts

ROLE_NAMES = (
    "dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
    "accent4", "accent5", "accent6", "hlink", "folHlink",
)
SCHEME = f"{{{A}}}schemeClr"
RGB = f"{{{A}}}srgbClr"


def selected_parts(z):
    slides = slide_parts(z)
    if len(slides) != 1:
        raise ValueError("颜色固化只接受已提取的单页组件")
    slide = slides[0]
    layout = related(z, slide, "slideLayout")
    master = related(z, layout, "slideMaster")
    theme = related(z, master, "theme")
    return slide, layout, master, theme


def theme_values(z, theme):
    root = ET.fromstring(z.read(theme))
    scheme = root.find(f".//{{{A}}}clrScheme")
    if scheme is None:
        raise ValueError("来源主题没有颜色方案：" + theme)
    values = {}
    for role in ROLE_NAMES:
        item = scheme.find(f"{{{A}}}{role}")
        if item is None or len(item) != 1:
            raise ValueError("来源主题缺少颜色槽：" + role)
        color = item[0].get("lastClr") or item[0].get("val")
        if not color or len(color) != 6:
            raise ValueError("来源主题颜色不可固化：" + role)
        values[role] = color.upper()
    return values


def color_map(z, slide, layout, master):
    root = ET.fromstring(z.read(master))
    item = root.find(f"{{{P}}}clrMap")
    if item is None:
        raise ValueError("来源母版没有颜色映射")
    mapping = dict(item.attrib)
    # A specific slide/layout mapping takes precedence over the master map.
    for part in (layout, slide):
        root = ET.fromstring(z.read(part))
        override = root.find(f"{{{P}}}clrMapOvr/{{{A}}}overrideClrMapping")
        if override is not None:
            mapping.update(override.attrib)
    return mapping


def freeze(input_path, output_path, report_path=None, expected_source_path=None, expected_source_page=None):
    input_path = Path(input_path)
    output_path = Path(output_path)
    with ZipFile(input_path) as zin:
        slide, layout, master, theme = selected_parts(zin)
        values = theme_values(zin, theme)
        if expected_source_path is not None:
            if expected_source_page is None:
                raise ValueError("校验来源主题时必须指定来源页码")
            with ZipFile(expected_source_path) as source_zip:
                source_slides = slide_parts(source_zip)
                page_index = int(expected_source_page) - 1
                if page_index < 0 or page_index >= len(source_slides):
                    raise ValueError("来源页码超出范围")
                source_slide = source_slides[page_index]
                source_layout = related(source_zip, source_slide, "slideLayout")
                source_master = related(source_zip, source_layout, "slideMaster")
                source_theme = related(source_zip, source_master, "theme")
                expected = theme_values(source_zip, source_theme)
            changed = {role: {"source": expected[role], "component": values[role]}
                       for role in ROLE_NAMES if expected[role] != values[role]}
            if changed:
                raise ValueError("组件主题槽与知识库来源页不一致，拒绝固化：" + json.dumps(changed, ensure_ascii=False))
        mapping = color_map(zin, slide, layout, master)
        parts = {slide, layout, master}
        # Charts belong to the extracted page's package. Chart style phClr is
        # a chart-style placeholder, not a master color slot, and is reported.
        parts.update(name for name in zin.namelist()
                     if name.startswith("ppt/charts/") and name.endswith(".xml"))
        changed = {}
        unresolved = {}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".colors-", suffix=".pptx", dir=output_path.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with ZipFile(temporary, "w") as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    if info.filename in parts:
                        root = ET.fromstring(data)
                        count = 0
                        pending = 0
                        for element in root.iter(SCHEME):
                            role = element.get("val")
                            if role == "phClr":
                                pending += 1
                                continue
                            resolved = mapping.get(role, role)
                            if resolved not in values:
                                raise ValueError(f"未登记的主题色槽 {role}: {info.filename}")
                            element.tag = RGB
                            element.set("val", values[resolved])
                            count += 1
                        if count:
                            data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                            changed[info.filename] = count
                        if pending:
                            unresolved[info.filename] = pending
                    zout.writestr(info, data)
            # Windows cannot replace a ZIP that is still open for reading.
            zin.close()
            for attempt in range(6):
                try:
                    os.replace(temporary, output_path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.15 * (attempt + 1))
        finally:
            if temporary.exists():
                temporary.unlink()
    result = {"input": str(input_path), "output": str(output_path), "theme_source": theme,
              "source_colors": values, "materialized_by_part": changed,
              "remaining_chart_style_placeholders": unresolved,
              "rendering_depends_on_master_theme_slots": False,
              "chart_visual_review_required": bool(unresolved)}
    if report_path:
        Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def freeze_uniform_deck(input_path, output_path, report_path=None, role_overrides=None):
    """Freeze a free-composition deck whose slides share one color map."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    with ZipFile(input_path) as zin:
        slides = slide_parts(zin)
        if not slides:
            raise ValueError("没有可固化的页面")
        parts = set()
        common = None
        for slide in slides:
            layout = related(zin, slide, "slideLayout")
            master = related(zin, layout, "slideMaster")
            theme = related(zin, master, "theme")
            values = theme_values(zin, theme)
            mapping = color_map(zin, slide, layout, master)
            if common is None:
                common = (values, mapping)
            elif common != (values, mapping):
                raise ValueError("整稿有不同母版配色，请逐页固化")
            parts.update((slide, layout, master))
        chart_parts = {name for name in zin.namelist()
                       if name.startswith("ppt/charts/") and name.endswith(".xml")}
        parts.update(chart_parts)
        values, mapping = common
        if role_overrides:
            if any(role not in values or len(color) != 6 for role, color in role_overrides.items()):
                raise ValueError("离线主题覆盖值无效")
            values = {**values, **{role: color.upper() for role, color in role_overrides.items()}}
        changed = {}
        unresolved = {}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".colors-", suffix=".pptx", dir=output_path.parent)
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with ZipFile(temporary, "w") as zout:
                for info in zin.infolist():
                    data = zin.read(info.filename)
                    if info.filename in parts:
                        root = ET.fromstring(data)
                        count = 0
                        pending = 0
                        for element in root.iter(SCHEME):
                            role = element.get("val")
                            if role == "phClr":
                                pending += 1
                                continue
                            resolved = mapping.get(role, role)
                            if resolved not in values:
                                raise ValueError(f"未登记的主题色槽 {role}: {info.filename}")
                            element.tag = RGB
                            element.set("val", values[resolved])
                            count += 1
                        if count:
                            data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                            changed[info.filename] = count
                        if pending:
                            unresolved[info.filename] = pending
                    zout.writestr(info, data)
            zin.close()
            for attempt in range(6):
                try:
                    os.replace(temporary, output_path)
                    break
                except PermissionError:
                    if attempt == 5:
                        raise
                    time.sleep(0.15 * (attempt + 1))
        finally:
            if temporary.exists():
                temporary.unlink()
    result = {"input": str(input_path), "output": str(output_path), "slide_count": len(slides),
              "source_colors": values, "materialized_by_part": changed,
              "remaining_chart_style_placeholders": unresolved,
              "rendering_depends_on_master_theme_slots": False,
              "chart_visual_review_required": bool(unresolved)}
    if report_path:
        Path(report_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()
    result = freeze(args.input, args.output, args.report)
    print(json.dumps({"materialized": sum(result["materialized_by_part"].values()),
                      "chart_style_placeholders": sum(result["remaining_chart_style_placeholders"].values())},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

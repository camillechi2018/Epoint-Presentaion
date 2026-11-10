"""Reject arbitrary RGB colors in newly drawn slides.

Source-template components are checked against their own source, not this
palette. This audit is for the Skill's brand-based free composition.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from audit_theme_integrity import A, related, slide_parts
from audit_brand_palette_source import locked_colors

def allowed_colors(theme):
    return locked_colors(theme)


def explicit_colors(package, part):
    root = etree.fromstring(package.read(part))
    colors = Counter()
    for element in root.iter():
        if element.tag == f"{{{A}}}srgbClr":
            value = element.get("val")
        elif element.tag == f"{{{A}}}sysClr":
            value = element.get("lastClr") or element.get("val")
        else:
            continue
        if value:
            colors[value.upper()] += 1
    return colors


def audit(path, theme):
    allowed = allowed_colors(theme)
    slides = []
    with ZipFile(path) as z:
        for page, name in enumerate(slide_parts(z), 1):
            layout = related(z, name, "slideLayout")
            master = related(z, layout, "slideMaster")
            parts = (name, layout, master)
            colors = Counter()
            for part in parts:
                colors.update(explicit_colors(z, part))
            unexpected = {color: count for color, count in colors.items() if color not in allowed}
            slides.append({"page": page, "parts": parts, "unexpected_colors": unexpected,
                           "passed": not unexpected})
        charts = {}
        for part in z.namelist():
            if part.startswith("ppt/charts/") and part.endswith(".xml"):
                colors = explicit_colors(z, part)
                unexpected = {color: count for color, count in colors.items() if color not in allowed}
                if unexpected:
                    charts[part] = unexpected
    return {"passed": all(slide["passed"] for slide in slides) and not charts,
            "theme": theme, "allowed_colors": sorted(allowed),
            "slide_count": len(slides), "slides": slides, "unexpected_chart_colors": charts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--theme", required=True, choices=("blue", "red", "deep-blue-tech"))
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = audit(args.input, args.theme)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "slide_count": result["slide_count"],
                      "unexpected_pages": [x["page"] for x in result["slides"] if not x["passed"]],
                      "unexpected_charts": list(result["unexpected_chart_colors"])}, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()

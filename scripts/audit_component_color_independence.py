"""Check that editable pages do not render from master theme color slots."""
import argparse
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

from audit_theme_integrity import A, related, slide_parts


def audit(path):
    rows = []
    chart_placeholders = 0
    unexpected_chart_theme_refs = {}
    with ZipFile(path) as z:
        for number, slide in enumerate(slide_parts(z), 1):
            layout = related(z, slide, "slideLayout")
            master = related(z, layout, "slideMaster")
            refs = Counter()
            for part in (slide, layout, master):
                root = etree.fromstring(z.read(part))
                refs.update(el.get("val") for el in root.iter(f"{{{A}}}schemeClr"))
            rows.append({"page": number, "slide": slide, "layout": layout, "master": master,
                         "remaining_master_theme_references": dict(refs), "passed": not refs})
        for name in z.namelist():
            if name.startswith("ppt/charts/") and name.endswith(".xml"):
                root = etree.fromstring(z.read(name))
                refs = Counter(el.get("val") for el in root.iter(f"{{{A}}}schemeClr"))
                chart_placeholders += refs.pop("phClr", 0)
                if refs:
                    unexpected_chart_theme_refs[name] = dict(refs)
    return {"passed": all(row["passed"] for row in rows) and not unexpected_chart_theme_refs,
            "slide_count": len(rows), "mismatch_pages": [row["page"] for row in rows if not row["passed"]],
            "chart_style_placeholders": chart_placeholders,
            "chart_visual_review_required": chart_placeholders > 0,
            "unexpected_chart_theme_references": unexpected_chart_theme_refs,
            "slides": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    result = audit(args.input)
    Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "slide_count": result["slide_count"],
                      "mismatch_pages": result["mismatch_pages"],
                      "chart_style_placeholders": result["chart_style_placeholders"]}, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 2)


if __name__ == "__main__":
    main()

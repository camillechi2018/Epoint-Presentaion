"""Verify that each assembled slide still resolves its source theme colors."""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
ROLES = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3",
         "accent4", "accent5", "accent6", "hlink", "folHlink")


def related(z, part, kind):
    folder, name = posixpath.split(part)
    rels = posixpath.join(folder, "_rels", name + ".rels")
    root = ET.fromstring(z.read(rels))
    for rel in root.findall(f"{{{REL}}}Relationship"):
        if rel.get("Type", "").endswith("/" + kind):
            target = rel.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join(folder, target))
    raise ValueError(f"{part} has no {kind} relationship")


def slide_parts(z):
    root = ET.fromstring(z.read("ppt/presentation.xml"))
    rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
    targets = {
        rel.get("Id"): rel.get("Target")
        for rel in rels.findall(f"{{{REL}}}Relationship")
    }
    result = []
    for slide in root.findall(f".//{{{P}}}sldId"):
        target = targets[slide.get(f"{{{R}}}id")]
        result.append(posixpath.normpath(posixpath.join("ppt", target)))
    return result


def theme_colors(z, slide_part):
    layout = related(z, slide_part, "slideLayout")
    master = related(z, layout, "slideMaster")
    theme = related(z, master, "theme")
    root = ET.fromstring(z.read(theme))
    scheme = root.find(f".//{{{A}}}clrScheme")
    if scheme is None:
        raise ValueError(f"{theme} has no color scheme")
    colors = {}
    for role in ROLES:
        element = scheme.find(f"{{{A}}}{role}")
        if element is None or len(element) != 1:
            raise ValueError(f"{theme} has no {role}")
        colors[role] = element[0].get("lastClr") or element[0].get("val")
    return {"theme_part": theme, "colors": colors}


def main():
    ap = argparse.ArgumentParser()
    source_group = ap.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--manifest")
    source_group.add_argument("--library")
    ap.add_argument("--input", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    if args.manifest:
        manifest_path = Path(args.manifest).resolve()
        plan = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        inputs = [Path(s["path"]) if Path(s["path"]).is_absolute() else manifest_path.parent / s["path"] for s in plan["slides"]]
    rows = []
    with ZipFile(args.input) as output:
        output_slides = slide_parts(output)
        if args.manifest and len(output_slides) != len(inputs):
            raise ValueError("assembled slide count differs from manifest")
        for index, output_slide in enumerate(output_slides, 1):
            if args.library:
                slide_root = ET.fromstring(output.read(output_slide))
                common = slide_root.find(f"{{{P}}}cSld")
                stamp = common.get("name", "") if common is not None else ""
                match = re.fullmatch(r"epoint:[^:]+:[^:]+:(sources/[^:]+\.pptx):(\d+):[0-9a-f]{40}(?::\d+)?", stamp)
                if not match:
                    raise ValueError(f"page {index} has no usable source stamp: {stamp}")
                source_path = Path(args.library) / match.group(1)
                source_index = int(match.group(2)) - 1
            else:
                source_path = inputs[index - 1]
                source_index = 0
            with ZipFile(source_path) as source:
                source_slides = slide_parts(source)
                if args.manifest and len(source_slides) != 1:
                    raise ValueError(f"source is not one slide: {source_path}")
                expected = theme_colors(source, source_slides[source_index])
            actual = theme_colors(output, output_slide)
            changed = {role: {"source": expected["colors"][role], "output": actual["colors"][role]}
                       for role in ROLES if expected["colors"][role].upper() != actual["colors"][role].upper()}
            rows.append({"page": index, "source": str(source_path), "source_theme": expected["theme_part"],
                         "output_theme": actual["theme_part"], "changed_colors": changed, "passed": not changed})
    report = {"passed": all(row["passed"] for row in rows), "slide_count": len(rows), "slides": rows}
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "slide_count": len(rows),
                      "mismatch_pages": [row["page"] for row in rows if not row["passed"]]}, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())

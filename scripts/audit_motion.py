"""Check native PowerPoint animation targets against selected motion profiles."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree


NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}


def audit(pptx: Path, manifest: Path, library: Path) -> dict:
    slides = json.loads(manifest.read_text(encoding="utf-8-sig"))["slides"]
    records = []
    with ZipFile(pptx) as package:
        names = sorted(
            (name for name in package.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"(\d+)\.xml$", name).group(1)),
        )
        if len(names) != len(slides):
            raise ValueError(f"页面数不符：PPTX={len(names)}，清单={len(slides)}")
        for page, (name, item) in enumerate(zip(names, slides), 1):
            layout = item["layout_id"]
            profile = library / "layouts" / layout / "motion.json"
            root = etree.fromstring(package.read(name))
            transitions = root.xpath('.//p:transition', namespaces=NS)
            auto_advance = any(node.get('advTm') is not None or node.get('advClick') == '0' for node in transitions)
            visual_transition = any(len(node) > 0 for node in transitions)
            actual = [int(value) for value in root.xpath(".//p:animEffect/p:cBhvr/p:tgtEl/p:spTgt/@spid", namespaces=NS)]
            clicks = len(root.xpath('.//p:cTn[@nodeType="clickEffect"]', namespaces=NS))
            if item.get('motion_profile') == 'off':
                clean = not actual and clicks == 0 and not auto_advance and not visual_transition
                records.append({"page": page, "layout_id": layout, "status": "static_passed" if clean else "failed",
                                "effects": len(actual), "clicks": clicks, "expected_effects": 0,
                                "expected_clicks": 0, "auto_advance": auto_advance,
                                "visual_transition": visual_transition})
                continue
            if profile.is_file():
                spec = json.loads(profile.read_text(encoding="utf-8-sig"))
                groups=spec.get("groups",[])
                shape_ids={int(v) for v in root.xpath('.//p:cNvPr/@id',namespaces=NS)}
                active=[g for g in groups if all(int(shape) in shape_ids for shape in g['shape_ids'])]
                partial=[g for g in groups if any(int(shape) in shape_ids for shape in g['shape_ids']) and not all(int(shape) in shape_ids for shape in g['shape_ids'])]
                expected = [shape for group in active for shape in group["shape_ids"]]
                status = "passed" if not partial and actual == expected and clicks == len(active) and not auto_advance and not visual_transition else "failed"
                if spec.get("status")=="static" and status=="passed":status="static_passed"
                records.append({"page": page, "layout_id": layout, "status": status, "effects": len(actual), "clicks": clicks, "expected_effects": len(expected), "expected_clicks": len(active), "auto_advance": auto_advance, "visual_transition": visual_transition})
            else:
                records.append({"page": page, "layout_id": layout, "status": "unprofiled" if not actual and not auto_advance and not visual_transition else "unprofiled_has_animation", "effects": len(actual), "clicks": clicks, "auto_advance": auto_advance, "visual_transition": visual_transition})
    passed = all(item["status"] in {"passed", "static_passed", "unprofiled"} for item in records)
    return {"passed": passed, "slide_count": len(records), "animated_slides": sum(item["status"] == "passed" for item in records), "effect_count": sum(item["effects"] for item in records), "slides": records, "playback_review_required": any(item["effects"] for item in records)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.input, args.manifest, args.library)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "slide_count", "animated_slides", "effect_count")}, ensure_ascii=False))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

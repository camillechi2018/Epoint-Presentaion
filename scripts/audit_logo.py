"""Verify that independent Logo pictures remain visible to ordinary PPTX viewers."""
from __future__ import annotations

import argparse
import io
import json
import posixpath
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from PIL import Image

REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def audit(path: Path, require_every_slide: bool = False, theme: str | None = None) -> dict:
    issues = []
    records = []
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        slide_names = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"slide(\d+)\.xml", name).group(1)),
        )
        for number, slide_name in enumerate(slide_names, 1):
            slide = etree.fromstring(archive.read(slide_name))
            relation_name = posixpath.join("ppt/slides/_rels", posixpath.basename(slide_name) + ".rels")
            relations = {}
            if relation_name in names:
                relation_root = etree.fromstring(archive.read(relation_name))
                relations = {node.get("Id"): node.get("Target") for node in relation_root}
            def inspect_red_logo(picture, label):
                if theme != "red":
                    return
                blips = picture.xpath('./*[local-name()="blipFill"]/*[local-name()="blip"]')
                embed = blips[0].get("{" + REL + "}embed") if blips else None
                target = relations.get(embed)
                media = posixpath.normpath(posixpath.join("ppt/slides", target)) if target else None
                if not media or media not in names:
                    issues.append({"slide": number, "code": "red_logo_image_missing", "shape": label})
                    return
                with Image.open(io.BytesIO(archive.read(media))) as image:
                    pixels = image.convert("RGBA")
                    visible = [pixel for pixel in pixels.getdata() if pixel[3] >= 64]
                if visible and sum(max(pixel[:3]) - min(pixel[:3]) > 12 for pixel in visible) / len(visible) > .005:
                    issues.append({"slide": number, "code": "red_logo_not_monochrome", "shape": label, "media": media})
            logo_count = 0
            source_groups=slide.xpath('//*[local-name()="grpSp"]/*[local-name()="nvGrpSpPr"]/*[local-name()="cNvPr"][@name="brand:logo:source"]')
            for group in source_groups:
                parent=group.getparent().getparent()
                text=''.join(parent.xpath('.//*[local-name()="t"]/text()'))
                if '688232' not in text:
                    issues.append({"slide":number,"code":"source_logo_group_missing_stock_code"})
                else:
                    logo_count += 1
                    records.append({"slide":number,"shape":"brand:logo:source","media":"native_group"})
                    for picture in parent.xpath('.//*[local-name()="pic"]'):
                        inspect_red_logo(picture, "brand:logo:source")
            for picture in slide.xpath('//*[local-name()="pic"]'):
                props = picture.xpath('./*[local-name()="nvPicPr"]/*[local-name()="cNvPr"]')
                if not props or not props[0].get("name", "").startswith("brand:logo:"):
                    continue
                if props[0].get("name") == "brand:logo:plate":
                    continue
                logo_count += 1
                # Source logos inside a group use group-local coordinates. A newly
                # inserted logo is top-level and must have a visible slide size.
                if not picture.xpath('ancestor::*[local-name()="grpSp"]'):
                    ext = picture.xpath('./*[local-name()="spPr"]/*[local-name()="xfrm"]/*[local-name()="ext"]')
                    if ext and (int(ext[0].get("cx", "0")) < 457200 or int(ext[0].get("cy", "0")) < 91440):
                        issues.append({"slide": number, "code": "logo_too_small", "shape": props[0].get("name")})
                blips = picture.xpath('./*[local-name()="blipFill"]/*[local-name()="blip"]')
                embed = blips[0].get("{" + REL + "}embed") if blips else None
                target = relations.get(embed)
                media = posixpath.normpath(posixpath.join("ppt/slides", target)) if target else None
                if not embed or not media or media not in names:
                    issues.append({"slide": number, "code": "missing_primary_logo_image", "shape": props[0].get("name")})
                    continue
                try:
                    with Image.open(io.BytesIO(archive.read(media))) as image:
                        image.verify()
                except Exception:
                    issues.append({"slide": number, "code": "invalid_primary_logo_image", "media": media})
                    continue
                records.append({"slide": number, "shape": props[0].get("name"), "media": media})
                inspect_red_logo(picture, props[0].get("name"))
            if require_every_slide and logo_count != 1:
                issues.append({"slide": number, "code": "logo_count", "count": logo_count})
        bad_member = archive.testzip()
        if bad_member:
            issues.append({"code": "invalid_zip_member", "member": bad_member})
    return {"input": str(path), "theme": theme, "slide_count": len(slide_names), "logos_with_primary_image": len(records), "passed": not issues, "issues": issues, "records": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-every-slide", action="store_true")
    parser.add_argument("--theme", choices=("blue", "red", "deep-blue-tech"))
    args = parser.parse_args()
    report = audit(args.input, args.require_every_slide, args.theme)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("slide_count", "logos_with_primary_image", "passed", "issues")}, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

"""Reject mixed typefaces in editable slide text after final assembly."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from font_profile import resolve


A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
NS = {'a': A}
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
PRIVATE_USE = re.compile(r'^[\ue000-\uf8ff\U000f0000-\U0010ffff]+$')
def audit(path: Path, profile=None) -> dict:
    selected = resolve(profile)
    expected_fonts = {'latin': selected['latin'], 'ea': selected['east_asian']}
    violations = []
    checked_runs = 0
    with ZipFile(path) as archive:
        slides = sorted(
            (name for name in archive.namelist()
             if re.fullmatch(r'ppt/slides/slide\d+\.xml', name)),
            key=lambda name: int(re.search(r'slide(\d+)\.xml', name).group(1)),
        )
        for slide_name in slides:
            number = int(re.search(r'slide(\d+)\.xml', slide_name).group(1))
            root = etree.fromstring(archive.read(slide_name))
            for run in root.xpath('//a:r | //a:fld', namespaces=NS):
                text = ''.join(run.xpath('./a:t/text()', namespaces=NS))
                if not text.strip() or PRIVATE_USE.fullmatch(text.strip()):
                    continue
                checked_runs += 1
                props = run.find(f'{{{A}}}rPr')
                paragraph = run.getparent()
                paragraph_default = paragraph.find(f'{{{A}}}pPr/{{{A}}}defRPr')
                for script, expected in expected_fonts.items():
                    # CJK runs need both explicit families. Latin-only runs do
                    # not require an East Asian assignment.
                    if script == 'ea' and not CJK.search(text):
                        continue
                    node = props.find(f'{{{A}}}{script}') if props is not None else None
                    if node is None and paragraph_default is not None:
                        node = paragraph_default.find(f'{{{A}}}{script}')
                    actual = node.get('typeface') if node is not None else None
                    if actual != expected:
                        violations.append({'page': number, 'script': script,
                                           'expected': expected, 'actual': actual,
                                           'text_sample': text[:24]})
    return {'passed': not violations, 'slide_count': len(slides),
            'checked_runs': checked_runs, 'violations': violations,
            'font_policy': expected_fonts, 'font_profile': selected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--profile')
    args = parser.parse_args()
    result = audit(args.input, args.profile)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'slide_count': result['slide_count'],
                      'checked_runs': result['checked_runs'],
                      'violations': len(result['violations'])}, ensure_ascii=False))
    if not result['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()

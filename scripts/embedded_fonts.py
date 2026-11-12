"""Remove embedded font payloads from a PPTX task copy without changing editable text.

Source PPTX files are immutable during normal generation. Maintainers may use
the CLI on a reviewed copy, then rebuild that library's hash manifest.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pptx import Presentation

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def font_parts(names):
    return {name for name in names if name.startswith('ppt/fonts/') and not name.endswith('/')}


def clean_metadata(name: str, data: bytes) -> bytes:
    if name == 'ppt/presentation.xml':
        root = etree.fromstring(data)
        changed = False
        for node in root.findall(f'{{{P}}}embeddedFontLst'):
            root.remove(node)
            changed = True
    elif name.endswith('.rels'):
        root = etree.fromstring(data)
        changed = False
        for link in list(root):
            target = link.get('Target', '').replace('\\', '/')
            if (link.get('Type', '').endswith('/font')
                    or (name == 'ppt/_rels/presentation.xml.rels'
                        and target.startswith('fonts/'))):
                root.remove(link)
                changed = True
    elif name == '[Content_Types].xml':
        root = etree.fromstring(data)
        changed = False
        for node in list(root):
            if (node.tag == f'{{{CT}}}Default' and node.get('Extension') == 'fntdata') \
                    or (node.tag == f'{{{CT}}}Override'
                        and node.get('PartName', '').lstrip('/').startswith('ppt/fonts/')):
                root.remove(node)
                changed = True
    else:
        return data
    return (etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            if changed else data)


def inspect(path: Path) -> dict:
    with ZipFile(path) as archive:
        names = archive.namelist()
        parts = font_parts(names)
        presentation = etree.fromstring(archive.read('ppt/presentation.xml'))
        embedded = presentation.find(f'{{{P}}}embeddedFontLst')
        references = []
        for name in names:
            if name.endswith('.rels'):
                links = etree.fromstring(archive.read(name))
                references.extend((name, link.get('Target')) for link in links
                                  if link.get('Type', '').endswith('/font'))
        types = etree.fromstring(archive.read('[Content_Types].xml'))
        declarations = [node.get('PartName') or node.get('Extension') for node in types
                        if (node.tag == f'{{{CT}}}Default' and node.get('Extension') == 'fntdata')
                        or (node.tag == f'{{{CT}}}Override'
                            and node.get('PartName', '').lstrip('/').startswith('ppt/fonts/'))]
        return {'font_parts': len(parts),
                'font_bytes_compressed': sum(info.compress_size for info in archive.infolist()
                                             if info.filename in parts),
                'font_entries': len(embedded) if embedded is not None else 0,
                'font_relationships': len(references),
                'font_content_types': len(declarations),
                'slides': len(Presentation(path).slides)}


def strip(source: Path, output: Path) -> dict:
    source = Path(source).resolve()
    output = Path(output).resolve()
    before = inspect(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not any(before[key] for key in ('font_parts', 'font_entries',
                                       'font_relationships', 'font_content_types')):
        if source != output:
            shutil.copyfile(source, output)
        return {'before': before, 'after': inspect(output)}
    with tempfile.NamedTemporaryFile(prefix='epoint-no-fonts-', suffix='.pptx',
                                     dir=output.parent, delete=False) as temporary:
        candidate = Path(temporary.name)
    try:
        with ZipFile(source) as original, ZipFile(candidate, 'w') as rewritten:
            removed = font_parts(original.namelist())
            for item in original.infolist():
                if item.filename in removed:
                    continue
                data = clean_metadata(item.filename, original.read(item.filename))
                rewritten.writestr(item, data)
        after = inspect(candidate)
        if any(after[key] for key in ('font_parts', 'font_entries',
                                      'font_relationships', 'font_content_types')):
            raise ValueError('EMBEDDED_FONT_REFERENCES_REMAIN')
        if after['slides'] != before['slides']:
            raise ValueError('SLIDE_COUNT_CHANGED')
        os.replace(candidate, output)
        return {'before': before, 'after': after}
    finally:
        if candidate.exists():
            candidate.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(strip(args.input, args.out), ensure_ascii=False))


if __name__ == '__main__':
    main()

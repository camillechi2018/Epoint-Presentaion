"""Build a small, source-traceable offline library from verified structural pages."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pptx import Presentation

SKILL = Path(__file__).resolve().parents[1]
SELECTION = {
    'blue': ['cover-02', 'content-blue-001', 'content-blue-002', 'supp-closing-01'],
    'red': ['supp-cover-red-06', 'supp-directory-04-red-variant', 'supp-section-red-13', 'supp-closing-red-19'],
    'deep-blue-tech': ['cover-tech-001', 'directory-tech-006', 'section-tech-011', 'closing-tech-082'],
}
ROLES = ('cover', 'directory', 'section', 'closing')


def remove_embedded_fonts(source: Path):
    """Keep the editable slide, but omit source-only embedded fonts in the offline copy."""
    presentation_ns = 'http://schemas.openxmlformats.org/presentationml/2006/main'
    content_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    with tempfile.NamedTemporaryFile(prefix='epoint-no-fonts-', suffix='.pptx',
                                     dir=source.parent, delete=False) as temporary:
        candidate = Path(temporary.name)
    try:
        with ZipFile(source) as original, ZipFile(candidate, 'w') as rewritten:
            font_parts = {name for name in original.namelist() if name.startswith('ppt/fonts/')}
            if not font_parts:
                candidate.unlink()
                return
            for item in original.infolist():
                name = item.filename
                if name in font_parts:
                    continue
                data = original.read(name)
                if name == 'ppt/presentation.xml':
                    root = etree.fromstring(data)
                    for node in root.findall(f'{{{presentation_ns}}}embeddedFontLst'):
                        root.remove(node)
                    data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                elif name == 'ppt/_rels/presentation.xml.rels':
                    root = etree.fromstring(data)
                    for node in list(root):
                        if node.get('Type', '').endswith('/font'):
                            root.remove(node)
                    data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                elif name == '[Content_Types].xml':
                    root = etree.fromstring(data)
                    for node in list(root):
                        if (node.tag == f'{{{content_ns}}}Default'
                                and node.get('Extension') == 'fntdata'):
                            root.remove(node)
                    data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
                rewritten.writestr(item, data)
        if len(Presentation(candidate).slides) != 1:
            raise RuntimeError(f'去嵌入字体后单页模板不可打开：{candidate}')
        os.replace(candidate, source)
    finally:
        if candidate.exists():
            candidate.unlink()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_for(entry, theme):
    if theme == 'red' and entry.get('red_source'):
        return entry['red_source'], entry['red_source_page'], entry.get('red_bindings', entry['bindings']), entry.get('red_preview', entry['preview'])
    return entry['source'], entry['source_page'], entry['bindings'], entry['preview']


def copy_one_slide(source, page, target):
    presentation = Presentation(source)
    if not 1 <= page <= len(presentation.slides):
        raise ValueError(f'来源页号超出范围：{source}:{page}')
    for index in range(len(presentation.slides) - 1, -1, -1):
        if index == page - 1:
            continue
        slide_id = presentation.slides._sldIdLst[index]
        presentation.part.drop_rel(slide_id.rId)
        presentation.slides._sldIdLst.remove(slide_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(target)
    if len(Presentation(target).slides) != 1:
        raise RuntimeError(f'单页模板不可打开：{target}')


def build(library: Path, target: Path):
    library = library.resolve()
    catalog = json.loads((library / 'catalog.json').read_text(encoding='utf-8-sig'))
    entries = {entry['id']: entry for entry in catalog['layouts']}
    commit = subprocess.check_output(['git', '-C', str(library), 'rev-parse', 'HEAD'], text=True).strip()
    staging = Path(tempfile.mkdtemp(prefix='epoint-pack-', dir=target.parent))
    try:
        selected = []
        for theme, ids in SELECTION.items():
            for role, entry_id in zip(ROLES, ids):
                entry = dict(entries[entry_id])
                if entry['role'] != role or theme not in entry['themes']:
                    raise ValueError(f'最小包选版角色或主题不符：{theme}/{entry_id}')
                if entry.get('classification_status') != 'verified' or entry.get('status') not in ('approved', 'draft_pending_review'):
                    raise ValueError(f'最小包只能包含已验收页面：{theme}/{entry_id}')
                source, page, binding, preview = source_for(entry, theme)
                pack_source = f'sources/{theme}-{entry_id}.pptx'
                copy_one_slide(library / source, page, staging / pack_source)
                if theme == 'blue' and role == 'cover':
                    remove_embedded_fonts(staging / pack_source)
                copied = {}
                for key, rel in [('bindings', binding), ('layout_rules', entry['layout_rules']),
                                 ('spec', entry['spec']), ('motion', entry['motion']), ('preview', preview)]:
                    dest = staging / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(library / rel, dest)
                    copied[key] = rel
                if entry.get('semantic_review'):
                    rel = entry['semantic_review']
                    dest = staging / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(library / rel, dest)
                if entry.get('background_override'):
                    rel = entry['background_override']
                    dest = staging / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(library / rel, dest)
                entry.update(source=pack_source, source_page=1, themes=[theme],
                             bindings=copied['bindings'], preview=copied['preview'],
                             red_source=None, red_source_page=None, red_bindings=None,
                             red_preview=None,
                             pack_origin={'commit': commit, 'source': source, 'source_page': page})
                selected.append(entry)
        for rel in ('relation-taxonomy.json', 'brand/logo/logo-black.png', 'brand/logo/logo-white.png',
                    'brand/logo/logo-color.png', 'brand/logo/logo.json'):
            source = library / rel
            if source.is_file():
                dest = staging / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
        mini_catalog = {key: value for key, value in catalog.items() if key != 'layouts'}
        mini_catalog['layouts'] = selected
        mini_catalog['component_entries'] = len(selected)
        (staging / 'catalog.json').write_text(json.dumps(mini_catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        hashes = {p.relative_to(staging).as_posix(): digest(p) for p in sorted(staging.rglob('*')) if p.is_file()}
        manifest = {'schema_version': '1.0', 'version': catalog['version'], 'source_commit': commit,
                    'status': 'draft_pending_review', 'file_count': len(hashes), 'files': hashes}
        (staging / 'knowledge-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        previous = target.with_name(target.name + '.previous')
        if previous.exists():
            shutil.rmtree(previous)
        if target.exists():
            target.rename(previous)
        try:
            staging.rename(target)
        except PermissionError:
            # Some Windows Office/AV file handles delay a directory rename.
            # A first install can safely copy; updates still retain .previous.
            if target.exists():
                raise
            shutil.copytree(staging, target)
            shutil.rmtree(staging, ignore_errors=True)
        return {'path': str(target), 'source_commit': commit, 'layouts': len(selected),
                'bytes': sum(p.stat().st_size for p in target.rglob('*') if p.is_file())}
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--library', type=Path, required=True)
    ap.add_argument('--target', type=Path, default=SKILL / 'assets' / 'minimal-template-pack')
    args = ap.parse_args()
    print(json.dumps(build(args.library, args.target), ensure_ascii=False))

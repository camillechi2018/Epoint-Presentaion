"""Small S3 gates for a complete, source-backed PPTX delivery."""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from lxml import etree as ET
from pptx import Presentation

from distribution import verify_manifest

STRUCTURAL = ('cover', 'directory', 'section', 'closing')
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'


def check_structure(pages, *, complete=True):
    if not complete:
        return {'status': 'partial_draft', 'complete_deck': False}
    if not isinstance(pages, list) or not pages or not all(isinstance(p, dict) for p in pages):
        raise ValueError('COMPLETE_DECK_PAGES_MISSING')
    roles = [page.get('role') for page in pages]
    if roles[0] != 'cover' or roles[-1] != 'closing' or 'directory' not in roles or 'section' not in roles:
        raise ValueError('COMPLETE_DECK_STRUCTURE_MISSING')
    if roles.index('directory') >= roles.index('section') or roles.index('section') >= len(roles) - 1:
        raise ValueError('COMPLETE_DECK_STRUCTURE_ORDER')
    sections = set()
    for page in pages:
        if page.get('role') not in STRUCTURAL:
            continue
        if page.get('selection_mode') != 'source_template' or not page.get('layout_id'):
            raise ValueError('STRUCTURE_SOURCE_REQUIRED')
        if page['role'] == 'section':
            sections.add(page['layout_id'])
    if len(sections) != 1:
        raise ValueError('SECTION_LAYOUT_MIXED')
    return {'status': 'passed', 'complete_deck': True, 'section_layout_id': next(iter(sections)),
            'roles': roles}


def _source(entry, theme):
    source = entry.get('red_source') if theme == 'red' and entry.get('red_source') else entry['source']
    page = entry.get('red_source_page') if theme == 'red' and entry.get('red_source_page') else entry['source_page']
    ready = entry.get('ready_source_by_theme', {}).get(theme)
    return (ready, 1) if ready else (source, page)


def check_prefilled(assembly, library):
    """Recheck trusted library bytes and all prefilled pages before assembly."""
    root = Path(library).resolve()
    manifest = verify_manifest(root)
    commit = assembly.get('library_commit')
    actual_commit = (subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                             text=True).strip() if (root / '.git').exists()
                     else manifest.get('source_commit'))
    if commit != actual_commit or not re.fullmatch(r'[0-9a-f]{40}', str(commit)):
        raise ValueError('LIBRARY_COMMIT_MISMATCH')
    catalog = json.loads((root / 'catalog.json').read_text(encoding='utf-8-sig'))
    entries = {entry['id']: entry for entry in catalog['layouts']}
    pages = assembly.get('pages', [])
    slides = assembly.get('slides', [])
    if len(pages) != len(slides):
        raise ValueError('ASSEMBLY_PAGE_COUNT_MISMATCH')
    structure = check_structure(pages, complete=assembly.get('complete_deck', False))
    evidence = []
    for index, (page, slide) in enumerate(zip(pages, slides), 1):
        path = Path(slide['path']).resolve(strict=True)
        presentation = Presentation(path)
        if len(presentation.slides) != 1:
            raise ValueError('PREFILLED_PAGE_COUNT_INVALID')
        record = {'index': index, 'role': page.get('role'), 'filled_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if page.get('role') in STRUCTURAL and slide.get('source_stamp') != page.get('source_stamp'):
            raise ValueError('STRUCTURE_SOURCE_STAMP_MISMATCH')
        if page.get('selection_mode') == 'source_template':
            layout = page.get('layout_id')
            entry = entries.get(layout)
            if not entry or (page.get('role') in STRUCTURAL and entry.get('role') != page['role']):
                raise ValueError('SOURCE_LAYOUT_NOT_IN_LIBRARY')
            theme = assembly['theme']
            if theme not in entry.get('themes', []):
                raise ValueError('SOURCE_THEME_MISMATCH')
            source, source_page = _source(entry, theme)
            expected = f'epoint:{layout}:{theme}:{source}:{source_page}:{commit}'
            if page.get('source_stamp') != expected or slide.get('source_stamp') != expected or presentation.slides[0]._element.cSld.get('name') != expected:
                raise ValueError('SOURCE_STAMP_NOT_CATALOG_BOUND')
            expected_hash = manifest['files'].get(source)
            if not expected_hash or hashlib.sha256((root / source).read_bytes()).hexdigest() != expected_hash:
                raise ValueError('SOURCE_FILE_HASH_MISMATCH')
            record.update(layout_id=layout, source=source, source_page=source_page,
                          source_sha256=expected_hash, source_stamp=expected)
        elif page.get('role') in STRUCTURAL:
            raise ValueError('STRUCTURE_SOURCE_REQUIRED')
        evidence.append(record)
    return {'status': 'passed', 'structure': structure, 'source_pages': evidence,
            'library_commit': commit}


def check_package_relations(path):
    """Reject missing internal OPC targets before a PPTX is called deliverable."""
    try:
        return _inspect_package_relations(path)
    except (BadZipFile, ET.XMLSyntaxError) as exc:
        raise ValueError('PACKAGE_INVALID') from exc


def _inspect_package_relations(path):
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('DUPLICATE_PACKAGE_PART')
        parts = set(names)
        checked = 0
        for name in names:
            if not name.endswith('.rels'):
                continue
            if name == '_rels/.rels':
                owner = ''
            else:
                folder, basename = posixpath.split(name)
                owner = posixpath.join(posixpath.dirname(folder), basename[:-5])
                if owner not in parts:
                    raise ValueError('ORPHAN_RELATIONSHIP_PART')
            links = ET.fromstring(archive.read(name))
            ids = set()
            for link in links:
                if link.tag != '{' + REL + '}Relationship':
                    continue
                rid = link.get('Id')
                if rid in ids:
                    raise ValueError('DUPLICATE_RELATIONSHIP_ID')
                ids.add(rid)
                if link.get('TargetMode') == 'External':
                    continue
                target = unquote(link.get('Target', ''))
                if target.startswith('/'):
                    target = target.lstrip('/')
                else:
                    target = posixpath.join(posixpath.dirname(owner), target)
                target = posixpath.normpath(target)
                if target not in parts or target.startswith('../'):
                    raise ValueError('RELATION_TARGET_MISSING: ' + owner + ' -> ' + target)
                checked += 1
    return {'status': 'passed', 'internal_relations': checked}


def check_finished(path, assembly, prefilled):
    relationships = check_package_relations(path)
    deck = Presentation(path)
    pages = assembly['pages']
    if len(deck.slides) != len(pages):
        raise ValueError('FINISHED_PAGE_COUNT_MISMATCH')
    for index, (page, source, slide) in enumerate(zip(pages, prefilled['source_pages'], deck.slides), 1):
        if hashlib.sha256(Path(assembly['slides'][index - 1]['path']).read_bytes()).hexdigest() != source['filled_sha256']:
            raise ValueError('PREFILLED_PAGE_CHANGED')
        if page.get('selection_mode') == 'source_template':
            actual = slide._element.cSld.get('name', '')
            if actual != source['source_stamp'] + ':' + str(index):
                raise ValueError('FINISHED_SOURCE_ASSOCIATION_MISMATCH')
    return {'status': 'passed', 'slide_count': len(deck.slides), 'package': relationships,
            'source_associations': sum(p.get('selection_mode') == 'source_template' for p in pages)}

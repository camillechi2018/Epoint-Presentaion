"""Structural OPC, visible-slide master and source audit for the S2 pilot.

PowerPoint opening and rendering remain separate acceptance gates.
"""
import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET
from assemble_native import CT, P, R, REL, rels_name, resolve, one_slide


def inspect(path, sources=()):
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('DUPLICATE_PACKAGE_PART')
        files = {name: archive.read(name) for name in names if not name.endswith('/')}
    if '[Content_Types].xml' not in files or '_rels/.rels' not in files:
        raise ValueError('PACKAGE_ROOT_MISSING')
    types = ET.fromstring(files['[Content_Types].xml'])
    defaults = {}
    overrides = {}
    for item in types:
        if item.tag == '{' + CT + '}Default':
            key = item.attrib['Extension'].lower()
            if key in defaults:
                raise ValueError('DUPLICATE_CONTENT_TYPE')
            defaults[key] = item.attrib['ContentType']
        elif item.tag == '{' + CT + '}Override':
            key = item.attrib['PartName'].lstrip('/')
            if key in overrides:
                raise ValueError('DUPLICATE_CONTENT_TYPE')
            overrides[key] = item.attrib['ContentType']
    for part in files:
        if part == '[Content_Types].xml':
            continue
        if part.startswith('/') or '..' in part.split('/') or '\\' in part:
            raise ValueError('UNSAFE_PACKAGE_PART')
        extension = 'rels' if part.endswith('.rels') else posixpath.splitext(part)[1].lstrip('.').lower()
        if part not in overrides and extension not in defaults:
            raise ValueError('CONTENT_TYPE_MISSING: ' + part)
        if part.endswith('.xml') or part.endswith('.rels'):
            ET.fromstring(files[part])
    def relations(part):
        name = '_rels/.rels' if not part else rels_name(part)
        if name not in files:
            return []
        links = list(ET.fromstring(files[name]))
        ids = [link.attrib.get('Id') for link in links]
        if len(ids) != len(set(ids)):
            raise ValueError('DUPLICATE_RELATIONSHIP_ID: ' + part)
        for link in links:
            if link.attrib.get('TargetMode') == 'External':
                continue
            target = resolve(part, link.attrib['Target'])
            if target not in files:
                raise ValueError('RELATION_TARGET_MISSING: ' + part + ' -> ' + target)
        return links
    root_links = relations('')
    if not any(link.attrib['Type'].endswith('/officeDocument') and
               resolve('', link.attrib['Target']) == 'ppt/presentation.xml'
               for link in root_links):
        raise ValueError('PRESENTATION_ROOT_RELATION_MISSING')
    for part in files:
        if '/_rels/' in part and part.endswith('.rels'):
            folder, name = posixpath.split(part)
            owner = posixpath.join(posixpath.dirname(folder), name[:-5])
            if owner not in files:
                raise ValueError('ORPHAN_RELATIONSHIP_PART: ' + part)
            relations(owner)
    presentation = ET.fromstring(files['ppt/presentation.xml'])
    pres_links = {link.attrib['Id']: link for link in relations('ppt/presentation.xml')}
    slide_nodes = list(presentation.find('{' + P + '}sldIdLst'))
    if len(slide_nodes) < 2 or len({x.attrib['id'] for x in slide_nodes}) != len(slide_nodes):
        raise ValueError('PILOT_SLIDE_COUNT_OR_IDS_INVALID')
    masters = presentation.find('{' + P + '}sldMasterIdLst')
    if masters is None:
        raise ValueError('MASTER_REGISTRATION_MISSING')
    registered = set()
    for node in masters:
        rid = node.attrib['{' + R + '}id']
        if rid not in pres_links:
            raise ValueError('MASTER_RELATION_MISSING')
        registered.add(resolve('ppt/presentation.xml', pres_links[rid].attrib['Target']))
    master_and_layout_ids = [int(node.attrib['id']) for node in masters]
    for master_part in registered:
        master_root = ET.fromstring(files[master_part])
        master_and_layout_ids.extend(int(node.attrib['id'])
                                     for node in master_root.iter('{' + P + '}sldLayoutId'))
    if len(master_and_layout_ids) != len(set(master_and_layout_ids)):
        raise ValueError('DUPLICATE_MASTER_OR_LAYOUT_ID')
    notes_list = presentation.find('{' + P + '}notesMasterIdLst')
    if notes_list is not None and len(notes_list) > 1:
        raise ValueError('MULTIPLE_NOTES_MASTERS')
    used = set()
    stamps = []
    slides = []
    for node in slide_nodes:
        rid = node.attrib['{' + R + '}id']
        if rid not in pres_links:
            raise ValueError('SLIDE_RELATION_MISSING')
        slide = resolve('ppt/presentation.xml', pres_links[rid].attrib['Target'])
        slides.append(slide)
        root = ET.fromstring(files[slide])
        cslide = root.find('{' + P + '}cSld')
        stamp = cslide.attrib.get('name', '') if cslide is not None else ''
        if not stamp.startswith('epoint:'):
            raise ValueError('SOURCE_STAMP_MISSING: ' + slide)
        stamps.append(stamp)
        layout_links = [link for link in relations(slide) if link.attrib['Type'].endswith('/slideLayout')]
        if len(layout_links) != 1:
            raise ValueError('SLIDE_LAYOUT_COUNT_INVALID: ' + slide)
        layout = resolve(slide, layout_links[0].attrib['Target'])
        master_links = [link for link in relations(layout) if link.attrib['Type'].endswith('/slideMaster')]
        if len(master_links) != 1:
            raise ValueError('LAYOUT_MASTER_COUNT_INVALID: ' + layout)
        used.add(resolve(layout, master_links[0].attrib['Target']))
    if registered != used:
        raise ValueError('UNUSED_OR_UNREGISTERED_MASTER')
    themes = set()
    commits = set()
    for stamp in stamps:
        parts = stamp.split(':', 3)
        if len(parts) != 4:
            raise ValueError('SOURCE_STAMP_INVALID')
        themes.add(parts[2])
        commit = stamp.rsplit(':', 1)[-1]
        if not re.fullmatch(r'[0-9a-f]{40}', commit):
            raise ValueError('SOURCE_COMMIT_INVALID')
        commits.add(commit)
    if len(themes) != 1:
        raise ValueError('MIXED_THEMES')
    if len(commits) != 1:
        raise ValueError('MIXED_LIBRARY_COMMITS')
    source_sha = []
    if sources:
        if len(sources) != len(slides):
            raise ValueError('SOURCE_COUNT_MISMATCH')
        for index, path in enumerate(sources):
            with ZipFile(path) as archive:
                source_files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
            source_slide = one_slide(source_files)
            if files[slides[index]] != source_files[source_slide]:
                raise ValueError('SOURCE_SLIDE_XML_MISMATCH: ' + str(index + 1))
            source_sha.append(hashlib.sha256(Path(path).read_bytes()).hexdigest())
    return {'status': 'passed', 'slide_count': len(slides), 'registered_masters': len(registered),
            'theme': next(iter(themes)), 'library_commit': next(iter(commits)),
            'source_stamps': stamps, 'source_file_sha256': source_sha, 'package_parts': len(files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--sources', type=Path, nargs='+', required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = inspect(args.input, args.sources)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()

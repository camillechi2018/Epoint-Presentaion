"""Experimental native OPC assembly of pre-filled single-slide PPTX files.

This S2 pilot is not the production deck entrypoint and does not replace source,
font, color, media or visual acceptance gates.
"""
import argparse
import json
import posixpath
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as ET

REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def rels_name(part):
    folder, name = posixpath.split(part)
    return posixpath.join(folder, '_rels', name + '.rels')


def resolve(part, target):
    target = unquote(target)
    if target.startswith('/'):
        result = posixpath.normpath(target.lstrip('/'))
    else:
        result = posixpath.normpath(posixpath.join(posixpath.dirname(part), target))
    if result.startswith('../') or result == '..':
        raise ValueError('PACKAGE_RELATION_ESCAPES_ROOT')
    return result


def xml(data):
    return ET.fromstring(data)


def bytes_xml(node):
    return ET.tostring(node, encoding='utf-8', xml_declaration=True)


def relationships(files, part):
    name = rels_name(part)
    return xml(files[name]) if name in files else ET.Element('{' + REL + '}Relationships')


def one_slide(files):
    pres = xml(files['ppt/presentation.xml'])
    slides = list(pres.find('{' + P + '}sldIdLst'))
    if len(slides) != 1:
        raise ValueError('EXPECTED_ONE_SOURCE_SLIDE')
    rid = slides[0].attrib['{' + R + '}id']
    links = relationships(files, 'ppt/presentation.xml')
    target = next(item.attrib['Target'] for item in links if item.attrib['Id'] == rid)
    return resolve('ppt/presentation.xml', target)


def _merge_one(out, source):
    second_slide = one_slide(source)
    source_types = xml(source['[Content_Types].xml'])
    overrides = {x.attrib['PartName'].lstrip('/'): x.attrib['ContentType']
                 for x in source_types if x.tag == '{' + CT + '}Override'}
    defaults = {x.attrib['Extension']: x.attrib['ContentType']
                for x in source_types if x.tag == '{' + CT + '}Default'}
    out_types = xml(out['[Content_Types].xml'])
    existing_defaults = {x.attrib['Extension'] for x in out_types if x.tag == '{' + CT + '}Default'}
    copied = {}

    def copy_part(old):
        if old in copied:
            return copied[old]
        if old.startswith('ppt/notesMasters/') and old.endswith('.xml'):
            existing = sorted(name for name in out if name.startswith('ppt/notesMasters/') and name.endswith('.xml'))
            if existing:
                copied[old] = existing[0]
                return existing[0]
        if old not in source:
            raise ValueError('SOURCE_RELATION_MISSING: ' + old)
        folder, name = posixpath.split(old)
        conventional = {'ppt/slides': 'slide', 'ppt/slideLayouts': 'slideLayout',
                        'ppt/slideMasters': 'slideMaster', 'ppt/theme': 'theme'}
        if folder in conventional and name.endswith('.xml'):
            candidate = posixpath.join(folder, conventional[folder] + '999.xml')
        else:
            candidate = posixpath.join(folder, 's2_' + name)
        number = 2
        while candidate in out:
            candidate = posixpath.join(folder, conventional[folder] + str(999 + number) + '.xml') if folder in conventional and name.endswith('.xml') else posixpath.join(folder, 's2_' + str(number) + '_' + name)
            number += 1
        copied[old] = candidate
        out[candidate] = source[old]
        if old in overrides:
            ET.SubElement(out_types, '{' + CT + '}Override',
                          {'PartName': '/' + candidate, 'ContentType': overrides[old]})
        else:
            suffix = posixpath.splitext(old)[1].lstrip('.')
            if suffix in defaults and suffix not in existing_defaults:
                ET.SubElement(out_types, '{' + CT + '}Default',
                              {'Extension': suffix, 'ContentType': defaults[suffix]})
                existing_defaults.add(suffix)
        link_name = rels_name(old)
        if link_name in source:
            links = xml(source[link_name])
            for link in links:
                if link.attrib.get('TargetMode') == 'External':
                    continue
                target = resolve(old, link.attrib['Target'])
                new_target = copy_part(target)
                link.attrib['Target'] = posixpath.relpath(new_target, posixpath.dirname(candidate))
            out[rels_name(candidate)] = bytes_xml(links)
        return candidate

    copied_slide = copy_part(second_slide)
    presentation = xml(out['ppt/presentation.xml'])
    links = relationships(out, 'ppt/presentation.xml')
    used_rids = {x.attrib['Id'] for x in links}

    def add_link(target, kind):
        number = 1
        while 'rId' + str(number) in used_rids:
            number += 1
        rid = 'rId' + str(number)
        used_rids.add(rid)
        ET.SubElement(links, '{' + REL + '}Relationship',
                      {'Id': rid, 'Type': R + '/' + kind,
                       'Target': posixpath.relpath(target, 'ppt')})
        return rid

    slide_list = presentation.find('{' + P + '}sldIdLst')
    slide_id = max(int(x.attrib['id']) for x in slide_list) + 1
    ET.SubElement(slide_list, '{' + P + '}sldId',
                  {'id': str(slide_id), '{' + R + '}id': add_link(copied_slide, 'slide')})
    # Register the copied slide's master with the presentation. The recursive
    # relationship walk already copied its layouts, themes, images and fonts.
    masters = presentation.find('{' + P + '}sldMasterIdLst')
    if masters is None:
        masters = ET.Element('{' + P + '}sldMasterIdLst')
        presentation.insert(0, masters)
    # Master and layout identifiers share a presentation-wide namespace in
    # PowerPoint. A cloned master may repeat layout IDs from the first deck.
    numeric_ids = {int(x.attrib['id']) for x in masters}
    for part in out:
        if part.startswith('ppt/slideMasters/') and part.endswith('.xml') and part not in copied.values():
            root = xml(out[part])
            numeric_ids.update(int(x.attrib['id']) for x in root.iter('{' + P + '}sldLayoutId'))
    master_id = max(numeric_ids or {2147483647}) + 1
    for old, new in copied.items():
        if old.startswith('ppt/slideMasters/') and old.endswith('.xml'):
            master_root = xml(out[new])
            for layout_id in master_root.iter('{' + P + '}sldLayoutId'):
                master_id += 1
                layout_id.attrib['id'] = str(master_id)
            out[new] = bytes_xml(master_root)
            master_id += 1
            ET.SubElement(masters, '{' + P + '}sldMasterId',
                          {'id': str(master_id), '{' + R + '}id': add_link(new, 'slideMaster')})
    # Filled source decks may register many unused masters. PowerPoint rejects
    # the merged package when all source masters remain registered. Determine
    # the actual master from each visible slide's layout and keep only those.
    link_by_id = {link.attrib['Id']: link for link in links}
    used_masters = set()
    for slide_id_node in slide_list:
        slide_part = resolve('ppt/presentation.xml', link_by_id[slide_id_node.attrib['{' + R + '}id']].attrib['Target'])
        slide_links = relationships(out, slide_part)
        layout_link = next((link for link in slide_links if link.attrib['Type'].endswith('/slideLayout')), None)
        if layout_link is None:
            raise ValueError('SLIDE_LAYOUT_MISSING: ' + slide_part)
        layout_part = resolve(slide_part, layout_link.attrib['Target'])
        layout_links = relationships(out, layout_part)
        master_link = next((link for link in layout_links if link.attrib['Type'].endswith('/slideMaster')), None)
        if master_link is None:
            raise ValueError('SLIDE_MASTER_MISSING: ' + layout_part)
        used_masters.add(resolve(layout_part, master_link.attrib['Target']))
    for master_node in list(masters):
        master_link = link_by_id[master_node.attrib['{' + R + '}id']]
        if resolve('ppt/presentation.xml', master_link.attrib['Target']) not in used_masters:
            masters.remove(master_node)
            links.remove(master_link)
    if len(masters) != len(used_masters):
        raise ValueError('MASTER_REGISTRATION_MISMATCH')
    out['ppt/presentation.xml'] = bytes_xml(presentation)
    out[rels_name('ppt/presentation.xml')] = bytes_xml(links)
    out['[Content_Types].xml'] = bytes_xml(out_types)
    for part in list(out):
        if '/_rels/' not in part or not part.endswith('.rels'):
            continue
        owner_dir, rel_name = posixpath.split(part)
        owner = posixpath.join(posixpath.dirname(owner_dir), rel_name[:-5])
        for link in xml(out[part]):
            if link.attrib.get('TargetMode') != 'External' and resolve(owner, link.attrib['Target']) not in out:
                raise ValueError('OUTPUT_RELATION_MISSING: ' + owner + ' -> ' + link.attrib['Target'])
    return len(copied), len(masters)


def assemble_many(inputs, output):
    inputs = tuple(Path(item) for item in inputs)
    if len(inputs) < 2:
        raise ValueError('AT_LEAST_TWO_SOURCE_SLIDES_REQUIRED')
    with ZipFile(inputs[0]) as z:
        out = {name: z.read(name) for name in z.namelist() if not name.endswith('/')}
    one_slide(out)
    copied_total = 0
    registered_masters = 0
    for source_path in inputs[1:]:
        with ZipFile(source_path) as z:
            source = {name: z.read(name) for name in z.namelist() if not name.endswith('/')}
        copied_count, registered_masters = _merge_one(out, source)
        copied_total += copied_count
    with ZipFile(output, 'w', ZIP_DEFLATED) as z:
        for name, data in out.items():
            z.writestr(name, data)
    return {'slides': len(inputs), 'copied_parts': copied_total,
            'registered_masters': registered_masters, 'output': str(output)}


def assemble(first, second, output):
    return assemble_many((first, second), output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--first', type=Path)
    parser.add_argument('--second', type=Path)
    parser.add_argument('--pages', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--experimental', action='store_true', required=True,
                        help='Explicit acknowledgement that full template audit is pending')
    args = parser.parse_args()
    if not args.experimental:
        raise SystemExit('EXPERIMENTAL_FLAG_REQUIRED')
    if args.out.exists():
        raise SystemExit('OUTPUT_EXISTS')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    inputs = args.pages if args.pages else (args.first, args.second)
    if any(item is None for item in inputs):
        raise SystemExit('SOURCE_PAGES_REQUIRED')
    print(json.dumps(assemble_many(inputs, args.out)))


if __name__ == '__main__':
    main()

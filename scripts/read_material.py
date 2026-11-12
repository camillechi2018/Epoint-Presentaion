"""Read supplied material facts without Office automation or silent fill-ins.

The JSON records source coordinates and missing formula caches. It is an input
inventory, not a slide plan or a claim that every item has been used.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def scalar(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    return value


def read_xlsx(path):
    from openpyxl import load_workbook
    from openpyxl.utils.cell import column_index_from_string

    formula_book = load_workbook(path, data_only=False, read_only=False, keep_links=False)
    cached_book = load_workbook(path, data_only=True, read_only=False, keep_links=False)
    sheets = []
    warnings = []
    for sheet in formula_book.worksheets:
        cached = cached_book[sheet.title]
        by_row = defaultdict(list)
        formula_count = 0
        cache_missing = 0
        for cell in sheet._cells.values():
            if cell.value is None or cell.value == '':
                continue
            item = {'cell': cell.coordinate, 'value': scalar(cell.value)}
            if cell.data_type == 'f':
                formula_count += 1
                result = cached[cell.coordinate].value
                item['cached_value'] = scalar(result)
                item['cache_status'] = 'missing' if result is None else 'available'
                if result is None:
                    cache_missing += 1
            by_row[cell.row].append(item)
        rows = [{'row': row, 'cells': sorted(cells, key=lambda item: column_index_from_string(
            ''.join(c for c in item['cell'] if c.isalpha())))}
                for row, cells in sorted(by_row.items())]
        merges = [{'range': str(region), 'anchor': sheet.cell(region.min_row, region.min_col).coordinate,
                   'value': scalar(sheet.cell(region.min_row, region.min_col).value)}
                  for region in sheet.merged_cells.ranges]
        sheets.append({'name': sheet.title, 'effective_row_count': len(rows),
                       'formula_count': formula_count, 'formula_cache_missing': cache_missing,
                       'merged_ranges': merges, 'rows': rows})
        if cache_missing:
            warnings.append({'code': 'FORMULA_CACHE_MISSING', 'sheet': sheet.title,
                             'count': cache_missing})
    with ZipFile(path) as archive:
        media = sorted(name for name in archive.namelist() if name.startswith('xl/media/') and not name.endswith('/'))
    return {'kind': 'xlsx', 'sheets': sheets, 'embedded_media': media, 'warnings': warnings}


def read_xls(path):
    import xlrd

    book = xlrd.open_workbook(str(path), formatting_info=True)
    sheets = []
    for sheet in book.sheets():
        rows = []
        for row_index in range(sheet.nrows):
            cells = []
            for col_index in range(sheet.ncols):
                cell = sheet.cell(row_index, col_index)
                if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK) or cell.value == '':
                    continue
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    value = xlrd.xldate_as_datetime(value, book.datemode).isoformat()
                elif cell.ctype == xlrd.XL_CELL_ERROR:
                    value = xlrd.error_text_from_code.get(value, 'UNKNOWN_EXCEL_ERROR')
                cells.append({'row': row_index + 1, 'column': col_index + 1, 'value': scalar(value)})
            if cells:
                rows.append({'row': row_index + 1, 'cells': cells})
        merges = [{'range': [r0 + 1, r1, c0 + 1, c1],
                   'anchor': [r0 + 1, c0 + 1], 'value': scalar(sheet.cell_value(r0, c0))}
                  for r0, r1, c0, c1 in sheet.merged_cells]
        sheets.append({'name': sheet.name, 'effective_row_count': len(rows),
                       'merged_ranges': merges, 'rows': rows})
    return {'kind': 'xls', 'sheets': sheets, 'warnings': [
        {'code': 'XLS_FORMULA_ORIGIN_UNAVAILABLE', 'detail': 'BIFF reader returns cached values; formula expressions are not identified.'},
        {'code': 'XLS_EMBEDDED_MEDIA_UNAVAILABLE', 'detail': 'Embedded image inventory is not supported for BIFF files.'}]}


def read_docx(path):
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(path)
    blocks = []
    def image_refs(element):
        result = []
        for blip in element.iter(qn('a:blip')):
            rid = blip.get(qn('r:embed'))
            if rid and rid in document.part.rels:
                result.append(str(document.part.rels[rid].target_part.partname).lstrip('/'))
        return result
    for child in document.element.body.iterchildren():
        if child.tag == qn('w:p'):
            paragraph = Paragraph(child, document._body)
            refs = image_refs(child)
            if paragraph.text.strip() or refs:
                blocks.append({'type': 'paragraph', 'text': paragraph.text, 'media_parts': refs})
        elif child.tag == qn('w:tbl'):
            table = Table(child, document._body)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            blocks.append({'type': 'table', 'rows': rows, 'media_parts': image_refs(child)})
    with ZipFile(path) as archive:
        media = [{'part': name, 'sha256': hashlib.sha256(archive.read(name)).hexdigest()}
                 for name in sorted(archive.namelist()) if name.startswith('word/media/') and not name.endswith('/')]
        side_stories = []
        for name in sorted(archive.namelist()):
            if not (name.startswith('word/header') or name.startswith('word/footer')) or not name.endswith('.xml'):
                continue
            from lxml import etree as ET
            root = ET.fromstring(archive.read(name))
            value = ''.join(node.text or '' for node in root.iter(qn('w:t')))
            if value.strip():
                side_stories.append({'part': name, 'text': value})
    return {'kind': 'docx', 'blocks': blocks, 'embedded_media': media,
            'media_reference_count': sum(len(block['media_parts']) for block in blocks),
            'side_stories': side_stories,
            'warnings': [{'code': 'DOCX_MEDIA_NOT_PLACED',
                          'detail': 'Media parts and body block references are inventoried; geometry and slide use are not inferred.'}] if media else []}


def read_plain_text(path, encoding='utf-8-sig'):
    try:
        content = path.read_text(encoding=encoding)
    except (UnicodeError, LookupError) as exc:
        raise ValueError('MATERIAL_ENCODING_UNREADABLE: specify the source encoding') from exc
    if not content.strip():
        raise ValueError('EMPTY_MATERIAL: no readable text')
    blocks = []
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        block = {'type': 'line', 'line': number, 'text': line}
        if path.suffix.lower() == '.md':
            heading = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
            if heading:
                block.update(type='heading', level=len(heading.group(1)))
        blocks.append(block)
    return {'kind': path.suffix.lower().lstrip('.'), 'encoding': encoding,
            'blocks': blocks, 'warnings': []}


def read_platform_extraction(path, extraction, source_hash):
    if extraction is None:
        raise ValueError('EXTRACTION_TOOL_UNAVAILABLE' if path.suffix.lower() == '.pdf' else 'OCR_REQUIRED')
    try:
        data = json.loads(Path(extraction).read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('EXTRACTION_INVALID_JSON') from exc
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('EXTRACTION_SCHEMA_INVALID: schema_version must be 1')
    source = data.get('source', {})
    if not isinstance(source, dict):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: source must be an object')
    if source.get('path') is not None and not isinstance(source['path'], str):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: source.path must be a string')
    if source.get('sha256') is not None and not isinstance(source['sha256'], str):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: source.sha256 must be a string')
    if source.get('path') and Path(source['path']).expanduser().resolve() != path:
        raise ValueError('EXTRACTION_SOURCE_MISMATCH: source.path differs from --input')
    if source.get('sha256') and source['sha256'].lower() != source_hash:
        raise ValueError('EXTRACTION_SOURCE_HASH_MISMATCH')
    image = path.suffix.lower() in {'.png', '.jpg', '.jpeg'}
    purpose = source.get('material_use', 'text_facts')
    if purpose not in {'text_facts', 'visual_asset'} or purpose == 'visual_asset' and not image:
        raise ValueError('EXTRACTION_SCHEMA_INVALID: invalid material_use')
    extraction_info = data.get('extraction', {})
    if not isinstance(extraction_info, dict):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: extraction must be an object')
    raw_items = data.get('items')
    if not isinstance(raw_items, list):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: items must be an array')
    raw_warnings = data.get('warnings', [])
    if not isinstance(raw_warnings, list) or any(not isinstance(w, dict) or not isinstance(w.get('code'), str)
                                                 for w in raw_warnings):
        raise ValueError('EXTRACTION_SCHEMA_INVALID: warnings must contain coded objects')
    warnings = list(raw_warnings)
    items = []
    for raw in raw_items:
        if not isinstance(raw, dict) or not isinstance(raw.get('text'), str):
            raise ValueError('EXTRACTION_SCHEMA_INVALID: each item needs text')
        locator = raw.get('locator') or {}
        if not isinstance(locator, dict):
            raise ValueError('EXTRACTION_SCHEMA_INVALID: locator must be an object')
        key = 'image' if image else 'page'
        position = locator.get(key)
        if position is not None and (isinstance(position, bool) or not isinstance(position, int) or position < 1):
            raise ValueError('EXTRACTION_SCHEMA_INVALID: page/image must be a positive integer')
        if position is None:
            warnings.append({'code': 'SOURCE_LOCATION_UNVERIFIED', 'item': len(items) + 1})
            locator = {'scope': 'file'}
        item = {'locator': locator, 'text': raw['text'], 'method': raw.get('method') or extraction_info.get('method') or 'platform_tool'}
        if 'confidence' in raw:
            item['confidence'] = raw['confidence']
        items.append(item)
        if not raw['text'].strip() and not image:
            warnings.append({'code': 'PDF_PAGE_TEXT_EMPTY', 'item': len(items), 'locator': locator})
    if purpose == 'text_facts' and not any(item['text'].strip() for item in items):
        raise ValueError('OCR_REQUIRED' if image or raw_items else 'EXTRACTION_TEXT_MISSING')
    return {'kind': path.suffix.lower().lstrip('.'), 'material_use': purpose,
            'extraction': extraction_info, 'items': items, 'warnings': warnings,
            'image_path': str(path) if image else None}


def read(path, extraction=None, encoding='utf-8-sig'):
    path = Path(path).resolve(strict=True)
    suffix = path.suffix.lower()
    readers = {'.xlsx': read_xlsx, '.xls': read_xls, '.docx': read_docx}
    if suffix not in {*readers, '.txt', '.md', '.pdf', '.png', '.jpg', '.jpeg'}:
        raise ValueError('UNSUPPORTED_MATERIAL_TYPE: ' + suffix)
    before = file_sha256(path)
    if suffix in readers:
        result = readers[suffix](path)
    elif suffix in {'.txt', '.md'}:
        result = read_plain_text(path, encoding=encoding)
    else:
        result = read_platform_extraction(path, extraction, before)
    after = file_sha256(path)
    if before != after:
        raise RuntimeError('SOURCE_CHANGED_DURING_READ')
    prefix = before[:12]
    for block in result.get('blocks', []):
        if 'line' in block:
            block['source_ref'] = f'{prefix}#line={block["line"]}'
    for item in result.get('items', []):
        locator = item['locator']
        label = ('image=' + str(locator['image']) if 'image' in locator else
                 'page=' + str(locator['page']) if 'page' in locator else 'file')
        item['source_ref'] = f'{prefix}#{label}'
    result['source'] = str(path)
    result['sha256'] = before
    result['status'] = 'read_with_warnings' if result['warnings'] else 'read'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--extraction', type=Path, help='Platform PDF/OCR result in schema_version 1 JSON')
    parser.add_argument('--encoding', default='utf-8-sig', help='Text/Markdown source encoding')
    args = parser.parse_args(argv)
    try:
        result = read(args.input, extraction=args.extraction, encoding=args.encoding)
    except (OSError, ValueError, RuntimeError) as exc:
        code = str(exc).split(':', 1)[0]
        if isinstance(exc, FileNotFoundError):
            code = 'SOURCE_FILE_MISSING'
        elif isinstance(exc, OSError) and not isinstance(exc, (ValueError, RuntimeError)):
            code = 'MATERIAL_READ_FAILED'
        print(json.dumps({'status': 'blocked', 'error_code': code,
                          'detail': str(exc)[:400]}, ensure_ascii=True))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {'status': result['status'], 'kind': result['kind'],
               'sha256': result['sha256'], 'warnings': [x['code'] for x in result['warnings']]}
    if 'sheets' in result:
        summary['effective_rows'] = {s['name']: s['effective_row_count'] for s in result['sheets']}
    elif 'blocks' in result:
        summary['blocks'] = len(result['blocks'])
        summary['embedded_media'] = len(result.get('embedded_media', []))
    else:
        summary['items'] = len(result['items'])
    print(json.dumps(summary, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

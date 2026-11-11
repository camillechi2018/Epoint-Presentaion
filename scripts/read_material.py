"""Read supplied Excel/Word facts without Office automation or silent fill-ins.

The JSON records source coordinates and missing formula caches. It is an input
inventory, not a slide plan or a claim that every item has been used.
"""
import argparse
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


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


def read(path):
    path = Path(path).resolve(strict=True)
    suffix = path.suffix.lower()
    readers = {'.xlsx': read_xlsx, '.xls': read_xls, '.docx': read_docx}
    if suffix not in readers:
        raise ValueError('UNSUPPORTED_MATERIAL_TYPE: ' + suffix)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = readers[suffix](path)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    if before != after:
        raise RuntimeError('SOURCE_CHANGED_DURING_READ')
    result['source'] = str(path)
    result['sha256'] = before
    result['status'] = 'read_with_warnings' if result['warnings'] else 'read'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = read(args.input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {'status': result['status'], 'kind': result['kind'],
               'sha256': result['sha256'], 'warnings': [x['code'] for x in result['warnings']]}
    if 'sheets' in result:
        summary['effective_rows'] = {s['name']: s['effective_row_count'] for s in result['sheets']}
    else:
        summary['blocks'] = len(result['blocks'])
        summary['embedded_media'] = len(result['embedded_media'])
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    main()

"""Material reader preserves coordinates, missing formulas and image references."""
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from read_material import read


class MaterialReaderTests(unittest.TestCase):
    def test_xlsx_uses_effective_rows_and_flags_missing_formula_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.xlsx'
            workbook = Workbook()
            sheet = workbook.active
            sheet['A1'] = '名称'
            sheet['C1'] = '合并标题'
            sheet.merge_cells('C1:D1')
            sheet['B2'] = '=1+2'
            sheet['Z100'].font = Font(bold=True)
            workbook.save(path)
            result = read(path)
            self.assertEqual(result['sheets'][0]['effective_row_count'], 2)
            self.assertEqual(result['sheets'][0]['formula_cache_missing'], 1)
            self.assertEqual(result['sheets'][0]['rows'][1]['cells'][0]['cache_status'], 'missing')
            self.assertEqual(result['sheets'][0]['merged_ranges'][0]['range'], 'C1:D1')

    def test_docx_keeps_image_only_block_and_header_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            photo = root / 'sample.png'
            Image.new('RGB', (2, 2), (20, 80, 120)).save(photo)
            document = Document()
            document.add_paragraph('正文事实')
            document.add_picture(str(photo))
            document.sections[0].header.paragraphs[0].text = '页眉资料'
            document.add_table(rows=1, cols=1).cell(0, 0).text = '表格事实'
            path = root / 'sample.docx'
            document.save(path)
            result = read(path)
            self.assertEqual(len(result['embedded_media']), 1)
            self.assertEqual(result['media_reference_count'], 1)
            self.assertTrue(any(block['media_parts'] for block in result['blocks']))
            self.assertEqual(result['side_stories'][0]['text'], '页眉资料')


if __name__ == '__main__':
    unittest.main()

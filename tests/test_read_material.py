"""Material reader preserves coordinates, missing formulas and image references."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Font
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from read_material import read, main as read_main
import run as skill_run


class MaterialReaderTests(unittest.TestCase):
    def test_launcher_routes_material_to_installed_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            python = root / 'python'
            python.touch()
            (root / 'runtime.json').write_text(json.dumps({'python': str(python)}), encoding='utf-8')
            with patch.object(skill_run, 'state_root', return_value=root), \
                 patch.object(skill_run.subprocess, 'call', return_value=0) as call, \
                 patch.object(sys, 'argv', ['run.py', '--read-material', '--input', 'source.txt']):
                self.assertEqual(skill_run.main(), 0)
            command = call.call_args.args[0]
            self.assertEqual(command[0], str(python))
            self.assertTrue(command[1].endswith('read_material.py'))
            self.assertEqual(command[2:], ['--input', 'source.txt'])

    def test_text_and_markdown_keep_line_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain = root / 'notes.txt'
            plain.write_text('第一行\n\n第三行', encoding='utf-8')
            text = read(plain)
            self.assertEqual([block['line'] for block in text['blocks']], [1, 3])
            self.assertTrue(text['blocks'][1]['source_ref'].endswith('#line=3'))
            markdown = root / 'report.md'
            markdown.write_text('# 标题\n| 指标 | 数值 |\n| 收入 | 10 |', encoding='utf-8')
            result = read(markdown)
            self.assertEqual(result['blocks'][0]['level'], 1)
            self.assertEqual(result['blocks'][2]['text'], '| 收入 | 10 |')

    def test_platform_extraction_accepts_file_level_location_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / 'source.pdf'
            pdf.write_bytes(b'%PDF-1.4 fixture')
            sidecar = root / 'extract.json'
            sidecar.write_text(json.dumps({'schema_version': 1,
                'source': {'path': str(pdf)},
                'extraction': {'method': 'platform_pdf_text_or_ocr', 'platform': 'sample-agent'},
                'items': [{'locator': {'page': 1}, 'text': '第一页事实', 'method': 'pdf_text'},
                          {'text': '位置待核对的内容', 'method': 'ocr'}]}), encoding='utf-8')
            result = read(pdf, extraction=sidecar)
            self.assertEqual(result['items'][0]['source_ref'].split('#')[1], 'page=1')
            self.assertEqual(result['items'][1]['locator'], {'scope': 'file'})
            self.assertEqual(result['warnings'][0]['code'], 'SOURCE_LOCATION_UNVERIFIED')
            self.assertEqual(result['status'], 'read_with_warnings')

    def test_image_can_be_a_visual_asset_without_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'photo.png'
            Image.new('RGB', (3, 3), 'blue').save(image)
            sidecar = root / 'photo.json'
            sidecar.write_text(json.dumps({'schema_version': 1, 'source': {'material_use': 'visual_asset'},
                'extraction': {'platform': 'sample-agent'}, 'items': []}), encoding='utf-8')
            result = read(image, extraction=sidecar)
            self.assertEqual(result['material_use'], 'visual_asset')
            self.assertEqual(result['image_path'], str(image))
            self.assertEqual(result['items'], [])

    def test_hash_mismatch_and_missing_ocr_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'source.jpg'
            Image.new('RGB', (3, 3), 'white').save(image)
            with self.assertRaisesRegex(ValueError, 'OCR_REQUIRED'):
                read(image)
            sidecar = root / 'extract.json'
            payload = {'schema_version': 1, 'source': {'sha256': '0' * 64},
                       'extraction': {'method': 'ocr'}, 'items': [{'text': '文字'}]}
            sidecar.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'EXTRACTION_SOURCE_HASH_MISMATCH'):
                read(image, extraction=sidecar)
            payload['source'].pop('sha256')
            payload['items'] = []
            sidecar.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'OCR_REQUIRED'):
                read(image, extraction=sidecar)

    def test_pdf_requires_platform_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / 'source.pdf'
            pdf.write_bytes(b'%PDF-1.4 fixture')
            with self.assertRaisesRegex(ValueError, 'EXTRACTION_TOOL_UNAVAILABLE'):
                read(pdf)
            report = Path(tmp) / 'unused.json'
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(read_main(['--input', str(pdf), '--out', str(report)]), 2)
            self.assertEqual(json.loads(stdout.getvalue())['error_code'], 'EXTRACTION_TOOL_UNAVAILABLE')
            self.assertFalse(report.exists())

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

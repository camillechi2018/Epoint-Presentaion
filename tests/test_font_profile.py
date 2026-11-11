"""S4 task font policy: no cross-profile rewrite or silent fallback."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_fonts import audit
from font_profile import probe, resolve
from normalize_fonts import normalize


class FontProfileTests(unittest.TestCase):
    def test_named_profiles_and_unknown_rejection(self):
        self.assertEqual(resolve('windows')['east_asian'], 'Microsoft YaHei')
        self.assertEqual(resolve('macos')['east_asian'], 'PingFang SC')
        self.assertEqual(resolve('linux')['east_asian'], 'Noto Sans CJK SC')
        with self.assertRaisesRegex(ValueError, 'FONT_PROFILE_UNKNOWN'):
            resolve('made-up')

    def test_roundtrip_and_mismatched_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'sample.pptx'
            pres = Presentation()
            slide = pres.slides.add_slide(pres.slide_layouts[6])
            box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(1))
            box.text = '测试 ABC 123'
            pres.save(source)
            result = normalize(source, source, profile='linux')
            self.assertEqual(result['font_profile']['id'], 'linux')
            self.assertTrue(audit(source, 'linux')['passed'])
            self.assertFalse(audit(source, 'windows')['passed'])

    def test_resource_probe_is_explicit(self):
        report = probe('windows' if os.name == 'nt' else 'linux')
        self.assertIn(report['status'], ('available', 'unavailable'))
        self.assertEqual(report['error_code'] is None, report['status'] == 'available')

    def test_private_use_symbol_font_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'symbol.pptx'
            pres = Presentation()
            slide = pres.slides.add_slide(pres.slide_layouts[6])
            box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(1), Inches(1))
            run = box.text_frame.paragraphs[0].add_run()
            run.text = '\ue001'
            run.font.name = 'Wingdings'
            pres.save(source)
            normalize(source, source, profile='linux')
            check = Presentation(source)
            actual = check.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.name
            self.assertEqual(actual, 'Wingdings')

    def test_linux_gradient_text_fallback_is_task_local(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'gradient.pptx'
            pres = Presentation()
            slide = pres.slides.add_slide(pres.slide_layouts[6])
            box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
            run = box.text_frame.paragraphs[0].add_run()
            run.text = 'Gradient title'
            a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
            props = run._r.get_or_add_rPr()
            gradient = etree.SubElement(props, f'{{{a}}}gradFill')
            stops = etree.SubElement(gradient, f'{{{a}}}gsLst')
            for position, color in ((0, '2D90F2'), (100000, 'FFFFFF')):
                stop = etree.SubElement(stops, f'{{{a}}}gs', pos=str(position))
                etree.SubElement(stop, f'{{{a}}}srgbClr', val=color)
            pres.save(source)
            windows = Path(folder) / 'windows.pptx'
            linux = Path(folder) / 'linux.pptx'
            self.assertEqual(normalize(source, windows, profile='windows')['gradient_text_fallbacks'], 0)
            self.assertEqual(normalize(source, linux, profile='linux')['gradient_text_fallbacks'], 1)
            self.assertIsNotNone(Presentation(windows).slides[0].shapes[0]
                                 .text_frame.paragraphs[0].runs[0]._r.rPr.find(f'{{{a}}}gradFill'))
            solid = (Presentation(linux).slides[0].shapes[0]
                     .text_frame.paragraphs[0].runs[0]._r.rPr.find(f'{{{a}}}solidFill'))
            self.assertEqual(solid.find(f'{{{a}}}srgbClr').get('val'), 'FFFFFF')

    def test_linux_materializes_inherited_gradient_fill(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'inherited.pptx'
            pres = Presentation()
            slide = pres.slides.add_slide(pres.slide_layouts[6])
            box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
            box.text = 'EPOINT'
            a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
            style = box._element.txBody.find(f'{{{a}}}lstStyle')
            level = etree.SubElement(style, f'{{{a}}}lvl1pPr')
            default = etree.SubElement(level, f'{{{a}}}defRPr')
            gradient = etree.SubElement(default, f'{{{a}}}gradFill')
            stops = etree.SubElement(gradient, f'{{{a}}}gsLst')
            stop = etree.SubElement(stops, f'{{{a}}}gs', pos='100000')
            etree.SubElement(stop, f'{{{a}}}srgbClr', val='FFFFFF')
            pres.save(source)
            output = Path(folder) / 'linux.pptx'
            result = normalize(source, output, profile='linux')
            self.assertGreaterEqual(result['gradient_text_fallbacks'], 2)
            run = Presentation(output).slides[0].shapes[0].text_frame.paragraphs[0].runs[0]
            solid = run._r.rPr.find(f'{{{a}}}solidFill')
            self.assertEqual(solid.find(f'{{{a}}}srgbClr').get('val'), 'FFFFFF')


if __name__ == '__main__':
    unittest.main()

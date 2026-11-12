"""Embedded fonts must not survive task-copy normalization or break PPTX editing."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from embedded_fonts import inspect, strip
from audit_fonts import audit
from normalize_fonts import normalize

P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'


def with_embedded_font(path):
    deck = Presentation()
    deck.slides.add_slide(deck.slide_layouts[6]).shapes.add_textbox(
        0, 0, 1000000, 300000).text = '可编辑标题'
    deck.save(path)
    candidate = path.with_name('injected.pptx')
    with ZipFile(path) as original, ZipFile(candidate, 'w') as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == 'ppt/presentation.xml':
                root = etree.fromstring(data)
                fonts = etree.SubElement(root, f'{{{P}}}embeddedFontLst')
                entry = etree.SubElement(fonts, f'{{{P}}}embeddedFont')
                etree.SubElement(entry, f'{{{P}}}font', typeface='Test Font')
                etree.SubElement(entry, f'{{{P}}}regular', {f'{{{R}}}id': 'rIdFontTest'})
                data = etree.tostring(root, encoding='UTF-8', xml_declaration=True)
            elif info.filename == 'ppt/_rels/presentation.xml.rels':
                root = etree.fromstring(data)
                etree.SubElement(root, f'{{{REL}}}Relationship',
                                 Id='rIdFontTest', Type=f'{R}/font', Target='fonts/font1.fntdata')
                data = etree.tostring(root, encoding='UTF-8', xml_declaration=True)
            elif info.filename == '[Content_Types].xml':
                root = etree.fromstring(data)
                etree.SubElement(root, f'{{{CT}}}Override',
                                 PartName='/ppt/fonts/font1.fntdata',
                                 ContentType='application/x-fontdata')
                data = etree.tostring(root, encoding='UTF-8', xml_declaration=True)
            output.writestr(info, data)
        output.writestr('ppt/fonts/font1.fntdata', b'embedded font data')
        output.writestr('ppt/fonts/font2.fntdata', b'orphan font data')
    candidate.replace(path)


class EmbeddedFontTests(unittest.TestCase):
    def test_remove_orphan_font_metadata_without_font_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.pptx'
            output = Path(directory) / 'clean.pptx'
            with_embedded_font(source)
            orphan = source.with_name('orphan.pptx')
            with ZipFile(source) as original, ZipFile(orphan, 'w') as rewritten:
                for info in original.infolist():
                    if not info.filename.startswith('ppt/fonts/'):
                        rewritten.writestr(info, original.read(info.filename))
            orphan.replace(source)
            self.assertEqual(inspect(source)['font_parts'], 0)
            result = strip(source, output)
            self.assertEqual(result['after']['font_entries'], 0)
            self.assertEqual(result['after']['font_relationships'], 0)
            self.assertEqual(result['after']['font_content_types'], 0)

    def test_remove_font_parts_and_all_package_references(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.pptx'
            output = root / 'without-fonts.pptx'
            with_embedded_font(source)
            result = strip(source, output)
            self.assertEqual(result['before']['font_parts'], 2)
            self.assertEqual(result['after']['font_parts'], 0)
            self.assertEqual(result['after']['font_relationships'], 0)
            self.assertEqual(result['after']['font_content_types'], 0)
            self.assertEqual(Presentation(output).slides[0].shapes[0].text, '可编辑标题')
            self.assertEqual(inspect(source)['font_parts'], 2)

    def test_normalize_task_copy_references_platform_fonts_without_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.pptx'
            output = Path(directory) / 'normalized.pptx'
            with_embedded_font(source)
            result = normalize(source, output, profile='windows')
            self.assertEqual(result['embedded_font_parts_removed'], 2)
            self.assertEqual(inspect(output)['font_parts'], 0)
            self.assertEqual(Presentation(output).slides[0].shapes[0].text, '可编辑标题')
            self.assertTrue(audit(output, 'windows')['passed'])


if __name__ == '__main__':
    unittest.main()

"""S2 pilot stays limited to two native one-slide presentations."""
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from pptx import Presentation
from lxml import etree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import P, assemble


class NativePilotTests(unittest.TestCase):
    def test_two_native_text_pages_remain_editable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = []
            for number, content in enumerate(('目录', '章节'), 1):
                deck = Presentation()
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                slide.shapes.add_textbox(0, 0, 1000000, 300000).text = content
                path = root / f'page{number}.pptx'
                deck.save(path)
                inputs.append(path)
            output = root / 'joined.pptx'
            summary = assemble(*inputs, output)
            assembled = Presentation(output)
            self.assertEqual(summary['registered_masters'], 2)
            self.assertEqual([slide.shapes[0].text for slide in assembled.slides], ['目录', '章节'])
            with ZipFile(output) as archive:
                ids = [int(node.attrib['id'])
                       for name in archive.namelist()
                       if name.startswith('ppt/slideMasters/') and name.endswith('.xml')
                       for node in ET.fromstring(archive.read(name)).iter('{' + P + '}sldLayoutId')]
            self.assertEqual(len(ids), len(set(ids)))

    def test_second_slide_notes_use_one_registered_notes_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for number in (1, 2):
                deck = Presentation()
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                slide.notes_slide.notes_text_frame.text = f'note {number}'
                path = root / f'note{number}.pptx'
                deck.save(path)
                paths.append(path)
            output = root / 'joined.pptx'
            assemble(*paths, output)
            with ZipFile(output) as archive:
                note_masters = [name for name in archive.namelist()
                                if name.startswith('ppt/notesMasters/') and name.endswith('.xml')]
                note_slides = [name for name in archive.namelist()
                               if name.startswith('ppt/notesSlides/') and name.endswith('.xml')]
            self.assertEqual(len(note_masters), 1)
            self.assertEqual(len(note_slides), 2)

    def test_multi_slide_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deck = Presentation()
            deck.slides.add_slide(deck.slide_layouts[6])
            deck.slides.add_slide(deck.slide_layouts[6])
            input_path = root / 'two.pptx'
            deck.save(input_path)
            with self.assertRaisesRegex(ValueError, 'EXPECTED_ONE_SOURCE_SLIDE'):
                assemble(input_path, input_path, root / 'joined.pptx')


if __name__ == '__main__':
    unittest.main()

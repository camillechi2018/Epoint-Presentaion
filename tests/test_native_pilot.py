"""S2 pilot stays limited to two native one-slide presentations."""
import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import assemble


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

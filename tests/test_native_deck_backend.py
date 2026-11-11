"""Native finalization must stamp slide relationship order, not XML filenames."""
import sys
import tempfile
import unittest
from pathlib import Path

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import assemble_many
from native_deck_backend import _basic_package_audit, stamp_source_pages


class NativeDeckBackendTests(unittest.TestCase):
    def test_stamps_all_pages_in_presentation_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = []
            records = []
            for number in range(4):
                deck = Presentation()
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                slide.shapes.add_textbox(0, 0, 1000000, 300000).text = f'page {number}'
                path = root / f'page-{number}.pptx'
                deck.save(path)
                inputs.append(path)
                records.append({'source_stamp': f'epoint:fixture:{number}'})
            output = root / 'joined.pptx'
            assemble_many(inputs, output)
            stamp_source_pages(output, records)
            self.assertTrue(_basic_package_audit(output)['passed'])
            names = [slide._element.cSld.get('name') for slide in Presentation(output).slides]
            self.assertEqual(names, [f'epoint:fixture:{n}:{n + 1}' for n in range(4)])


if __name__ == '__main__':
    unittest.main()

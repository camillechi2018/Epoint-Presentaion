"""Native finalization must stamp slide relationship order, not XML filenames."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import assemble_many
from native_deck_backend import _basic_package_audit, _render, assemble_and_check, stamp_source_pages


class NativeDeckBackendTests(unittest.TestCase):
    def test_mac_renderer_requires_manual_target_application_review(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('native_deck_backend.platform.system', return_value='Darwin'), \
             patch('native_deck_backend.shutil.which', side_effect=AssertionError('LibreOffice called')):
            result = _render(Path(directory) / 'candidate.pptx', Path(directory) / 'rendered')
        self.assertEqual(result['status'], 'pending_manual')
        self.assertEqual(result['error_code'], 'MAC_RENDERER_MANUAL_REQUIRED')

    def test_render_failure_keeps_assembled_and_audited_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for number in range(2):
                deck = Presentation()
                slide = deck.slides.add_slide(deck.slide_layouts[6])
                slide.shapes.add_textbox(0, 0, 1000000, 300000).text = f'page {number}'
                path = root / f'page-{number}.pptx'
                deck.save(path)
                sources.append({'path': str(path), 'source_stamp': None})
            output = root / 'candidate.pptx'
            assembly = {'slides': sources, 'font_profile': 'windows', 'theme': 'blue'}
            with patch('native_deck_backend.normalize'), \
                 patch('native_deck_backend.audit_colors', return_value={'passed': True}), \
                 patch('native_deck_backend.repair_svg', return_value={'passed': True}), \
                 patch('native_deck_backend.audit_fonts', return_value={'passed': True}), \
                 patch('native_deck_backend.audit_logo', return_value={'passed': True}), \
                 patch('native_deck_backend.check_finished', return_value={'status': 'passed'}), \
                 patch('native_deck_backend._render', side_effect=RuntimeError('LibreOffice failed')):
                result = assemble_and_check(assembly, root / 'assembly.json', output, {}, root / 'rendered')
            self.assertTrue(output.is_file())
            self.assertEqual(result['finished']['status'], 'passed')
            self.assertEqual(result['render']['status'], 'failed')
            self.assertTrue(output.with_suffix('.render.json').is_file())

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

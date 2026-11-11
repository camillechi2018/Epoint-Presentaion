"""Essential S3 delivery examples: one complete deck and core rejection cases."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from pptx import Presentation

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from assemble_native import assemble_many
from audit_deck import audit as audit_deck
from delivery_gate import check_structure, check_prefilled, check_finished, check_package_relations


class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        (self.library / 'sources').mkdir(parents=True)
        self.commit = 'a' * 40
        self.pages = []
        self.slides = []
        entries = []
        files = {}
        for role in ('cover', 'directory', 'section', 'closing'):
            layout = 'fixture-' + role
            relative = 'sources/' + layout + '.pptx'
            source = self.library / relative
            deck = Presentation()
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            slide.shapes.add_textbox(0, 0, 1000000, 300000).text = role
            deck.save(source)
            files[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
            stamp = f'epoint:{layout}:blue:{relative}:1:{self.commit}'
            slide._element.cSld.set('name', stamp)
            filled = self.root / (layout + '-filled.pptx')
            deck.save(filled)
            entries.append({'id': layout, 'role': role, 'source': relative,
                            'source_page': 1, 'themes': ['blue']})
            self.pages.append({'role': role, 'layout_id': layout,
                               'selection_mode': 'source_template', 'source_stamp': stamp})
            self.slides.append({'path': str(filled), 'role': role,
                                'layout_id': layout, 'source_stamp': stamp})
        catalog = self.library / 'catalog.json'
        catalog.write_text(json.dumps({'layouts': entries}), encoding='utf-8')
        files['catalog.json'] = hashlib.sha256(catalog.read_bytes()).hexdigest()
        (self.library / 'knowledge-manifest.json').write_text(json.dumps({
            'source_commit': self.commit, 'files': files, 'file_count': len(files)
        }), encoding='utf-8')
        self.assembly = {'theme': 'blue', 'library_commit': self.commit,
                         'complete_deck': True, 'pages': self.pages, 'slides': self.slides}

    def finished(self):
        path = self.root / 'finished.pptx'
        assemble_many([Path(item['path']) for item in self.slides], path)
        deck = Presentation(path)
        for index, (page, slide) in enumerate(zip(self.pages, deck.slides), 1):
            slide._element.cSld.set('name', page['source_stamp'] + ':' + str(index))
        deck.save(path)
        return path

    def test_complete_source_backed_deck_passes(self):
        prefilled = check_prefilled(self.assembly, self.library)
        finished = check_finished(self.finished(), self.assembly, prefilled)
        self.assertEqual(finished['source_associations'], 4)
        self.assertGreater(finished['package']['internal_relations'], 0)

    def test_missing_directory_and_mixed_section_are_rejected(self):
        missing = [page for page in self.pages if page['role'] != 'directory']
        with self.assertRaisesRegex(ValueError, 'COMPLETE_DECK_STRUCTURE_MISSING'):
            check_structure(missing)
        missing_section = [page for page in self.pages if page['role'] != 'section']
        with self.assertRaisesRegex(ValueError, 'COMPLETE_DECK_STRUCTURE_MISSING'):
            check_structure(missing_section)
        drawn = [dict(page) for page in self.pages]
        drawn[0]['selection_mode'] = 'guided_composition'
        with self.assertRaisesRegex(ValueError, 'STRUCTURE_SOURCE_REQUIRED'):
            check_structure(drawn)
        mixed = self.pages[:3] + [dict(self.pages[2], layout_id='different')] + self.pages[3:]
        with self.assertRaisesRegex(ValueError, 'SECTION_LAYOUT_MIXED'):
            check_structure(mixed)

    def test_catalog_mismatch_is_rejected_before_assembly(self):
        forged = dict(self.assembly, pages=[dict(page) for page in self.pages],
                      slides=[dict(slide) for slide in self.slides])
        forged['pages'][0]['source_stamp'] = forged['pages'][0]['source_stamp'].replace(':1:', ':2:')
        forged['slides'][0]['source_stamp'] = forged['pages'][0]['source_stamp']
        with self.assertRaisesRegex(ValueError, 'SOURCE_STAMP_NOT_CATALOG_BOUND'):
            check_prefilled(forged, self.library)

    def test_missing_package_target_and_wrong_final_page_are_rejected(self):
        prefilled = check_prefilled(self.assembly, self.library)
        path = self.finished()
        deck = Presentation(path)
        deck.slides[1]._element.cSld.set('name', 'epoint:forged')
        deck.save(path)
        with self.assertRaisesRegex(ValueError, 'FINISHED_SOURCE_ASSOCIATION_MISMATCH'):
            check_finished(path, self.assembly, prefilled)
        with ZipFile(path) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        target = next(name for name in files if name.startswith('ppt/slideLayouts/') and name.endswith('.xml'))
        bad = self.root / 'missing-layout.pptx'
        with ZipFile(bad, 'w', ZIP_DEFLATED) as archive:
            for name, data in files.items():
                if name != target:
                    archive.writestr(name, data)
        with self.assertRaisesRegex(ValueError, 'RELATION_TARGET_MISSING'):
            check_package_relations(bad)

    def test_independent_deck_audit_rejects_missing_structure(self):
        path = self.finished()
        plan = self.root / 'audit-plan.json'
        data = {'theme': 'blue', 'library_commit': self.commit,
                'complete_deck': True, 'pages': self.pages[:1] + self.pages[2:]}
        plan.write_text(json.dumps(data), encoding='utf-8')
        result = audit_deck(plan, path)
        self.assertFalse(result['p0_passed'])
        self.assertIn('complete_deck_roles', {issue['code'] for issue in result['issues']})


if __name__ == '__main__':
    unittest.main()

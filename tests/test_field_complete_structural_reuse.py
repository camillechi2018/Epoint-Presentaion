import json
import sys
import unittest
from pathlib import Path

ROOT = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from plan_deck import eligible, matches_structural_contract


class FieldCompleteStructuralReuseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
        cls.ready = [entry for entry in catalog['layouts']
                     if entry.get('matching_activation') == 'structure_ready']

    def test_all_ready_components_accept_complete_fields_without_source_business_relation(self):
        self.assertTrue(self.ready)
        for entry in self.ready:
            with self.subTest(entry=entry['id']):
                contract = entry['matching_contract']
                content = {'type': 'template_fields', 'structure_type': contract['structure_type'],
                           'texts': {path: '说明' for path in contract['required_binding_paths']}}
                page = {'role': 'body', 'title': '跨业务材料', 'content': content,
                        'theme': 'deep-blue-tech' if entry['id'].startswith('content-tech-') else 'blue'}
                self.assertTrue(matches_structural_contract(entry, page, {}))
                request = {'_root': ROOT, 'allow_draft': True, 'allow_visual_reviewed': True,
                           'theme': page['theme'], 'style_family': entry.get('style_family')}
                self.assertEqual(eligible(entry, page, request, {}), [])
                key = contract['required_binding_paths'][0]
                del content['texts'][key]
                self.assertFalse(matches_structural_contract(entry, page, {}))

    def test_special_pages_do_not_enter_complete_field_route(self):
        catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
        for layout_id in ('content-blue-231', 'content-blue-247', 'content-tech-031',
                          'content-blue-025', 'content-blue-070'):
            entry = next(x for x in catalog['layouts'] if x['id'] == layout_id)
            with self.subTest(entry=layout_id):
                self.assertNotEqual(entry['matching_policy'], 'structural')
                self.assertNotEqual(entry.get('matching_activation'), 'structure_ready')


if __name__ == '__main__':
    unittest.main()

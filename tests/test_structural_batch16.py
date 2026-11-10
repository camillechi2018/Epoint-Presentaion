"""B-stage opt-in contracts for generic stage matrix and two-phase plan."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content_adapters import adapt_for_layout
from plan_deck import binding_gap, eligible
from relation_match import load_taxonomy

LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')


def sample(layout_id):
    if layout_id == 'content-blue-180':
        return {'type': 'stage_matrix', 'order': 'left_to_right',
                'items': [{'title': f'阶段{i}', 'label': f'{i:02d}',
                           'highlights': [{'title': '任务甲', 'body': f'完成第{i}阶段核对。'},
                                          {'title': '任务乙', 'body': f'形成第{i}阶段记录。'}]}
                          for i in range(1, 5)]}
    return {'type': 'two_phase_plan', 'order': 'left_to_right',
            'summary': '分两阶段落实十项工作',
            'items': [{'title': '准备阶段', 'issues': [f'准备任务{i}' for i in range(1, 6)]},
                      {'title': '实施阶段', 'issues': [f'实施任务{i}' for i in range(1, 6)]}]}


class StructuralBatch16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_valid_generic_content_reaches_template_without_gap(self):
        for layout_id in ('content-blue-180', 'content-tech-028'):
            with self.subTest(layout=layout_id):
                entry = self.entries[layout_id]
                content = sample(layout_id)
                adapted, adapter = adapt_for_layout(layout_id, content, '项目实施安排')
                self.assertIsNotNone(adapter)
                self.assertTrue(adapted['texts'])
                self.assertEqual(binding_gap(entry, {'content': content, 'title': '项目实施安排'},
                                             LIBRARY, entry['themes'][0]), 0)
                page = {'role': 'body', 'title': '项目实施安排', 'information_relation': 'process',
                        'content': content, 'needs': {'item_count': len(content['items'])}}
                reasons = eligible(entry, page, {'_root': LIBRARY, 'allow_draft': True,
                                                 'theme': entry['themes'][0]}, self.taxonomy)
                self.assertNotIn('structure_contract', reasons)
                self.assertNotIn('semantic_invariant', reasons)

    def test_missing_facts_are_rejected(self):
        matrix = sample('content-blue-180')
        matrix['items'][0]['highlights'].pop()
        self.assertIsNone(adapt_for_layout('content-blue-180', matrix, '项目实施安排')[1])
        phases = sample('content-tech-028')
        phases['items'][1]['issues'].pop()
        self.assertIsNone(adapt_for_layout('content-tech-028', phases, '项目实施安排')[1])
        phases = sample('content-tech-028')
        phases.pop('summary')
        self.assertIsNone(adapt_for_layout('content-tech-028', phases, '项目实施安排')[1])

    def test_wrong_order_and_count_do_not_match(self):
        for layout_id in ('content-blue-180', 'content-tech-028'):
            entry = self.entries[layout_id]
            content = sample(layout_id)
            content['order'] = 'unordered'
            self.assertIsNone(adapt_for_layout(layout_id, content, '项目实施安排')[1])
            content['order'] = 'left_to_right'
            content['items'].pop()
            self.assertIsNone(adapt_for_layout(layout_id, content, '项目实施安排')[1])


if __name__ == '__main__':
    unittest.main()

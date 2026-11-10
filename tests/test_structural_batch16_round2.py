"""Cross-scenario contracts for six-month timeline and six-step process."""
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
    if layout_id == 'content-blue-204':
        return {'type': 'monthly_timeline', 'order': 'chronological',
                'items': [{'month': f'{i}月', 'title': f'任务{i}', 'body': f'完成第{i}项工作。'}
                          for i in range(1, 7)]}
    return {'type': 'serpentine_process', 'order': 'serpentine', 'center_title': '工作闭环',
            'items': [{'title': f'步骤{i}', 'goal': f'目标{i}', 'body': f'完成第{i}步工作。'}
                      for i in range(1, 7)]}


class StructuralBatch16Round2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_valid_structure_is_eligible_and_fillable(self):
        for layout_id, relation in (('content-blue-204', 'timeline'),
                                    ('content-blue-240', 'process')):
            with self.subTest(layout=layout_id):
                entry, content = self.entries[layout_id], sample(layout_id)
                adapted, adapter = adapt_for_layout(layout_id, content, '项目推进安排')
                self.assertIsNotNone(adapter)
                self.assertEqual(binding_gap(entry, {'title': '项目推进安排', 'content': content},
                                             LIBRARY, 'blue'), 0)
                page = {'role': 'body', 'title': '项目推进安排', 'information_relation': relation,
                        'content': content, 'needs': {'item_count': 6}}
                for theme in ('blue', 'red'):
                    reasons = eligible(entry, page, {'_root': LIBRARY, 'allow_draft': True,
                                                     'theme': theme}, self.taxonomy)
                    self.assertEqual(reasons, [])

    def test_calendar_and_sequence_cannot_be_faked(self):
        monthly = sample('content-blue-204')
        monthly['items'][2]['month'] = '8月'
        self.assertIsNone(adapt_for_layout('content-blue-204', monthly, '项目推进安排')[1])
        monthly = sample('content-blue-204')
        monthly['items'].pop()
        self.assertIsNone(adapt_for_layout('content-blue-204', monthly, '项目推进安排')[1])
        snake = sample('content-blue-240')
        snake['order'] = 'unordered'
        self.assertIsNone(adapt_for_layout('content-blue-240', snake, '项目推进安排')[1])
        snake = sample('content-blue-240')
        snake.pop('center_title')
        self.assertIsNone(adapt_for_layout('content-blue-240', snake, '项目推进安排')[1])
        snake = sample('content-blue-240')
        snake['items'][4].pop('goal')
        self.assertIsNone(adapt_for_layout('content-blue-240', snake, '项目推进安排')[1])


if __name__ == '__main__':
    unittest.main()

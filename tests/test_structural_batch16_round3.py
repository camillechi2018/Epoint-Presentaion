"""Validate reusable quarter and consecutive-month structures."""
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
    if layout_id == 'content-blue-207':
        return {'type': 'quarter_cycle', 'order': 'clockwise',
                'center_title': '全年培训计划',
                'items': [{'quarter': f'第{x}季度', 'title': f'任务{i}',
                           'body': f'完成第{i}项工作。'}
                          for i, x in enumerate('一二三四', 1)]}
    return {'type': 'monthly_roadmap', 'order': 'chronological',
            'items': [{'date': f'2026年{i}月', 'title': f'任务{i}',
                       'body': f'完成第{i}项工作。'} for i in range(1, 7)]}


class StructuralBatch16Round3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_generic_content_is_eligible(self):
        for layout_id in ('content-blue-207', 'content-blue-214'):
            with self.subTest(layout=layout_id):
                entry, content = self.entries[layout_id], sample(layout_id)
                adapted, adapter = adapt_for_layout(layout_id, content, '项目安排')
                self.assertIsNotNone(adapter)
                self.assertEqual(binding_gap(entry, {'title': '项目安排', 'content': content},
                                             LIBRARY, 'blue'), 0)
                page = {'role': 'body', 'title': '项目安排',
                        'information_relation': 'timeline', 'content': content,
                        'needs': {'item_count': len(content['items'])}}
                for theme in ('blue', 'red'):
                    self.assertEqual(eligible(entry, page, {'_root': LIBRARY,
                                     'allow_draft': True, 'theme': theme}, self.taxonomy), [])

    def test_invalid_calendar_and_quarter_structure_rejected(self):
        for layout_id in ('content-blue-207', 'content-blue-214'):
            content = sample(layout_id)
            content['items'].pop()
            self.assertIsNone(adapt_for_layout(layout_id, content, '项目安排')[1])
        quarter = sample('content-blue-207')
        quarter['items'][1]['quarter'] = '第四季度'
        self.assertIsNone(adapt_for_layout('content-blue-207', quarter, '项目安排')[1])
        quarter = sample('content-blue-207')
        quarter.pop('center_title')
        self.assertIsNone(adapt_for_layout('content-blue-207', quarter, '项目安排')[1])
        months = sample('content-blue-214')
        months['items'][3]['date'] = '2026年8月'
        self.assertIsNone(adapt_for_layout('content-blue-214', months, '项目安排')[1])
        months = sample('content-blue-214')
        months['order'] = 'unordered'
        self.assertIsNone(adapt_for_layout('content-blue-214', months, '项目安排')[1])
        months = sample('content-blue-214')
        months['items'] = [{'date': f'2026年{i}月', 'title': f'任务{i}',
                            'body': f'完成第{i}项工作。'} for i in range(7, 13)]
        self.assertIsNone(adapt_for_layout('content-blue-214', months, '项目安排')[1])


if __name__ == '__main__':
    unittest.main()

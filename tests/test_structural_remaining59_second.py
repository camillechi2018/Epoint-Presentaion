"""A six-row schedule and five-part framework use only input facts."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from content_adapters import adapt_for_layout
from plan_deck import binding_gap, eligible
from relation_match import load_taxonomy

LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')


class Remaining59SecondTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_generic_content_matches_and_fills(self):
        schedule = {
            'type': 'schedule', 'order': 'chronological', 'summary': '按时间安排现场检查',
            'column_labels': {'time': '时间', 'activity': '事项', 'owner': '负责组'},
            'items': [{'time': f'{9+i:02d}:00-{10+i:02d}:00',
                       'activity': f'检查事项{i+1}', 'owner': f'第{i+1}组'} for i in range(6)],
        }
        framework = {
            'type': 'framework', 'summary': '五项工作共同保障质量', 'unit': '项保障',
            'items': [{'title': f'保障{i+1}', 'body': f'落实第{i+1}项工作。'} for i in range(5)],
        }
        for layout_id, relation, content in (
            ('schedule-tech-069', 'timeline', schedule),
            ('content-tech-016', 'framework', framework),
        ):
            with self.subTest(layout=layout_id):
                adapted, adapter = adapt_for_layout(layout_id, content, '项目质量计划')
                self.assertIsNotNone(adapter)
                self.assertTrue(adapted['texts'])
                self.assertEqual(binding_gap(self.entries[layout_id],
                                 {'title': '项目质量计划', 'content': content}, LIBRARY,
                                 'deep-blue-tech'), 0)
                page = {'role': 'body', 'title': '项目质量计划', 'content': content,
                        'information_relation': relation,
                        'needs': {'item_count': len(content['items'])}}
                self.assertEqual(eligible(self.entries[layout_id], page,
                                 {'_root': LIBRARY, 'allow_draft': True,
                                  'theme': 'deep-blue-tech', 'style_family': 'deep-blue-tech'},
                                 self.taxonomy), [])
        self.assertEqual(adapt_for_layout('content-tech-016', framework, '项目质量计划')[0]
                         ['texts']['center.count'], '5')

    def test_missing_fields_and_invalid_time_order_reject(self):
        valid = {'type': 'schedule', 'order': 'chronological', 'summary': '日程',
                 'column_labels': {'time': '时间', 'activity': '事项', 'owner': '负责组'},
                 'items': [{'time': f'{9+i:02d}:00-{10+i:02d}:00',
                            'activity': f'任务{i}', 'owner': f'组{i}'} for i in range(6)]}
        valid['items'][1]['time'] = '08:00-09:00'
        self.assertIsNone(adapt_for_layout('schedule-tech-069', valid, '日程')[1])
        valid['items'][1]['time'] = '10:00-11:00'
        valid['items'][0].pop('owner')
        self.assertIsNone(adapt_for_layout('schedule-tech-069', valid, '日程')[1])
        framework = {'type': 'framework', 'summary': '说明', 'unit': '项',
                     'items': [{'title': '措施', 'body': '说明'} for _ in range(4)]}
        self.assertIsNone(adapt_for_layout('content-tech-016', framework, '计划')[1])


if __name__ == '__main__':
    unittest.main()

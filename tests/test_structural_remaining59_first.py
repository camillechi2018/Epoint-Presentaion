"""The first three layouts from the remaining structural pool accept only true relations."""
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
    if layout_id == 'content-blue-261':
        return {'type': 'cycle', 'order': 'clockwise', 'center_title': '服务闭环',
                'items': [{'title': f'任务{i}', 'body': f'完成第{i}步。'} for i in range(1, 7)]}
    if layout_id == 'content-blue-266':
        return {'type': 'process', 'order': 'serpentine',
                'items': [{'title': f'任务{i}', 'body': f'完成第{i}步。'} for i in range(1, 7)]}
    return {'type': 'hierarchy', 'order': 'bottom_to_top',
            'summary': '三层保障', 'left_support': '制度支持', 'right_support': '反馈机制',
            'items': [{'body': f'第{i}层保障'} for i in range(1, 4)]}


class Remaining59FirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_generic_cases_fit_blue_red_and_tech(self):
        cases = [('content-blue-261', 'cycle', ('blue', 'red')),
                 ('content-blue-266', 'process', ('blue', 'red')),
                 ('content-tech-018', 'framework', ('deep-blue-tech',))]
        for layout_id, relation, themes in cases:
            with self.subTest(layout=layout_id):
                content = sample(layout_id)
                adapted, adapter = adapt_for_layout(layout_id, content, '项目安排')
                self.assertIsNotNone(adapter)
                self.assertEqual(binding_gap(self.entries[layout_id],
                                 {'title': '项目安排', 'content': content}, LIBRARY, themes[0]), 0)
                page = {'role': 'body', 'title': '项目安排', 'content': content,
                        'information_relation': relation,
                        'needs': {'item_count': len(content['items'])}}
                for theme in themes:
                    self.assertEqual(eligible(self.entries[layout_id], page,
                                     {'_root': LIBRARY, 'allow_draft': True,
                                      'theme': theme,
                                      'style_family': self.entries[layout_id].get('style_family')}, self.taxonomy), [])
        adapted, _ = adapt_for_layout('content-blue-261', sample('content-blue-261'), '项目安排')
        self.assertEqual(adapted['texts']['center.title'], '服务\n闭环')

    def test_incomplete_or_unordered_content_is_rejected(self):
        for layout_id in ('content-blue-261', 'content-blue-266', 'content-tech-018'):
            with self.subTest(layout=layout_id):
                content = sample(layout_id)
                content['items'].pop()
                self.assertIsNone(adapt_for_layout(layout_id, content, '项目安排')[1])
                content = sample(layout_id)
                content['order'] = 'unordered'
                self.assertIsNone(adapt_for_layout(layout_id, content, '项目安排')[1])
        content = sample('content-tech-018')
        content.pop('right_support')
        self.assertIsNone(adapt_for_layout('content-tech-018', content, '项目安排')[1])


if __name__ == '__main__':
    unittest.main()

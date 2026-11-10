"""Regression for activated cross-scenario body layouts."""
import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from content_adapters import adapt_for_layout
from plan_deck import binding_gap, eligible
from relation_match import load_taxonomy


LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')


def sample(layout_id):
    items = [{'title': f'任务{i}', 'body': f'完成第{i}项工作。'} for i in range(1, 5)]
    if layout_id == 'content-blue-060':
        return {'type': 'process', 'goal': '逐项完成建设任务',
                'items': [dict(item, outcome=f'形成第{i}项成果') for i, item in enumerate(items, 1)]}
    if layout_id == 'content-blue-267':
        return {'type': 'process', 'items': items}
    if layout_id == 'content-tech-026':
        return {'type': 'comparison', 'summary': '比较四项安排', 'items': items}
    if layout_id == 'content-tech-029':
        return {'type': 'comparison', 'summary': '比较两项安排', 'conclusion': '两项安排各有适用范围',
                'items': items[:2]}
    if layout_id == 'content-tech-040':
        return {'type': 'comparison', 'summary': '比较两项安排',
                'items': [dict(item, tags=['重点一', '重点二']) for item in items[:2]]}
    if layout_id == 'content-tech-033':
        return {'type': 'cards', 'summary': '说明五项工作', 'conclusion': '五项任务协同推进',
                'items': items + [{'title': '任务5', 'body': '完成第5项工作。'}]}
    if layout_id == 'content-tech-054':
        return {'type': 'process', 'summary': '按顺序推进四项任务', 'items': items}
    if layout_id == 'content-tech-034':
        return {'type': 'cards', 'summary': '说明五项工作',
                'items': items + [{'title': '任务5', 'body': '完成第5项工作。'}]}
    if layout_id in ('content-tech-037', 'content-tech-043'):
        return {'type': 'cards', 'summary': '说明三项工作', 'items': items[:3]}
    if layout_id == 'content-tech-038':
        return {'type': 'process', 'summary': '按顺序推进四项任务', 'items': items}
    if layout_id == 'content-tech-020':
        return {'type': 'cards', 'summary': '六项工作围绕同一主题',
                'center': {'topic': '项目建设'},
                'items': [{'title': f'任务{i}'} for i in range(1, 7)]}
    if layout_id == 'content-tech-042':
        return {'type': 'cycle', 'conclusion': '四项工作形成闭环', 'items': items}
    if layout_id == 'content-tech-045':
        return {'type': 'process', 'items': items}
    if layout_id == 'content-tech-081':
        return {'type': 'hierarchy', 'order': 'top_to_bottom', 'items': items[:3]}
    if layout_id in ('content-tech-063', 'content-tech-064', 'content-tech-065'):
        dates = [f'{2025+i}年{i}月' if layout_id.endswith('065') else f'{2025+i}年'
                 for i in range(1, 6)]
        detail_key = 'title' if layout_id.endswith('064') else 'body'
        return {'type': 'milestone_timeline', 'order': 'chronological',
                'summary': '逐年推进项目建设',
                'items': [dict(label=dates[i-1], **{detail_key: (
                    f'阶段{i}' if detail_key == 'title' else f'完成第{i}项工作。')})
                          for i in range(1, 6)]}
    return {'type': 'cards', 'summary': '并列说明四项工作', 'conclusion': '四项工作协同推进',
            'items': items}


class StructuralBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.catalog = {x['id']: x for x in catalog['layouts']}
        cls.taxonomy = load_taxonomy(LIBRARY, catalog)

    def test_activated_generic_requests_have_no_binding_gaps(self):
        for layout_id in ('content-blue-060', 'content-blue-267', 'content-tech-026',
                          'content-tech-029', 'content-tech-040', 'content-tech-048',
                          'content-tech-033', 'content-tech-054', 'content-tech-063',
                          'content-tech-064', 'content-tech-065', 'content-tech-034',
                          'content-tech-037', 'content-tech-038', 'content-tech-043',
                          'content-tech-020', 'content-tech-042', 'content-tech-045',
                          'content-tech-081'):
            with self.subTest(layout_id=layout_id):
                entry = self.catalog[layout_id]
                content = sample(layout_id)
                adapted, adapter = adapt_for_layout(layout_id, content, '业务安排')
                self.assertIsNotNone(adapter)
                self.assertTrue(adapted['texts'])
                self.assertEqual(binding_gap(entry, {'content': content, 'title': '业务安排'},
                                             LIBRARY, entry['themes'][0]), 0)
                page = {'role': 'body', 'title': '业务安排', 'information_relation':
                        entry['matching_contract']['compatible_relations'][0], 'content': content,
                        'needs': {'item_count': len(content['items'])}}
                reasons = eligible(entry, page, {'_root': LIBRARY, 'allow_draft': True,
                                                'theme': entry['themes'][0]}, self.taxonomy)
                self.assertNotIn('structure_contract', reasons)
                self.assertNotIn('semantic_invariant', reasons)

    def test_missing_meaningful_field_does_not_get_invented(self):
        for layout_id, missing in (('content-blue-060', 'goal'), ('content-tech-029', 'conclusion'),
                                   ('content-tech-040', 'tags'), ('content-tech-048', 'summary')):
            with self.subTest(layout_id=layout_id):
                content = sample(layout_id)
                if missing == 'tags':
                    content['items'][0].pop('tags')
                else:
                    content.pop(missing)
                self.assertIsNone(adapt_for_layout(layout_id, content, '业务安排')[1])

    def test_four_card_title_and_body_keep_visual_order(self):
        content = sample('content-tech-048')
        adapted, _ = adapt_for_layout('content-tech-048', content, '业务安排')
        texts = adapted['texts']
        for visual_index, (title_slot, body_slot) in enumerate(zip((3, 4, 2, 1), (2, 1, 3, 4))):
            self.assertEqual(texts[f'item_{title_slot}.title'], content['items'][visual_index]['title'])
            self.assertEqual(texts[f'item_{body_slot}.body'], content['items'][visual_index]['body'])

    def test_timeline_requires_actual_chronology(self):
        entry = self.catalog['content-tech-065']
        content = sample('content-tech-065')
        content['items'][1]['label'] = '2024年2月'
        page = {'role': 'body', 'title': '建设路线', 'information_relation': 'timeline',
                'content': content, 'needs': {'item_count': 5}}
        reasons = eligible(entry, page, {'_root': LIBRARY, 'allow_draft': True,
                                        'theme': 'deep-blue-tech'}, self.taxonomy)
        self.assertIn('structure_contract', reasons)

    def test_new_fixed_structures_reject_missing_facts_or_wrong_order(self):
        for layout_id, mutate in (
            ('content-tech-042', lambda c: c.pop('conclusion')),
            ('content-tech-045', lambda c: c['items'][0].pop('body')),
            ('content-tech-081', lambda c: c.update(order='bottom_to_top')),
        ):
            with self.subTest(layout_id=layout_id):
                content = sample(layout_id)
                mutate(content)
                self.assertIsNone(adapt_for_layout(layout_id, content, '项目建设安排')[1])


if __name__ == '__main__':
    unittest.main()

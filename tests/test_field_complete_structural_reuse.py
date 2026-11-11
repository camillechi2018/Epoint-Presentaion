import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from plan_deck import eligible, matches_structural_contract, matches_structural_discovery, count_profile
from content_adapters import adapt_for_layout, structural_mapping_issue, field_source_evidence
from fill_layout import fill
from relation_match import load_taxonomy


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

    def test_all_ready_components_are_discoverable_before_field_mapping(self):
        generic_types = {'framework': 'cards', 'summary': 'cards',
                         'parallel-points': 'cards', 'process': 'process',
                         'ordered-steps': 'process', 'comparison': 'comparison',
                         'hierarchy': 'hierarchy', 'cycle': 'cycle',
                         'timeline': 'timeline', 'schedule': 'schedule',
                         'single-focus': 'single_focus'}
        for entry in self.ready:
            with self.subTest(entry=entry['id']):
                count = count_profile(entry, ROOT)[0][0]
                page = {'role': 'body', 'title': '跨业务材料',
                        'content': {'type': generic_types[entry['matching_contract']['structure_type']],
                                    'items': [{'title': f'第{i+1}项'} for i in range(count)]},
                        'needs': {'item_count': count},
                        'theme': 'deep-blue-tech' if entry['id'].startswith('content-tech-') else 'blue'}
                self.assertTrue(matches_structural_discovery(entry, page, {}, ROOT))
                request = {'_root': ROOT, 'allow_draft': True, 'allow_visual_reviewed': True,
                           'theme': page['theme'], 'style_family': entry.get('style_family')}
                self.assertEqual(eligible(entry, page, request, {}), [])
                page['content']['items'].pop()
                page['needs']['item_count'] -= 1
                self.assertFalse(matches_structural_discovery(entry, page, {}, ROOT))

    def test_generic_inputs_fill_simple_reviewed_structures(self):
        entries = {entry['id']: entry for entry in self.ready}
        cases = {
            'content-blue-143': {'type': 'cards', 'items': [
                {'title': f'服务{i}', 'body': f'服务内容{i}'} for i in range(1, 5)]},
            'content-blue-246': {'type': 'process', 'items': [
                {'title': f'环节{i}', 'body': f'工作内容{i}'} for i in range(1, 6)]},
            'content-tech-023': {'type': 'cards', 'summary': '两类情况的共同背景',
                                 'items': [{'title': '第一类', 'body': '第一类的真实说明'},
                                           {'title': '第二类', 'body': '第二类的真实说明'}]},
            'content-tech-055': {'type': 'single_focus', 'body': '以客户需求为中心持续完善服务。'},
            'content-tech-066': {'type': 'timeline', 'items': [
                {'title': f'{i}月'} for i in range(1, 8)]},
        }
        with tempfile.TemporaryDirectory() as directory:
            for layout_id, content in cases.items():
                with self.subTest(layout=layout_id):
                    payload, adapter = adapt_for_layout(layout_id, content, '服务体系', entry=entries[layout_id])
                    self.assertEqual(adapter, 'declared_structural_fields')
                    payload['theme'] = 'deep-blue-tech' if layout_id.startswith('content-tech-') else 'blue'
                    source = Path(directory) / (layout_id + '.json')
                    output = Path(directory) / (layout_id + '.pptx')
                    source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                    fill(ROOT, layout_id, source, output, allow_draft=True)
                    self.assertGreater(output.stat().st_size, 1000)

    def test_flat_bullets_do_not_recall_unmappable_special_geometry(self):
        catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
        by_id = {entry['id']: entry for entry in catalog['layouts']}
        taxonomy = load_taxonomy(ROOT, catalog)
        request = {'_root': ROOT, 'allow_draft': True, 'allow_visual_reviewed': True,
                   'theme': 'blue', 'style_family': 'legacy-blue-red'}
        page = {'role': 'body', 'title': '材料概况', 'information_relation': 'parallel-points',
                'content': {'type': 'bullets', 'items': [f'第{i}条完整事实' for i in range(6)]},
                'needs': {'item_count': 6}, 'theme': 'blue'}
        self.assertFalse(matches_structural_discovery(by_id['content-blue-244'], page, taxonomy, ROOT))
        self.assertIn('structure_contract', eligible(by_id['content-blue-244'], page, request, taxonomy))
        page['theme'] = 'deep-blue-tech'
        page['content']['items'].pop()
        page['needs']['item_count'] = 5
        request.update(theme='deep-blue-tech', style_family='deep-blue-tech')
        self.assertIn('structure_contract', eligible(by_id['content-tech-024'], page, request, taxonomy))
        page['content']['items'] = page['content']['items'][:3]
        page['needs']['item_count'] = 3
        self.assertIn('semantic_invariant', eligible(by_id['content-tech-031'], page, request, taxonomy))
        self.assertIn('data_contract', eligible(by_id['content-tech-053'], page, request, taxonomy))

    def test_explicit_heading_description_aliases_map_without_inventing_facts(self):
        entry = next(x for x in self.ready if x['id'] == 'content-blue-143')
        content = {'type': 'cards', 'items': [
            {'heading': f'服务{i}', 'description': f'第{i}项真实说明'} for i in range(1, 5)]}
        mapped, adapter = adapt_for_layout(entry['id'], content, '服务体系', entry=entry)
        self.assertEqual(adapter, 'declared_structural_fields')
        for i in range(4):
            self.assertIn(f'第{i+1}项真实说明', mapped['texts'].values())
        mapped['theme'] = 'blue'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'alias-content.json'
            output = Path(directory) / 'alias-content.pptx'
            source.write_text(json.dumps(mapped, ensure_ascii=False), encoding='utf-8')
            fill(ROOT, entry['id'], source, output, allow_draft=True)
            self.assertGreater(output.stat().st_size, 1000)

    def test_string_cards_report_missing_fields_without_crashing(self):
        entry = next(x for x in self.ready if x['id'] == 'content-tech-023')
        content = {'type': 'cards', 'summary': '共同说明', 'items': ['第一条事实', '第二条事实']}
        mapped, adapter = adapt_for_layout(entry['id'], content, '服务体系', entry=entry)
        self.assertIsNone(adapter)
        self.assertEqual(mapped, content)
        issue = structural_mapping_issue(entry, content, '服务体系')
        self.assertEqual(issue['reason_code'], 'MISSING_REQUIRED_FIELD')

    def test_text_alias_preserves_both_columns_and_rejects_extra_facts(self):
        entry = next(x for x in self.ready if x['id'] == 'content-tech-023')
        content = {'type': 'cards', 'summary': '共同说明', 'items': [
            {'heading': '甲类', 'text': '第一类真实说明'},
            {'heading': '乙类', 'text': '第二类真实说明'}]}
        mapped, adapter = adapt_for_layout(entry['id'], content, '服务体系', entry=entry)
        self.assertIsNotNone(adapter)
        self.assertEqual(mapped['texts']['left.title'], '甲类')
        self.assertEqual(mapped['texts']['right.body'], '第二类真实说明')
        content['items'][0]['extra_fact'] = '不能遗漏的额外事实'
        self.assertIsNone(adapt_for_layout(entry['id'], content, '服务体系', entry=entry)[1])
        self.assertEqual(structural_mapping_issue(entry, content, '服务体系')['reason_code'],
                         'INPUT_FACTS_UNMAPPED')

    def test_flat_strings_still_reach_a_compatible_title_only_layout(self):
        entry = next(x for x in self.ready if x['id'] == 'content-tech-066')
        content = {'type': 'bullets', 'structure_type': 'timeline',
                   'items': [f'{i}月' for i in range(1, 8)]}
        page = {'role': 'body', 'title': '进度安排', 'content': content,
                'information_relation': 'timeline', 'needs': {'item_count': 7}}
        self.assertTrue(matches_structural_discovery(entry, page, {}, ROOT))
        mapped, adapter = adapt_for_layout(entry['id'], content, page['title'], entry=entry)
        self.assertIsNotNone(adapter)
        for i in range(1, 8):
            self.assertEqual(mapped['texts'][f'milestone_{i}'], f'{i}月')

    def test_extra_required_facts_are_not_invented(self):
        entry = next(x for x in self.ready if x['id'] == 'content-blue-089')
        content = {'type': 'cards', 'items': [{'title': f'方向{i}', 'body': '真实内容'} for i in range(4)]}
        page = {'role': 'body', 'title': '发展方向', 'information_relation': 'parallel-points',
                'content': content, 'needs': {'item_count': 4}}
        self.assertTrue(matches_structural_discovery(entry, page, {}, ROOT))
        self.assertFalse(matches_structural_contract(entry, page, {}))
        self.assertIsNone(adapt_for_layout(entry['id'], content, page['title'], entry=entry)[1])

    def test_nested_schedule_fields_use_explicit_source_tasks(self):
        entry = next(x for x in self.ready if x['id'] == 'content-blue-071')
        phases = [
            {'title': f'阶段{i}', 'tasks': [
                {'heading': f'任务{i}甲', 'body': f'工作{i}甲'},
                {'heading': f'任务{i}乙', 'body': f'工作{i}乙'},
            ]} for i in range(1, 4)
        ]
        content = {'type': 'schedule', 'phases': phases}
        payload, adapter = adapt_for_layout(entry['id'], content, '工作安排', entry=entry)
        self.assertEqual(adapter, 'declared_structural_fields')
        self.assertEqual(payload['texts']['phases[0].tasks[1].body'], '工作1乙')
        self.assertEqual(set(payload['texts']), set(entry['matching_contract']['required_binding_paths']))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'schedule.json'
            output = Path(directory) / 'schedule.pptx'
            payload['theme'] = 'blue'
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            fill(ROOT, entry['id'], source, output, allow_draft=True)
            self.assertGreater(output.stat().st_size, 1000)

        phases[1]['tasks'][0].pop('body')
        incomplete, adapter = adapt_for_layout(entry['id'], content, '工作安排', entry=entry)
        self.assertIsNone(adapter)
        self.assertEqual(incomplete['type'], 'schedule')

    def test_title_only_template_rejects_unmapped_item_body(self):
        entry = next(x for x in self.ready if x['id'] == 'content-tech-066')
        content = {'type': 'timeline', 'items': [
            {'title': f'{i}月', 'body': f'{i}月发生的材料事实'} for i in range(1, 8)
        ]}
        payload, adapter = adapt_for_layout(entry['id'], content, '年度进展', entry=entry)
        self.assertIsNone(adapter)
        self.assertEqual(payload['items'], content['items'])
        issue = structural_mapping_issue(entry, content, '年度进展')
        self.assertEqual(issue['reason_code'], 'INPUT_FACTS_UNMAPPED')
        self.assertIn('unmapped_input:items[0].body', issue['paths'])
        content['items'] = [{'title': f'{i}月'} for i in range(1, 8)]
        content['summary'] = '材料中的年度结论'
        issue = structural_mapping_issue(entry, content, '年度进展')
        self.assertEqual(issue['reason_code'], 'INPUT_FACTS_UNMAPPED')
        self.assertIn('unmapped_input:summary', issue['paths'])

    def test_field_evidence_keeps_source_reference_and_ambiguity(self):
        content = {'type': 'cards', 'source_refs': ['company_intro-006'],
                   'items': [{'title': '服务', 'body': '服务内容'}]}
        mapped = {'texts': {'items[0].heading': '服务',
                            'items[0].body': '服务内容'}}
        evidence = field_source_evidence(content, mapped)
        self.assertIn('items[0].title', evidence['items[0].heading']['input_paths'])
        self.assertEqual(evidence['items[0].body']['source_refs'], ['company_intro-006'])

    def test_source_reference_metadata_is_not_treated_as_extra_copy(self):
        entry = next(x for x in self.ready if x['id'] == 'content-blue-143')
        content = {'type': 'cards', 'source_refs': ['company_intro-006'],
                   'unit_claims': ['C01'],
                   'items': [{'title': f'领域{i}', 'body': f'服务内容{i}',
                              'source_refs': ['company_intro-006']} for i in range(4)]}
        _, adapter = adapt_for_layout(entry['id'], content, '业务概览', entry=entry)
        self.assertEqual(adapter, 'declared_structural_fields')


if __name__ == '__main__':
    unittest.main()

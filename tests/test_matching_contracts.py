"""Pilot: business labels are soft for structural layouts, strict invariants stay hard."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from plan_deck import resolve, matches_structural_relation, matches_structural_contract, matches_strict_contract
from content_adapters import adapt_for_layout
from fill_layout import fill
from pptx import Presentation

LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')


@unittest.skipUnless(LIBRARY.is_dir(), 'local knowledge base unavailable')
class MatchingContracts(unittest.TestCase):
    def request(self, page):
        return {'theme': 'blue', 'allow_draft': True, 'seed': 1,
                'pages': [dict({'role': 'body', 'purpose': '验证结构匹配',
                                'theme': 'blue'}, **page)]}

    def test_four_cards_reuse_summary_without_achievement_semantics(self):
        page = {'layout_id': 'content-blue-112', 'title': '业务概览',
                'information_relation': 'parallel-points',
                'content': {'type': 'cards', 'items': [
                    {'title': '规模', 'body': '服务覆盖全国'},
                    {'title': '人才', 'body': '团队持续成长'},
                    {'title': '网络', 'body': '区域协同推进'},
                    {'title': '空间', 'body': '办公条件完善'}]}}
        plan = resolve(LIBRARY, self.request(page))
        self.assertEqual(plan['pages'][0]['layout_id'], 'content-blue-112')
        adapted, name = adapt_for_layout('content-blue-112', page['content'], page['title'])
        self.assertEqual(name, 'four_card_items_to_p112')
        self.assertEqual(adapted['texts']['items[0].body'], '服务覆盖全国')
        self.assertTrue(adapted['generic_visual'])

    def test_cycle_layout_rejects_independent_directions(self):
        content = {'type': 'directions', 'center': {'title': '服务网络'},
                   'items': [{'heading': f'区域{i}', 'body': f'服务领域{i}', 'short': f'领域{i}'}
                             for i in range(4)]}
        page = {'layout_id': 'content-blue-076', 'title': '区域布局',
                'information_relation': 'parallel-points', 'content': content}
        plan = resolve(LIBRARY, self.request(page))
        self.assertNotEqual(plan['pages'][0]['selection_mode'], 'source_template')
        self.assertGreater(plan['pages'][0]['rejected_reasons'].get('semantic_invariant', 0), 0)
        incomplete = dict(content, center={})
        self.assertIsNone(adapt_for_layout('content-blue-076', incomplete, page['title'])[1])
        self.assertNotEqual(resolve(LIBRARY, self.request(dict(page, content=incomplete)))
                            ['pages'][0]['selection_mode'], 'source_template')

    def test_five_cards_reuse_result_rows_without_achievement_label(self):
        page = {'layout_id': 'content-blue-106', 'title': '服务体系',
                'information_relation': 'parallel-points',
                'content': {'type': 'cards', 'items': [
                    {'title': f'领域{i}', 'body': f'提供服务{i}'} for i in range(5)]}}
        choice = resolve(LIBRARY, self.request(page))['pages'][0]
        self.assertEqual(choice['layout_id'], 'content-blue-106')
        adapted, name = adapt_for_layout('content-blue-106', page['content'], page['title'])
        self.assertEqual(name, 'five_card_items_to_p106')
        self.assertEqual(adapted['texts']['items[4].heading'], '领域4')
        self.assertTrue(adapted['generic_visual'])
        misleading = dict(page, information_relation='cycle')
        self.assertNotEqual(resolve(LIBRARY, self.request(misleading))['pages'][0]
                            ['selection_mode'], 'source_template')

    def test_fixed_icons_defer_generic_capability_arcs(self):
        content = {'type': 'cards', 'center': {'title': '服务\n能力'},
                   'items': [{'title': title, 'body': body} for title, body in
                             [('咨询', '提供业务咨询'), ('实施', '完成系统部署'),
                              ('运营', '保障日常运行'), ('培训', '开展人员培训')]]}
        page = {'layout_id': 'content-blue-142', 'title': '四项服务',
                'information_relation': 'parallel-points', 'content': content}
        self.assertNotEqual(resolve(LIBRARY, self.request(page))['pages'][0]
                            ['selection_mode'], 'source_template')
        adapted, name = adapt_for_layout('content-blue-142', content, page['title'])
        self.assertEqual(name, 'four_cards_with_center_to_p142')
        self.assertEqual(adapted['texts']['center.title'], '服务\n能力')
        missing = dict(page, content=dict(content, center={}))
        self.assertNotEqual(resolve(LIBRARY, self.request(missing))['pages'][0]
                            ['selection_mode'], 'source_template')

    def test_generic_visual_removes_fixed_pictograms(self):
        content = {'type': 'cards', 'items': [{'title': title, 'body': body} for title, body in
                   [('成立于1998年', '覆盖全国'), ('人才', '团队成长'), ('网络', '区域协同'), ('空间', '办公完善')]]}
        payload, adapter = adapt_for_layout('content-blue-112', content, '业务概览')
        self.assertEqual(adapter, 'four_card_items_to_p112')
        payload['theme'] = 'blue'
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'content.json'
            output = directory / 'slide.pptx'
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            fill(LIBRARY, 'content-blue-112', source, output, allow_draft=True)
            shapes = {shape.shape_id for shape in Presentation(output).slides[0].shapes}
            self.assertFalse({20, 21, 22, 27, 42} & shapes)

    def test_four_step_process_replaces_source_icons_with_numbers(self):
        content = {'type': 'process', 'items': [
            {'title': '需求确认', 'body': '核对目标与范围'},
            {'title': '方案设计', 'body': '形成实施路径'},
            {'title': '执行交付', 'body': '按计划完成任务'},
            {'title': '结果验收', 'body': '检查结果并复盘'}]}
        page = {'layout_id': 'content-blue-256', 'title': '四步实施流程',
                'information_relation': 'process', 'content': content}
        choice = resolve(LIBRARY, self.request(page))['pages'][0]
        self.assertEqual(choice['layout_id'], 'content-blue-256')
        payload, adapter = adapt_for_layout('content-blue-256', content, page['title'])
        self.assertEqual(adapter, 'four_process_items_to_p256')
        self.assertEqual(payload['texts']['steps[3].body'], '检查结果并复盘')
        payload['theme'] = 'blue'
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source, output = directory / 'content.json', directory / 'slide.pptx'
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            fill(LIBRARY, 'content-blue-256', source, output, allow_draft=True)
            shapes = {shape.shape_id: shape for shape in Presentation(output).slides[0].shapes}
            self.assertFalse({12, 13, 14, 16} & shapes.keys())
            self.assertEqual([shapes[sid].text for sid in (2, 3, 4, 5)], ['01', '02', '03', '04'])

        wrong = dict(page, information_relation='parallel-points')
        self.assertNotEqual(resolve(LIBRARY, self.request(wrong))['pages'][0]
                            ['selection_mode'], 'source_template')
        automatic = dict(page)
        del automatic['layout_id']
        self.assertEqual(resolve(LIBRARY, self.request(automatic))['pages'][0]['layout_id'],
                         'content-blue-256')

    def test_specialized_problem_solving_and_issue_action_remain_strict(self):
        for layout_id, relation in [('content-blue-119', 'process'),
                                    ('content-blue-135', 'comparison'),
                                    ('content-blue-262', 'process')]:
            page = {'layout_id': layout_id, 'title': '通用工作安排',
                    'information_relation': relation,
                    'content': {'type': 'cards', 'items': [
                        {'title': '项目', 'body': '独立事实'} for _ in range(4)]}}
            choice = resolve(LIBRARY, self.request(page))['pages'][0]
            self.assertNotEqual(choice['selection_mode'], 'source_template')
            self.assertGreater(choice['rejected_reasons'].get('semantic_invariant', 0), 0)

    def test_serpentine_four_step_layout_uses_neutral_number_nodes(self):
        content = {'type': 'process', 'items': [
            {'title': f'阶段{i}', 'body': f'阶段{i}的真实工作'} for i in range(1, 5)]}
        page = {'layout_id': 'content-blue-258', 'title': '四阶段流程',
                'information_relation': 'process', 'content': content}
        self.assertEqual(resolve(LIBRARY, self.request(page))['pages'][0]['layout_id'],
                         'content-blue-258')
        payload, adapter = adapt_for_layout('content-blue-258', content, page['title'])
        self.assertEqual(adapter, 'four_process_items_to_p258')
        payload['theme'] = 'blue'
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source, output = directory / 'content.json', directory / 'slide.pptx'
            source.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            fill(LIBRARY, 'content-blue-258', source, output, allow_draft=True)
            shapes = {shape.shape_id: shape for shape in Presentation(output).slides[0].shapes}
            self.assertFalse({66, 67, 68, 69} & shapes.keys())
            self.assertEqual([shapes[sid].text for sid in (31, 32, 33, 34)],
                             ['01', '02', '03', '04'])

    def test_nested_four_layers_requires_explicit_inside_out_order(self):
        content = {'type': 'hierarchy', 'order': 'inner_to_outer',
                   'items': [{'title': f'层级{i}', 'body': f'第{i}层的真实职责'}
                             for i in range(1, 5)]}
        page = {'layout_id': 'content-blue-181', 'title': '服务能力层级',
                'information_relation': 'framework', 'content': content}
        self.assertEqual(resolve(LIBRARY, self.request(page))['pages'][0]['layout_id'],
                         'content-blue-181')
        payload, adapter = adapt_for_layout('content-blue-181', content, page['title'])
        self.assertEqual(adapter, 'four_nested_layers_to_p181')
        self.assertEqual(payload['texts']['layers[3].heading'], '层级4')
        automatic = dict(page)
        del automatic['layout_id']
        self.assertEqual(resolve(LIBRARY, self.request(automatic))['pages'][0]['layout_id'],
                         'content-blue-181')
        wrong = dict(page, content=dict(content, order='outer_to_inner'))
        self.assertNotEqual(resolve(LIBRARY, self.request(wrong))['pages'][0]
                            ['selection_mode'], 'source_template')

    def test_five_year_timeline_requires_real_ascending_years(self):
        content = {'type': 'milestone_timeline', 'items': [
            {'label': f'{2026 + i}年', 'title': f'阶段{i+1}', 'body': f'完成第{i+1}阶段工作'}
            for i in range(5)]}
        page = {'layout_id': 'content-blue-199', 'title': '五年建设路线',
                'information_relation': 'timeline', 'content': content}
        self.assertEqual(resolve(LIBRARY, self.request(page))['pages'][0]['layout_id'],
                         'content-blue-199')
        payload, adapter = adapt_for_layout('content-blue-199', content, page['title'])
        self.assertEqual(adapter, 'five_year_milestones_to_p199')
        self.assertEqual(payload['texts']['years[4].label'], '2030年')
        automatic = dict(page)
        del automatic['layout_id']
        self.assertEqual(resolve(LIBRARY, self.request(automatic))['pages'][0]['layout_id'],
                         'content-blue-199')
        wrong_items = [dict(item) for item in content['items']]
        wrong_items[2]['label'] = '阶段三'
        wrong = dict(page, content=dict(content, items=wrong_items))
        self.assertNotEqual(resolve(LIBRARY, self.request(wrong))['pages'][0]
                            ['selection_mode'], 'source_template')

    def test_smart_and_risk_response_reject_generic_pages(self):
        for layout_id, relation in [('content-blue-125', 'framework'),
                                    ('content-blue-050', 'comparison')]:
            page = {'layout_id': layout_id, 'title': '通用概览',
                    'information_relation': relation,
                    'content': {'type': 'cards', 'items': [{'title': str(i), 'body': '事实'}
                                                           for i in range(5 if '125' in layout_id else 4)]}}
            choice = resolve(LIBRARY, self.request(page))['pages'][0]
            self.assertNotEqual(choice['selection_mode'], 'source_template')
            self.assertGreater(choice['rejected_reasons'].get('semantic_invariant', 0), 0)

    def test_inventory_classification_does_not_activate_unreviewed_adapter(self):
        entry = {'matching_policy': 'structural', 'canonical_relation': 'parallel-points',
                 'information_relation': 'source-specific-label'}
        page = {'role': 'body', 'information_relation': 'parallel-points',
                'content': {'type': 'cards', 'items': []}}
        self.assertFalse(matches_structural_relation(entry, page, {}))

    def test_pending_structural_layout_keeps_explicit_field_binding(self):
        entry = {'id': 'content-blue-142', 'matching_activation': 'classified_pending_trial',
                 'matching_contract': {'policy': 'structural'}}
        exact = {'layout_id': 'content-blue-142', 'role': 'body',
                 'content': {'texts': {'center.title': '真实中心主题'}}}
        self.assertTrue(matches_structural_contract(entry, exact, {}))
        generic = {'layout_id': 'content-blue-142', 'role': 'body',
                   'content': {'type': 'cards', 'items': []}}
        self.assertFalse(matches_structural_contract(entry, generic, {}))

    def test_arrows_and_common_target_reject_unrelated_cards(self):
        for layout_id in ('content-blue-150', 'content-blue-152'):
            page = {'layout_id': layout_id, 'title': '业务概览',
                    'information_relation': 'parallel-points',
                    'content': {'type': 'cards', 'items': [
                        {'title': f'项目{i}', 'body': '相互独立的事实'} for i in range(5)]}}
            choice = resolve(LIBRARY, self.request(page))['pages'][0]
            self.assertNotEqual(choice['selection_mode'], 'source_template')
            self.assertGreater(choice['rejected_reasons'].get('semantic_invariant', 0), 0)

    def test_strict_exact_fields_only_preserve_registered_legacy_relation(self):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))['layouts']
        by_id = {entry['id']: entry for entry in catalog}
        old = {'layout_id': 'content-blue-150', 'information_relation': 'parallel-items',
               'content': {'texts': {'page.title': '阶段计划'}}}
        self.assertTrue(matches_strict_contract(by_id['content-blue-150'], old))
        wrong = dict(old, layout_id='content-blue-076', information_relation='parallel-points')
        self.assertFalse(matches_strict_contract(by_id['content-blue-076'], wrong))


if __name__ == '__main__':
    unittest.main()

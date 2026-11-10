import json
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts'
LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')
sys.path.insert(0, str(SCRIPT))
from content_adapters import adapt_for_layout
from plan_deck import matches_structural_contract


class StructuralBatch16Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {x['id']: x for x in catalog['layouts']}

    def test_problem_action_pairs_require_real_axes_and_actions(self):
        content = {'type': 'problem_action_pairs', 'title': '问题与改善',
                   'axis_top': '响应', 'axis_bottom': '质量',
                   'problem_label': '问题', 'action_label': '行动',
                   'items': [{'problem_title': f'问题{i}', 'problem_body': '实际问题',
                              'action_title': f'措施{i}', 'action_body': '实际行动'}
                             for i in range(3)]}
        entry = self.entries['content-blue-133']
        self.assertTrue(matches_structural_contract(entry, {'role': 'body', 'content': content}, {}))
        adapted, adapter = adapt_for_layout(entry['id'], content)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapted['texts']['pairs[2].action_body'], '实际行动')
        del content['items'][1]['action_body']
        self.assertFalse(matches_structural_contract(entry, {'role': 'body', 'content': content}, {}))
        self.assertIsNone(adapt_for_layout(entry['id'], content)[1])

    def test_five_phase_contract_requires_all_outputs(self):
        content = {'type': 'phase_goal_activity_output', 'title': '培训实施',
                   'items': [{'title': f'阶段{i}', 'goal': '目标', 'activity': '实际活动',
                              'output': '真实产物'} for i in range(5)]}
        entry = self.entries['content-blue-230']
        self.assertTrue(matches_structural_contract(entry, {'role': 'body', 'content': content}, {}))
        adapted, adapter = adapt_for_layout(entry['id'], content)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapted['texts']['steps[4].output'], '真实产物')
        self.assertNotIn('items', adapted)
        del content['items'][0]['output']
        self.assertFalse(matches_structural_contract(entry, {'role': 'body', 'content': content}, {}))
        self.assertIsNone(adapt_for_layout(entry['id'], content)[1])


if __name__ == '__main__':
    unittest.main()

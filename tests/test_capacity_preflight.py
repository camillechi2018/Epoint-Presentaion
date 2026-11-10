import json
import sys
import tempfile
import unittest
from pathlib import Path

LIBRARY = Path(r'C:\Users\xiaoc\.codex\skills\github-knowledge-next')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from capacity_preflight import preflight
from content_adapters import adapt_for_layout
from fill_layout import fill
from plan_deck import resolve


class CapacityPreflightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((LIBRARY / 'catalog.json').read_text(encoding='utf-8'))
        cls.entries = {entry['id']: entry for entry in catalog['layouts']}

    def test_known_p142_center_title_wrap_preserves_text_and_fills(self):
        entry = self.entries['content-blue-142']
        content = {'type': 'cards', 'center': {'title': '服务能力'},
                   'items': [{'title': f'项目{i}', 'body': '说明'} for i in range(4)]}
        check = preflight(LIBRARY, entry, content, '业务概览', 'blue')
        self.assertEqual(check['status'], 'wrap_possible')
        wrapped = check['wrap_suggestions']['center.title']
        self.assertEqual(wrapped.replace('\n', ''), '服务能力')
        self.assertTrue(check['longcopy_sha256'])
        mapped, adapter = adapt_for_layout(entry['id'], content, '业务概览', entry=entry)
        self.assertIsNotNone(adapter)
        mapped['texts']['center.title'] = wrapped
        mapped['theme'] = 'blue'
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.json'
            output = Path(directory) / 'page.pptx'
            source.write_text(json.dumps(mapped, ensure_ascii=False), encoding='utf-8')
            fill(LIBRARY, entry['id'], source, output, allow_draft=True)
            self.assertGreater(output.stat().st_size, 1000)

    def test_real_customer_copy_ranks_roomier_card_before_tight_card(self):
        content = {'type': 'cards', 'items': [
            {'title': '产品体验', 'body': '通过持续维护、优化搜索引擎词库，让用户搜的更快、更准'},
            {'title': '商品扩充', 'body': '可售类目内的商品是否可直接上架？'},
            {'title': '社群宣传', 'body': '发布宣传海报有哪些内容上的限制以及要求？'},
            {'title': '线下宣传', 'body': '是否允许此类线下推广方式？'}]}
        request = {'theme': 'blue', 'asset_policy': 'verified_draft', 'allow_draft': True,
                   'pages': [{'role': 'body', 'purpose': '运营计划与待确认事项',
                              'title': '运营计划与待确认事项', 'content': content}]}
        result = resolve(LIBRARY, request)['pages'][0]
        self.assertEqual(result['candidate_ids'][0], 'content-blue-112')
        summaries = {row['layout_id']: row for row in result['candidate_summaries']}
        self.assertGreater(len(summaries['content-blue-143']['capacity_preflight']['advisory']),
                           len(summaries['content-blue-112']['capacity_preflight']['advisory']))


if __name__ == '__main__':
    unittest.main()

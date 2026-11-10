"""Regression checks against the verified Git catalog."""
from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from plan_deck import count_profile, eligible, load, resolve
from relation_match import load_taxonomy, match_relation, match_role


class RelationMatchingTest(unittest.TestCase):
    root: Path

    @classmethod
    def setUpClass(cls):
        cls.catalog = load(cls.root)
        cls.taxonomy = load_taxonomy(cls.root, cls.catalog)

    def candidates(self, role, relation, theme='blue'):
        return [e for e in self.catalog['layouts']
                if e.get('classification_status') == 'verified'
                and theme in e.get('themes', [])
                and match_role(e, role, relation, self.taxonomy)
                and match_relation(e, relation, self.taxonomy)]

    def test_generic_process_crosses_body_roles(self):
        rows = self.candidates('content', '流程')
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(e['canonical_relation'] == 'process' for e in rows))

    def test_specific_relation_stays_exact(self):
        self.assertEqual([e['id'] for e in self.candidates('content', 'five-stage-process')],
                         ['content-blue-230'])

    def test_structural_roles_remain_strict(self):
        self.assertEqual(self.candidates('directory', '流程'), [])
        self.assertEqual(self.candidates('cover', '目录'), [])

    def test_missing_relation_does_not_broaden_role(self):
        rows = self.candidates('content', None)
        self.assertTrue(all(e['role'] == 'content' for e in rows))

    def test_theme_and_status_gates_remain_in_planner(self):
        page = {'purpose': '项目流程', 'role': 'content', 'information_relation': '流程',
                'theme': 'blue', 'needs': {'item_count': 3}}
        result = resolve(self.root, {'allow_draft': True, 'pages': [page]})
        self.assertIn(result['pages'][0]['layout_id'], {'content-blue-230', 'content-blue-252'})
        self.assertEqual(result['pages'][0]['matched_role'], 'process')
        with self.assertRaisesRegex(ValueError, '没有合格版式'):
            resolve(self.root, {'allow_draft': False, 'pages': [page]})

    def test_purpose_label_breaks_generic_relation_ties(self):
        for title,count,expected in (
            ('三阶段项目逻辑',3,'content-blue-252'),
            ('五阶段工作流程',5,'content-blue-230'),
            ('六步问题处理闭环',6,'content-blue-240'),
        ):
            with self.subTest(title=title):
                page={'purpose':title,'title':title,'role':'content',
                      'information_relation':'流程','theme':'blue','needs':{'item_count':count}}
                chosen=resolve(self.root,{'allow_draft':True,'pages':[page]})['pages'][0]
                self.assertEqual(chosen['layout_id'],expected)
                self.assertGreater(chosen['fit_signals']['label_overlap'],0)

    def test_item_count_is_inferred_and_conflicts_fail(self):
        page={'purpose':'三阶段项目逻辑','role':'content','information_relation':'流程',
              'theme':'blue','items':[{}, {}, {}]}
        chosen=resolve(self.root,{'allow_draft':True,'pages':[page]})['pages'][0]
        self.assertEqual(chosen['layout_id'],'content-blue-252')
        page['needs']={'item_count':4}
        with self.assertRaisesRegex(ValueError,'不一致'):
            resolve(self.root,{'allow_draft':True,'pages':[page]})

    def test_verified_tech_relation_agrees_with_review(self):
        rows={e['id']:e for e in self.catalog['layouts']}
        self.assertEqual(rows['content-tech-021']['information_relation'],'key-points')
        self.assertEqual(rows['content-tech-021']['canonical_relation'],'parallel-points')
        self.assertNotIn(rows['content-tech-021'],self.candidates('content','流程','deep-blue-tech'))

    def test_older_fixed_count_evidence_is_retrievable(self):
        rows={e['id']:e for e in self.catalog['layouts']}
        self.assertEqual(count_profile(rows['content-blue-133'],self.root)[0],[3])
        self.assertEqual(count_profile(rows['content-tech-016'],self.root)[0],[5])
        page={'purpose':'五项能力','role':'content','information_relation':'层级',
              'theme':'deep-blue-tech','needs':{'item_count':5}}
        request={'_root':self.root,'allow_draft':True,'style_family':'deep-blue-tech'}
        self.assertEqual(eligible(rows['content-tech-016'],page,request,self.taxonomy),[])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    RelationMatchingTest.root = args.library.resolve()
    unittest.main(argv=['test_relation_matching.py'])

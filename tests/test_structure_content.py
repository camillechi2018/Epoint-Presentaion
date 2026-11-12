import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from structure_content import prepare, main
import run


class StructureContentTests(unittest.TestCase):
    def test_preflight_without_pages_keeps_existing_request(self):
        request = {'theme': 'blue'}
        self.assertEqual(prepare(request)[0], request)

    def request(self):
        return {'theme': 'blue', 'pages': [{'page_id': 'P1', 'role': 'body',
                 'information_relation': 'parallel-points', 'source_refs': ['source#1'],
                 'content': {'type': 'bullets', 'items': ['约200人，计划2027年部署。', '尚未通过验收。'],
                             'item_titles': ['人员与计划', '验收状态']}}]}

    def test_preserves_every_body_and_source_with_no_mutation(self):
        original = self.request(); before = copy.deepcopy(original)
        result, report = prepare(original)
        self.assertEqual(original, before)
        self.assertEqual(report['status'], 'ready_for_matching')
        self.assertEqual([i['body'] for i in result['pages'][0]['content']['items']],
                         before['pages'][0]['content']['items'])
        self.assertEqual(result['pages'][0]['source_refs'], ['source#1'])
        self.assertEqual(result['pages'][0]['content_preparation']['title_review'], 'host_agent_provided')
        self.assertEqual(prepare(result)[0], result)

    def test_missing_labels_returns_actionable_task_without_changing_text(self):
        request = self.request(); del request['pages'][0]['content']['item_titles']
        result, report = prepare(request)
        self.assertEqual(result, request)
        self.assertEqual(report['status'], 'needs_agent_structure')
        self.assertEqual(report['tasks'][0]['code'], 'ITEM_TITLES_REQUIRED')
        self.assertEqual(report['tasks'][0]['source_refs'], ['source#1'])

    def test_wrong_title_count_does_not_drop_items(self):
        request = self.request(); request['pages'][0]['content']['item_titles'] = ['一项']
        result, report = prepare(request)
        self.assertEqual(result, request)
        self.assertEqual(len(report['tasks']), 1)

    def test_does_not_invent_parallel_relationship(self):
        for relation in ('cycle', 'timeline', 'hierarchy', None):
            request = self.request(); request['pages'][0]['information_relation'] = relation
            result, report = prepare(request)
            self.assertEqual(result, request)
            self.assertEqual(report['tasks'][0]['code'], 'RELATION_NEEDS_STRUCTURED_CONTENT')

    def test_explicit_plain_text_and_structural_pages_remain_available(self):
        request = self.request(); request['pages'][0]['content']['keep_bullets_reason'] = '逐条保留原文条款'
        result, report = prepare(request)
        self.assertEqual(result, request)
        self.assertEqual(report['status'], 'ready_for_matching')
        request['pages'][0]['role'] = 'section'
        self.assertEqual(prepare(request)[0], request)

    def test_cli_reports_pending_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source=root/'request.json'; out=root/'prepared.json'; report=root/'report.json'
            req=self.request();del req['pages'][0]['content']['item_titles']
            source.write_text(json.dumps(req),encoding='utf-8')
            args=['--request',str(source),'--out',str(out),'--report',str(report)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(args),2)
                self.assertEqual(main(args),2)
            self.assertEqual(json.loads(out.read_text(encoding='utf-8')),req)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['status'],'needs_agent_structure')

    def test_portable_launcher_dispatches_to_registered_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'runtime.json').write_text(json.dumps({'python':sys.executable}),encoding='utf-8')
            with patch.object(run,'state_root',return_value=root), \
                 patch.object(sys,'argv',['run.py','--structure-content','--request','a.json']), \
                 patch.object(run.subprocess,'call',return_value=0) as call:
                self.assertEqual(run.main(),0)
                self.assertEqual(Path(call.call_args.args[0][1]).name,'structure_content.py')
                self.assertEqual(call.call_args.args[0][2:],['--request','a.json'])

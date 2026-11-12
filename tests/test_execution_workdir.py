"""A failed execution must not poison the next attempt's page files."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_presentation


class ExecutionWorkdirTests(unittest.TestCase):
    def test_retry_uses_new_work_directory(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'deck.pptx'
            request = {'pages': [{'role': 'body'}]}
            plan = {'pages': [{'selection_mode': 'guided_composition'}]}
            paths = []
            with patch.object(run_presentation, '_load_workflow'), \
                 patch.object(run_presentation, 'check_directory_section_count', create=True), \
                 patch.object(run_presentation, 'check_structure', create=True):
                for _ in range(2):
                    report = {'can_make_complete_deck': True}
                    with self.assertRaisesRegex(ValueError, '缺少可填充'):
                        run_presentation.execute_plan(request, plan, report, output)
                    paths.append(Path(report['execution_work_dir']))
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(all(path.is_dir() for path in paths))

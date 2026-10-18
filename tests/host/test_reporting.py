# SPDX-License-Identifier: Apache-2.0
"""Subprocess regressions for pytest phases, integrity and exact case replays."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from tests.testlab.build import PROJECT
from tests.testlab.process import run_process

FIXTURE = 'tests/fixtures/reporting_cases.py'


class ReportingTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get('TESTLAB_EVIDENCE_ROOT')
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName+'-', dir=Path(evidence).resolve()))
        else:
            temporary = tempfile.TemporaryDirectory(prefix='testlab-report-')
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.index = 0

    def child(self, *args):
        self.index += 1
        directory = self.root/str(self.index)
        command = [sys.executable, '-W', 'error::ResourceWarning', '-m', 'pytest', '-q',
                   *args, '--evidence-root', str(directory/'reports')]
        result = run_process(command, cwd=str(PROJECT), env=dict(os.environ,
            PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1'),
            log_dir=directory/'launcher', timeout=25, expected_returncodes=tuple(range(6)))
        self.assertEqual(result['status'], 'passed', result)
        paths = list((directory/'reports').glob('*/run.json'))
        self.assertEqual(len(paths), 1)
        run = json.loads(paths[0].read_text())
        self.assertEqual(run['pytest_exitcode'], result['returncode'])
        return paths[0].parent, run, result['returncode']

    def replay(self, failure):
        self.index += 1
        directory = self.root/str(self.index)
        result = run_process([sys.executable, '-m', 'tests.testlab', 'reproduce', str(failure),
            '--output-root', str(directory/'replays')], cwd=str(PROJECT),
            env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1'),
            log_dir=directory/'launcher', timeout=25, expected_returncodes=(0,1,2))
        self.assertEqual(result['status'], 'passed', result)
        return directory, result

    def failure(self):
        root, run, code = self.child(FIXTURE+'::test_call_failure')
        self.assertEqual(code, 1)
        return root, next(root.glob('cases/*/failure.json'))

    def test_real_pytest_phases_and_junit(self):
        root, run, code = self.child(*[FIXTURE+'::'+name for name in
            ('test_pass','test_call_failure','test_setup_failure','test_teardown_failure')])
        self.assertEqual(code, 1)
        self.assertEqual(run['status'], 'error')
        self.assertEqual(run['counts'], {'passed':1,'failed':1,'error':2,'skipped':0,'not_run':0})
        results = {p['nodeid'].split('::')[-1]: json.loads((root/p['result_artifact']).read_text()) for p in run['cases']}
        self.assertEqual([p['outcome'] for p in results['test_teardown_failure']['phases']], ['passed','passed','failed'])
        self.assertEqual(results['test_setup_failure']['phases'][0]['error_type'], 'RuntimeError')
        xml = ET.parse(root/'junit.xml').getroot()
        self.assertEqual(len(xml.findall('.//error')), 2)
        self.assertEqual(len(xml.findall('.//failure')), 1)
        self.assertEqual(len(list(root.glob('cases/*/failure.json'))), 3)

    def test_zero_collection_errors_and_collect_only(self):
        root, run, code = self.child(FIXTURE, '-k', 'does_not_name_any_case')
        self.assertEqual(code, 5)
        self.assertEqual(run['status'], 'error')
        self.assertEqual(run['collected'], 0)
        self.assertTrue((root/'failure.json').is_file())
        root, run, code = self.child('tests/fixtures/not_a_test_file.py')
        self.assertEqual(code, 4)
        self.assertEqual(run['status'], 'error')
        root, run, code = self.child(FIXTURE+'::test_pass', '--collect-only')
        self.assertEqual(code, 0)
        self.assertEqual(run['status'], 'not_run')
        self.assertEqual(run['counts']['not_run'], 1)
        self.assertFalse(list(root.glob('cases/*/failure.json')))

    def test_required_skip_is_visible_and_not_success(self):
        root, run, code = self.child(FIXTURE+'::test_required_skip')
        self.assertEqual(code, 1)
        self.assertEqual(run['original_pytest_exitcode'], 0)
        self.assertEqual(run['status'], 'error')
        self.assertEqual(run['counts']['skipped'], 1)
        self.assertIn('required_case_skipped:', run['policy_errors'][0])
        self.assertEqual(len(ET.parse(root/'junit.xml').findall('.//skipped')), 1)

    def test_runs_are_unique_and_artifacts_are_relative(self):
        first, _, _ = self.child(FIXTURE+'::test_pass')
        second, run, code = self.child(FIXTURE+'::test_pass')
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(code, 0)
        self.assertEqual(run['status'], 'passed')
        self.assertTrue((first/'run.json').is_file())
        for name in run['artifacts'].values():
            self.assertFalse(Path(name).is_absolute())
            self.assertTrue((second/name).exists())

    def test_exact_selection_guard_refuses_two_cases(self):
        root, run, code = self.child(FIXTURE+'::test_pass', FIXTURE+'::test_call_failure',
                                   '--testlab-exact-node', FIXTURE+'::test_pass')
        self.assertEqual(code, 4)
        self.assertEqual(run['status'], 'error')
        self.assertIn('exact_node_selection', run['policy_errors'][0])
        self.assertFalse([c for c in run['cases'] if c['status'] == 'passed'])

    def test_replay_uses_selector_and_ignores_report_commands(self):
        root, failure = self.failure()
        data = json.loads(failure.read_text())
        marker = self.root/'must-not-be-created'
        data['argv'] = [sys.executable, '-c', 'open('+repr(str(marker))+',"w").write("bad")']
        failure.write_text(json.dumps(data))
        directory, result = self.replay(failure)
        self.assertEqual(result['returncode'], 1)
        replay = json.loads(next((directory/'replays').glob('*/reproduction.json')).read_text())
        self.assertEqual(replay['status'], 'failed')
        self.assertTrue(replay['same_exact_node'] and replay['same_case_outcome'])
        self.assertFalse(marker.exists())
        self.assertTrue((root/'run.json').exists())

    def test_changed_source_snapshot_is_refused_before_launch(self):
        root, failure = self.failure()
        target = root/'inputs/source/common.mk'
        target.write_bytes(target.read_bytes()+b'\n# changed snapshot\n')
        directory, result = self.replay(failure)
        self.assertEqual(result['returncode'], 2)
        self.assertFalse((directory/'replays').exists())
        self.assertIn('snapshot', (directory/'launcher/stderr.log').read_text())

    def test_changed_harness_and_unsafe_selector_are_refused(self):
        for kind in ('harness', 'selector'):
            with self.subTest(kind=kind):
                root, failure = self.failure()
                if kind == 'harness':
                    path = root/'run.json'
                    data = json.loads(path.read_text())
                    data['harness']['digest'] = '0'*64
                else:
                    path = failure
                    data = json.loads(path.read_text())
                    data['reproduction']['nodeid'] = '../../outside.py::test_anything'
                path.write_text(json.dumps(data))
                directory, result = self.replay(failure)
                self.assertEqual(result['returncode'], 2)
                self.assertFalse((directory/'replays').exists())

    def test_input_changes_cannot_be_reported_as_passed(self):
        source = self.root/'private-source'
        shutil.copytree(PROJECT/'upstream/examples', source)
        original = (PROJECT/'upstream/examples/common.mk').read_bytes()
        root, run, code = self.child(FIXTURE+'::test_input_change','--source-root',str(source))
        self.assertEqual(code, 1)
        self.assertEqual(run['original_pytest_exitcode'], 0)
        self.assertEqual(run['counts']['passed'], 1)
        self.assertEqual(run['status'], 'error')
        self.assertIn('tested_source_changed_during_run', run['policy_errors'])
        self.assertEqual((PROJECT/'upstream/examples/common.mk').read_bytes(), original)

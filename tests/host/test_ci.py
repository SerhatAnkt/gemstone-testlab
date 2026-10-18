# SPDX-License-Identifier: Apache-2.0
"""CI gates reject real empty/partial/skip runs and mismatched evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.testlab import ci_gate as gate
from tests.testlab import reporting as r
from tests.testlab.build import PROJECT, build_targets
from tests.testlab.ci import run_ci
from tests.testlab.process import run_process

FIXTURE = 'tests/fixtures/reporting_cases.py'


class CIGateTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get('TESTLAB_EVIDENCE_ROOT')
        if evidence:
            parent = Path(evidence).resolve();parent.mkdir(parents=True,exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=parent))
        else:
            temporary = tempfile.TemporaryDirectory(prefix='testlab-ci-')
            self.addCleanup(temporary.cleanup);self.root = Path(temporary.name)
        self.index = 0

    def child(self, *arguments):
        self.index += 1
        directory = self.root/str(self.index)
        process = run_process([sys.executable,'-m','pytest','-q',*arguments,
            '--evidence-root',str(directory/'reports')],cwd=PROJECT,
            env={**os.environ,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1'},
            log_dir=directory/'launcher',timeout=30,expected_returncodes=tuple(range(6)))
        self.assertEqual(process['status'],'passed',process)
        path = next((directory/'reports').glob('*/run.json'))
        return path,process['returncode']

    def test_real_pass_is_accepted_but_missing_required_case_is_not(self):
        node = FIXTURE+'::test_pass'
        path,code = self.child(node)
        self.assertEqual(code,0)
        self.assertEqual(gate.validate_pytest(path,[node])['collected'],1)
        with self.assertRaisesRegex(gate.AcceptanceError,'Missing required'):
            gate.validate_pytest(path,[node,FIXTURE+'::another_required_case'])

    def test_zero_collection_is_rejected(self):
        path,code = self.child(FIXTURE,'-k','WP09_NO_SUCH_CASE')
        self.assertEqual(code,5)
        with self.assertRaises(gate.AcceptanceError):gate.validate_pytest(path,[FIXTURE+'::test_pass'])

    def test_collect_only_is_rejected_despite_zero_exit(self):
        path,code = self.child(FIXTURE+'::test_pass','--collect-only')
        self.assertEqual(code,0)
        with self.assertRaises(gate.AcceptanceError):gate.validate_pytest(path,[FIXTURE+'::test_pass'])

    def test_required_skip_never_passes_the_ci_gate(self):
        node = FIXTURE+'::test_required_skip'
        path,code = self.child(node)
        self.assertEqual(code,1)
        self.assertEqual(gate.read(path)['original_pytest_exitcode'],0)
        with self.assertRaises(gate.AcceptanceError):gate.validate_pytest(path,[node])

    def test_case_and_junit_disagreement_are_rejected(self):
        node = FIXTURE+'::test_pass'
        path,_ = self.child(node)
        case = path.parent/gate.read(path)['cases'][0]['result_artifact']
        original = case.read_bytes()
        value = gate.read(case);value['status'] = 'failed';r.save_json(case,value)
        try:
            with self.assertRaises(gate.AcceptanceError):gate.validate_pytest(path,[node])
        finally:case.write_bytes(original)
        junit = path.parent/'junit.xml';original = junit.read_bytes()
        junit.write_text('<testsuites><testsuite /></testsuites>')
        try:
            with self.assertRaisesRegex(gate.AcceptanceError,'JUnit'):gate.validate_pytest(path,[node])
        finally:junit.write_bytes(original)

    def test_native_binary_cannot_satisfy_aarch64_build_gate(self):
        report = build_targets(target_ids=['can.c.sender'],build_root=self.root/'binaries',output_root=self.root/'builds')
        self.assertEqual(report['status'],'passed')
        gate.validate_build(report,'host',['can.c.sender'])
        with self.assertRaises(gate.AcceptanceError):gate.validate_build(report,'aarch64',['can.c.sender'])

    def test_changed_missing_and_escaping_evidence_are_rejected(self):
        folder = self.root/'evidence';folder.mkdir()
        file = folder/'payload.log';file.write_text('original')
        manifest = gate.inventory(folder)
        gate.verify_inventory(folder,manifest)
        file.write_text('changed')
        with self.assertRaises(gate.AcceptanceError):gate.verify_inventory(folder,manifest)
        file.unlink()
        with self.assertRaises(gate.AcceptanceError):gate.verify_inventory(folder,manifest)
        file.write_text('original')
        broken = {'files':[{'path':'../outside','sha256':'0'*64,'size_bytes':1}]}
        broken['digest'] = r.digest_json(broken['files'])
        with self.assertRaises(ValueError):gate.verify_inventory(folder,broken)

    def test_wrong_checkout_is_reported_before_compiler_or_pytest(self):
        with patch.dict(os.environ,{'TESTLAB_EXPECTED_COMMIT':'0'*40}):
            report = run_ci(profile='aarch64',output=self.root/'wrong-checkout')
        self.assertEqual(report['exitcode'],2)
        self.assertIsNone(report['build_report'])
        self.assertIsNone(report['pytest_report'])
        self.assertIn('Checkout does not match',report['errors'][0])

    def test_missing_sdk_has_nonzero_ci_json_and_no_host_fallback(self):
        environment = {k:v for k,v in os.environ.items() if k not in ('TESTLAB_EXPECTED_COMMIT','GITHUB_ACTIONS')}
        with patch.dict(os.environ,environment,clear=True):
            report = run_ci(profile='aarch64',output=self.root/'missing-sdk',toolchain_root=self.root/'absent')
        self.assertEqual(report['exitcode'],2)
        self.assertEqual(report['status'],'error')
        self.assertTrue((self.root/'missing-sdk/ci.json').is_file())
        build = gate.read(self.root/'missing-sdk'/report['build_report'])
        self.assertFalse(build['tools'])
        self.assertTrue(all(t['binary'] is None for t in build['targets']))

    def test_proposed_fix_copies_work_under_parent_git_repository(self):
        repository = self.root/'parent-checkout'
        process = run_process(['git','init','-q',str(repository)],log_dir=self.root/'git-init',timeout=10)
        self.assertEqual(process['status'],'passed',process)
        environment = {**os.environ,'GIT_DIR':str(repository/'.git'),'GIT_WORK_TREE':str(repository)}
        for helper,folder,receipt in (('prepare_can_fix.py','can','testlab-fix.json'),
                                      ('prepare_serial_fixes.py','serial','testlab-serial-fixes.json')):
            copy = repository/folder
            process = run_process([sys.executable,str(PROJECT/'tools'/helper),'--output',str(copy)],
                cwd=PROJECT,env=environment,log_dir=self.root/(folder+'-prepare'),timeout=30)
            self.assertEqual(process['status'],'passed',process)
            value = gate.read(copy/receipt)
            self.assertEqual(value['status'],'passed')
            self.assertTrue(value['original_unchanged'])

    def test_aggregate_rejects_partial_duplicate_mixed_and_local_hosted_claims(self):
        output = self.root/'acceptance.json'
        self.assertEqual(gate.verify_profiles([Path('absent')]*3,output)['exitcode'],1)
        def values():
            return [{'profile':p,'contract_sha256':'c','source_input':{'digest':'s'},'harness':{'digest':'h'},
                     'repository':{'commit':'a'*40},'github':{}} for p in gate.PROFILES]
        good = values()
        with patch.object(gate,'verify_profile',side_effect=good):
            self.assertEqual(gate.verify_profiles([Path('fixture')]*4,output)['status'],'passed')
        variants=[]
        duplicate=values();duplicate[-1]['profile']='host';variants.append(duplicate)
        mixed=values();mixed[-1]['repository']['commit']='b'*40;variants.append(mixed)
        harness=values();harness[-1]['harness']['digest']='other';variants.append(harness)
        for variant in variants:
            with patch.object(gate,'verify_profile',side_effect=variant):
                self.assertEqual(gate.verify_profiles([Path('fixture')]*4,output)['exitcode'],1)
        with patch.object(gate,'verify_profile',side_effect=values()):
            result=gate.verify_profiles([Path('fixture')]*4,output,require_hosted=True,expected_commit='a'*40)
        self.assertEqual(result['exitcode'],1)
        self.assertEqual(result['github_hosted_runner'],'not_executed')

    def test_lease_gate_uses_final_cleanup_and_preserves_initial_refusal(self):
        recovered = {'owned':True,'cleanup_error':'controlled ownership refusal',
                     'cleanup':{'owned_interface_removed':True,'foreign_interface_touched':False}}
        gate.validate_lease(recovered)
        self.assertIn('cleanup_error',recovered)
        gate.validate_lease({'owned':False,'cleanup':{'owned_interface_removed':False,'foreign_interface_touched':False}})
        for cleanup in ({'owned_interface_removed':False,'foreign_interface_touched':False},
                        {'owned_interface_removed':True,'foreign_interface_touched':True},{}):
            with self.assertRaises(gate.AcceptanceError):gate.validate_lease({'owned':True,'cleanup':cleanup})


if __name__ == '__main__':unittest.main()

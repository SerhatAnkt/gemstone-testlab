#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove CI tests the selected commit using an isolated, unpublished Git fixture."""
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from tests.testlab import reporting as r
from tests.testlab.process import run_process


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toolchain-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    source=BASE/'upstream/examples'
    names=json.loads((BASE/'source.lock.json').read_text())['files']
    before={n:r.sha256(source/n) for n in names}
    result={'schema_version':1,'status':'failed','github_hosted_runner':'not_executed',
            'fixture':'local unpublished Git checkout','checks':{}}
    environment={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',PYTHONDONTWRITEBYTECODE='1')
    try:
        with tempfile.TemporaryDirectory(prefix='gemstone-ci-current-tree-') as temporary:
            checkout=Path(temporary)/'project';checkout.mkdir()
            for directory in ('tests','tools','upstream','patches','docs','.github'):
                shutil.copytree(BASE/directory,checkout/directory,
                    ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache','*.pyc','*.o'))
            for name in ('README.md','RESULTS.md','LICENSE','NOTICE','.gitignore','source.lock.json','pytest.ini'):
                shutil.copy2(BASE/name,checkout/name)
            index=0
            def git(*argv):
                nonlocal index
                index+=1
                process=run_process(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
                    '-c','user.name=TestLab CI fixture','-c','user.email=testlab@example.invalid',*argv],
                    cwd=checkout,env=environment,log_dir=out/'git'/str(index),timeout=20)
                assert process['status']=='passed',process
                return (out/'git'/str(index)/'stdout.log').read_text().strip()
            def ci(name,expected_commit,expected_exit):
                process=run_process([sys.executable,'-m','tests.testlab','ci','--profile','aarch64',
                    '--toolchain-root',str(args.toolchain_root.resolve()),'--output',str(out/name)],
                    cwd=checkout,env={**environment,'TESTLAB_EXPECTED_COMMIT':expected_commit},
                    log_dir=out/(name+'-cli'),timeout=180,expected_returncodes=(expected_exit,))
                assert process['status']=='passed' and process['returncode']==expected_exit,process
                return json.loads((out/name/'ci.json').read_text())
            git('init','-q');git('add','.');git('commit','-qm','Original fixture source')
            first=git('rev-parse','HEAD')
            good=ci('base-commit',first,0)
            assert good['status']=='passed' and good['repository']['commit']==first
            target=checkout/'upstream/examples/canbus/c/sender/main.c'
            original=target.read_text();changed='#error WP09_ACTUAL_PR_CHANGE\n'+original
            target.write_text(changed)
            (out/'change.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),
                fromfile='a/upstream/examples/canbus/c/sender/main.c',tofile='b/upstream/examples/canbus/c/sender/main.c')))
            git('add','upstream/examples/canbus/c/sender/main.c');git('commit','-qm','Controlled PR fixture change')
            second=git('rev-parse','HEAD');assert first!=second
            bad=ci('changed-commit',second,1)
            assert bad['repository']['commit']==second and bad['repository']['dirty'] is False
            assert bad['source_input']['digest']!=good['source_input']['digest']
            build=json.loads((out/'changed-commit'/bad['build_report']).read_text())
            assert build['status']=='failed' and not build['source']['reference']['selected_inputs_match']
            failed=next(t for t in build['targets'] if t['id']=='can.c.sender')
            assert failed['status']=='failed' and failed['binary'] is None
            assert 'WP09_ACTUAL_PR_CHANGE' in Path(failed['command']['log']).read_text()
            mismatch=ci('wrong-expected-commit',first,2)
            assert mismatch['build_report'] is None and mismatch['pytest_report'] is None
            assert 'Checkout does not match' in mismatch['errors'][0]
            result.update(status='passed',base_commit=first,changed_commit=second,
                checks={'base_commit_passed':True,'actual_changed_commit_failed':True,
                        'old_source_not_substituted':True,'wrong_expected_commit_blocked_before_tools':True})
    except Exception as exc:
        result['error']={'type':type(exc).__name__,'message':str(exc)}
    finally:
        result['original_unchanged']=before=={n:r.sha256(source/n) for n in names}
        if not result['original_unchanged']:result['status']='failed'
        r.save_json(out/'experiment.json',result)
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())

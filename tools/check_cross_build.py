#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the real pinned SDK, dirty sources and fail-closed build controls."""
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
from tests.testlab.build import default_source_root, sha256
from tests.testlab.process import run_process
from tests.testlab.toolchain import verify_tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path)
    parser.add_argument('--toolchain-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    source = (args.source_root or default_source_root()).resolve()
    sdk = args.toolchain_root.resolve()
    out = args.output.resolve()
    if out == source or out.is_relative_to(source) or out == sdk or out.is_relative_to(sdk):
        parser.error('Output must be outside source and SDK trees')
    out.mkdir(parents=True,exist_ok=False)
    names = json.loads((BASE/'source.lock.json').read_text())['files']
    before = {name:sha256(source/name) for name in names}
    result = {'schema_version':1,'work_package':'WP-08','status':'failed',
              'execution_mode':'cross_build_only','source_before':before,'checks':{}}
    children = []

    def build(name,tree,toolchain,ids=(),environment=None,expected=0):
        argv = [sys.executable,'-m','tests.testlab','build','--profile','aarch64',
                '--source-root',str(tree),'--toolchain-root',str(toolchain),
                '--build-root',str(out/'binaries'),'--output-root',str(out/name/'builds')]
        for target in ids:
            argv.extend(['--target',target])
        process = run_process(argv,cwd=BASE,env=environment,log_dir=out/name/'cli',
                              timeout=180,expected_returncodes=(expected,))
        children.append(process)
        assert process['status'] == 'passed' and process['returncode'] == expected, process
        summary = json.loads((out/name/'cli/stdout.log').read_text())
        report_path = Path(summary['report'])
        return json.loads(report_path.read_text()),report_path

    try:
        result['sdk_before'] = verify_tree(sdk)
        poison = {'CC':'/nonexistent/testlab-cc','CXX':'/nonexistent/testlab-cxx',
                  'CFLAGS':'--TESTLAB_INVALID_FLAG','CXXFLAGS':'--TESTLAB_INVALID_FLAG',
                  'CPPFLAGS':'--TESTLAB_INVALID_FLAG','LDFLAGS':'--TESTLAB_INVALID_FLAG',
                  'MAKEFLAGS':'--TESTLAB_INVALID_FLAG','MAKEFILES':'/nonexistent/testlab.mk',
                  'CPATH':'/nonexistent/testlab-headers','COMPILER_PATH':'/nonexistent/testlab-compiler',
                  'LIBRARY_PATH':'/nonexistent/testlab-libs','BASH_ENV':'/nonexistent/testlab-bash-env'}
        parent = {key:os.environ.get(key) for key in poison}
        baseline,path = build('poisoned-parent',source,sdk,environment={**os.environ,**poison})
        assert baseline['status'] == 'passed' and len(baseline['targets']) == 6
        assert all(t['binary']['elf']['machine'] == 183 for t in baseline['targets'])
        assert baseline['source']['inputs_unchanged_during_build']
        result['checks']['poisoned_parent'] = {'status':'passed','report':str(path),'injected_variables':poison,
            'targets':6,'parent_environment_unchanged':parent == {key:os.environ.get(key) for key in poison}}
        assert result['checks']['poisoned_parent']['parent_environment_unchanged']

        copy = out/'modified-examples'
        shutil.copytree(source,copy,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','build'))
        target = copy/'canbus/c/sender/main.c'
        original = target.read_text()
        modified = '#error WP08_EXPECTED_COMPILE_FAILURE\n'+original
        target.write_text(modified)
        (out/'change.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),
            fromfile='a/canbus/c/sender/main.c',tofile='b/canbus/c/sender/main.c')))
        failure,path = build('compile-failure',copy,sdk,('can.c.sender','serial.c'),expected=1)
        bad,good = failure['targets']
        assert failure['status'] == 'failed' and bad['status'] == 'failed' and good['status'] == 'passed'
        assert bad['binary'] is None and not Path(bad['expected_binary']).exists()
        assert not failure['source']['reference']['selected_inputs_match']
        assert 'WP08_EXPECTED_COMPILE_FAILURE' in Path(bad['command']['log']).read_text()
        previous = baseline['targets'][0]['binary']
        assert sha256(Path(previous['path'])) == previous['sha256']
        assert Path(bad['build_directory']) != Path(previous['path']).parent
        result['checks']['compile_failure'] = {'status':'passed','report':str(path),'cli_returncode':1,
            'healthy_target_still_built':True,'old_binary_not_reused':True,'dirty_source_was_built':True}

        # Copying is deliberate: the caller's SDK, including hard-linked files, is never edited.
        with tempfile.TemporaryDirectory(prefix='gemstone-wp08-sdk-') as temporary:
            relocated = Path(temporary)/'SDK with spaces'
            shutil.copytree(sdk,relocated,symlinks=True)
            installed = verify_tree(relocated)
            valid,path = build('relocated-sdk',source,relocated,('can.c.sender','serial.cpp'))
            assert valid['status'] == 'passed'
            result['checks']['relocated_sdk'] = {'status':'passed','report':str(path),
                'payload_sha256':installed['payload_sha256'],'targets':2,'sdk_path_contains_spaces':True}
            env = relocated/'env'
            env.write_text(env.read_text()+'\nexit 77 # TestLab tamper fixture; must never be sourced\n')
            invalid,path = build('tampered-sdk',source,relocated,('can.c.sender',),expected=2)
            assert invalid['status'] == 'error' and not invalid['tools']
            assert invalid['targets'][0]['command'] is None and invalid['targets'][0]['binary'] is None
            assert not (path.parent/'commands.jsonl').read_text()
            assert 'payload differs' in invalid['toolchain']['error']
            result['checks']['tampered_sdk'] = {'status':'passed','report':str(path),'cli_returncode':2,
                'sdk_env_not_sourced':True,'compiler_not_started':True,'host_fallback':False}

        result['sdk_after'] = verify_tree(sdk)
        assert result['sdk_before']['payload_sha256'] == result['sdk_after']['payload_sha256']
        assert all(p['cleanup']['group_gone'] and p['cleanup']['leader_reaped'] for p in children)
        result.update(status='passed',sdk_unchanged=True,cli_processes_collected=len(children))
    except Exception as exc:
        result['error'] = {'type':type(exc).__name__,'message':str(exc)}
    finally:
        result['original_unchanged'] = before == {name:sha256(source/name) for name in names}
        if not result['original_unchanged']:
            result['status'] = 'failed'
        (out/'experiment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('status','execution_mode','original_unchanged')},indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

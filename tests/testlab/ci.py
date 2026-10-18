# SPDX-License-Identifier: Apache-2.0
"""One CI entry per profile, with current-source identity and retained failures."""
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sys

from . import ci_gate as gate
from . import reporting as r
from .build import PROJECT, build_targets, default_source_root, elf_info, git_state, source_snapshot
from .process import run_process
from .targets import select_targets


def github_context():
    return {key:os.environ.get(name) for key,name in (
        ('actions','GITHUB_ACTIONS'),('repository','GITHUB_REPOSITORY'),('run_id','GITHUB_RUN_ID'),
        ('run_attempt','GITHUB_RUN_ATTEMPT'),('event','GITHUB_EVENT_NAME'),('event_sha','GITHUB_SHA'))}


def copy_evidence(source, destination):
    if not source.exists():
        return
    for path in source.rglob('*'):
        if path.is_symlink() or not path.is_file() or set(path.parts)&{'.git','__pycache__','.pytest_cache'}:
            continue
        if path.suffix in ('.json','.jsonl','.log','.xml','.bin','.sh','.patch') or '/inputs/source/' in path.as_posix():
            target = destination/path.relative_to(source)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)


def check_dependencies(profile):
    if profile == 'aarch64':
        return {}
    packages = gate.read(PROJECT/'tests/python-dependencies.lock.json')['packages']
    if profile == 'serial':
        packages += gate.read(PROJECT/'tests/serial-dependencies.lock.json')['packages']
    versions = {}
    for package in packages:
        try:
            versions[package['name']] = importlib.metadata.version(package['name'])
        except importlib.metadata.PackageNotFoundError:
            raise gate.AcceptanceError('Missing Python dependency: '+package['name']) from None
        gate.require(versions[package['name']] == package['version'],'Python dependency version differs: '+package['name'])
    return versions


def prebuilt_can(path, source, ids):
    value = gate.read(path)
    gate.require(value['source_digest'] == source_snapshot(source,select_targets(ids))['digest'],
                 'Prebuilt CAN inputs differ from tested sources')
    gate.require(set(value['binaries']) == set(ids),'Prebuilt CAN target matrix differs')
    targets = []
    for name in ids:
        binary = value['binaries'][name]
        path = Path(binary['path'])
        gate.require(path.is_file() and r.sha256(path) == binary['sha256'],'Prebuilt CAN binary differs')
        targets.append({'id':name,'status':'passed','binary':{**binary,'size_bytes':path.stat().st_size,'elf':elf_info(path)}})
    return {'schema_version':1,'profile':'host','status':'passed','origin':'verified_host_prebuilt',
            'source_digest':value['source_digest'],'targets':targets}


def run_ci(*, profile, output, source_root=None, source_profile='working-tree',
           toolchain_root=None, can_prebuilt=None, timeout=300, timeout_scale=1):
    if profile not in gate.PROFILES or source_profile not in ('working-tree','proposed-fixes'):
        raise ValueError('Unknown CI profile or source profile')
    if not all(math.isfinite(v) and v > 0 for v in (timeout,timeout_scale)):
        raise ValueError('CI budgets must be finite and positive')
    out = Path(output).resolve()
    source = Path(source_root or default_source_root()).resolve()
    if out == source or out.is_relative_to(source):
        raise ValueError('CI output must be outside the examples source tree')
    out.mkdir(parents=True,exist_ok=False)
    work = out/'work'
    work.mkdir()
    result = {'schema_version':1,'type':'testlab.ci','profile':profile,'source_profile':source_profile,
              'started_at':r.now(),'status':'error','exitcode':2,'errors':[],'checks':{},
              'github':github_context(),'repository':git_state(PROJECT),
              'environment':{'python':platform.python_version(),'system':platform.system(),
                             'machine':platform.machine(),'runner_uid':os.getuid()},
              'execution':{'github_hosted_runner':'not_executed','board_runtime':'not_run',
                           'arm64_build':'not_run','host_runtime':'not_run'},
              'inputs_unchanged':False,'build_report':None,'pytest_report':None}
    if result['github']['actions'] == 'true':
        result['execution']['github_hosted_runner'] = 'executed'
    environment = dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
    for key in ('PYTEST_ADDOPTS','PYTEST_PLUGINS','TESTLAB_EVIDENCE_ROOT'):
        environment.pop(key,None)
    prepared = source
    build = None
    captured = False

    def command(name, argv, *, expected=(0,), budget=timeout, extra=None):
        process = run_process(argv,cwd=PROJECT,env={**environment,**(extra or {})},
                              log_dir=out/'commands'/name,timeout=budget,
                              expected_returncodes=expected,max_output_bytes=8*1024*1024)
        result['checks'][name] = {'status':process['status'],'returncode':process['returncode'],
            'timed_out':process['timed_out'],'process_report':'commands/'+name+'/process.json'}
        gate.require(process['status'] == 'passed','CI command failed: '+name)
        return process

    try:
        rules = gate.contract()['profiles'][profile]
        result['contract_sha256'] = r.sha256(gate.CONTRACT)
        result['harness'] = r.harness_manifest()
        result['source_input'] = r.source_manifest(source,{'host'},out/'inputs/source')
        captured = True
        gate.require(all(f['sha256'] for f in result['source_input']['files']),'Missing current source inputs')
        gate.require(platform.system() == 'Linux','CI profiles require Linux')
        gate.require(sys.version_info[:2] == (3,12),'The pinned CI dependency set requires Python 3.12')
        expected = os.environ.get('TESTLAB_EXPECTED_COMMIT')
        if expected or result['github']['actions'] == 'true':
            gate.require(expected and re.fullmatch('[0-9a-f]{40}',expected),'CI requires an exact expected commit')
            gate.require(result['repository'].get('commit') == expected,'Checkout does not match expected commit')
            gate.require(result['repository'].get('dirty') is False,'Expected commit has uncommitted project changes')
            gate.require(source.is_relative_to(PROJECT),'Hosted CI must test the checked-out source tree')
        result['dependencies'] = check_dependencies(profile)
        if source_profile == 'proposed-fixes':
            gate.require(profile in ('serial','can'),'Proposed fixes belong only to serial and CAN profiles')
            helper = 'prepare_serial_fixes.py' if profile == 'serial' else 'prepare_can_fix.py'
            prepared = work/'prepared-source'
            command('prepare-source',[sys.executable,str(PROJECT/'tools'/helper),
                    '--source-root',str(source),'--output',str(prepared)],budget=30)
            name = 'testlab-serial-fixes.json' if profile == 'serial' else 'testlab-fix.json'
            shutil.copy2(prepared/name,out/'source-profile.json')
            folder = 'testlab-serial-fix-evidence' if profile == 'serial' else 'testlab-fix-evidence'
            copy_evidence(prepared/folder,out/'source-profile-evidence')
        result['tested_source'] = r.source_manifest(prepared,{profile if profile in ('serial','can') else 'host'})
        if profile == 'can':
            gate.require(os.geteuid() != 0,'CAN CI must run as a normal user; only ip/module operations use sudo')
            gate.require(shutil.which('ip') and shutil.which('sudo'),'CAN CI requires iproute2 and noninteractive sudo')
            if not Path('/sys/module/vcan').is_dir():
                command('load-vcan',['sudo','-n','modprobe','vcan'],budget=15)
            result['checks']['vcan_module'] = {'status':'passed','loaded':True}
        if can_prebuilt:
            gate.require(profile == 'can','--can-prebuilt belongs only to can')
            build = prebuilt_can(can_prebuilt,prepared,rules['targets'])
            build_path = out/'build/prebuilt.json'
            r.save_json(build_path,build)
        else:
            build = build_targets(source_root=prepared,target_ids=rules['targets'],
                profile='aarch64' if profile == 'aarch64' else 'host',toolchain_root=toolchain_root,
                output_root=out/'builds',timeout=min(timeout,120))
            build_path = Path(build['report_directory'])/'run.json'
        result['build_report'] = build_path.relative_to(out).as_posix()
        result['checks']['build'] = gate.validate_build(build,profile,rules['targets'])
        if profile == 'aarch64':
            result['execution']['arm64_build'] = 'passed'
            result['execution_mode'] = 'cross_build_only'
        else:
            argv = [sys.executable,'-W','error::ResourceWarning','-m','pytest','tests/'+profile,'-q',
                    '--source-root',str(prepared),'--evidence-root',str(out/'tests'),
                    '--junitxml='+str(out/'junit.xml'),'--timeout-scale='+str(timeout_scale)]
            if can_prebuilt:
                argv.extend(['--can-prebuilt',str(Path(can_prebuilt).resolve())])
            child = command('pytest',argv,expected=tuple(range(6)),
                            extra={'TESTLAB_EVIDENCE_ROOT':str(work/'host-cases')})
            result['pytest_exitcode'] = child['returncode']
            reports = list((out/'tests').glob('*/run.json'))
            gate.require(len(reports) == 1,'Expected exactly one pytest run')
            result['pytest_report'] = reports[0].relative_to(out).as_posix()
            result['checks']['pytest'] = gate.validate_pytest(reports[0],rules['required_nodes'],
                harness_digest=result['harness']['digest'],source_digest=result['tested_source']['digest'])
            gate.require(child['returncode'] == 0,'Pytest process returned a nonzero code')
            result['execution']['host_runtime'] = 'passed'
        result.update(status='passed',exitcode=0)
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as exc:
        result['errors'].append(str(exc))
        result['status'] = ('error' if build and build.get('status') == 'error' else
                            'failed' if result.get('pytest_exitcode') is not None or result.get('build_report') else 'error')
        result['exitcode'] = 1 if result['status'] == 'failed' else 2
    finally:
        copy_evidence(work/'host-cases',out/'host-evidence')
        shutil.rmtree(work)
        if captured:
            try:
                result['inputs_unchanged'] = (r.source_manifest(source,{'host'}) == result['source_input'] and
                                               r.harness_manifest() == result['harness'])
                if not result['inputs_unchanged']:
                    result.update(status='error',exitcode=2)
                    result['errors'].append('Source or harness changed during CI execution')
            except (ValueError,OSError) as exc:
                result.update(status='error',exitcode=2)
                result['errors'].append('Input recheck: '+str(exc))
        result['finished_at'] = r.now()
        result['evidence'] = gate.inventory(out)
        r.save_json(out/'ci.json',result)
        if result['status'] == 'passed':
            try:
                gate.verify_profile(out/'ci.json')
            except (ValueError,OSError,KeyError,TypeError) as exc:
                result.update(status='error',exitcode=2)
                result['errors'].append('Final evidence gate: '+str(exc))
                r.save_json(out/'ci.json',result)
    return result

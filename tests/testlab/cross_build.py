# SPDX-License-Identifier: Apache-2.0
"""Verified Gemstone SDK build profile; target programs are never executed."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import re
import shlex
import shutil
import sys
import uuid

from .build import (PROJECT, default_source_root, elf_info, git_state, now,
                    reference_state, run_logged, sha256, source_snapshot)
from .targets import select_targets
from . import toolchain as sdk


def cross_build_targets(*, source_root=None, target_ids=None, build_root=None,
                        output_root=None, cc=None, cxx=None, timeout=60.0,
                        toolchain_root=None):
    targets = select_targets(target_ids)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Build timeout must be finite and positive')
    source = Path(source_root or default_source_root()).resolve()
    if not source.is_dir():
        raise ValueError('Source root is not a directory: '+str(source))
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    out = Path(output_root or PROJECT/'artifacts/testlab').resolve()/run_id
    logs = out/'build'
    logs.mkdir(parents=True,exist_ok=False)
    builds = Path(build_root or PROJECT/'build/testlab').resolve()
    before = source_snapshot(source,targets)
    lock = sdk.lock_data()
    report = {
        'schema_version':1,'work_package':'WP-08','run_id':run_id,'started_at':now(),
        'profile':'aarch64','stage':'build','status':'error','execution_mode':'cross_build_only',
        'source':{'root':str(source),'selection':'explicit_working_tree' if source_root else 'default_working_tree',
                  'git':git_state(source),'inputs':before,'reference':reference_state(before)},
        'environment':{'platform':platform.platform(),'python':sys.version,
                       'inherited_build_variables_removed':list(sdk.CLEARED)},
        'toolchain':{'lock':lock,'requested_root':str(toolchain_root) if toolchain_root else None},
        'tools':{},'targets':[],'report_directory':str(out),
        'execution':{'host_runtime':'not_run','arm64_build':'not_run',
                     'board_runtime':'not_run','github_hosted_runner':'not_executed'},
    }
    commands, env, verified = [],sdk.clean_environment(),False

    def command(argv,name,deadline=10):
        record = run_logged(argv,source,logs/(name+'.log'),deadline,env)
        commands.append(record)
        if record.get('error') or record['process_status'] != 'passed' or record['returncode'] != 0 or record['timed_out']:
            raise sdk.ToolchainError('Command failed: '+name+'; see '+record['log'])
        return record,(logs/(name+'.log')).read_text(errors='replace')

    preflight_error = None
    try:
        if cc is not None or cxx is not None:
            raise sdk.ToolchainError('aarch64 uses only locked SDK compilers; --cc/--cxx overrides are not accepted')
        if (platform.system(),platform.machine().lower()) != (lock['host']['system'],lock['host']['machine']):
            raise sdk.ToolchainError('This pinned SDK requires a Linux x86_64 host')
        if toolchain_root is None:
            raise sdk.ToolchainError('aarch64 requires --toolchain-root; host fallback is disabled')
        root = Path(toolchain_root).resolve()
        report['toolchain']['before_build'] = sdk.verify_tree(root,lock)
        verified = True
        record,output = command(sdk.environment_command(root),'sdk-environment')
        env,values = sdk.parse_environment(output,root,env)
        if values.get('ARCH') != 'arm64' or values.get('CROSS_COMPILE') != lock['target']['triple']+'-':
            raise sdk.ToolchainError('SDK target environment mismatch')
        report['environment']['sdk_variables'] = values
        report['environment']['make_flag_variables'] = {key:env.get(key) for key in ('CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS')}
        make = shutil.which('make',path=env.get('PATH'))
        if make is None:
            raise sdk.ToolchainError('make is unavailable')
        record,output = command([make,'--version'],'tool-make')
        report['tools']['make'] = {'path':make,'argv':[make],'version':output.splitlines()[0],'command':record,'status':'passed'}
        for key,variable in (('cc','CC'),('cxx','CXX'),('readelf','READELF')):
            if key == 'cc' and not any(t.language == 'c' for t in targets):
                continue
            if key == 'cxx' and not any(t.language == 'cpp' for t in targets):
                continue
            argv = sdk.compiler_spec(values.get(variable),root,env)
            if key != 'readelf' and argv[1:] != ['--sysroot='+str(root/'sysroot')]:
                raise sdk.ToolchainError('SDK compiler sysroot argument mismatch')
            record,output = command([*argv,'--version'],'tool-'+key)
            item = {'path':argv[0],'argv':argv,'version':output.splitlines()[0],'command':record,'status':'passed'}
            if key != 'readelf':
                for flag,field in (('-dumpmachine','target_triple'),('-dumpfullversion','compiler_version'),('--print-sysroot','sysroot')):
                    _,text = command([*argv,flag],'tool-'+key+'-'+field)
                    item[field] = text.strip()
                if item['target_triple'] != lock['target']['triple'] or item['compiler_version'] != lock['compiler_version']:
                    raise sdk.ToolchainError('SDK compiler identity mismatch')
                if Path(item['sysroot']).resolve() != root/'sysroot':
                    raise sdk.ToolchainError('Compiler selected a different sysroot')
            report['tools'][key] = item
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as exc:
        preflight_error = str(exc)
        report['toolchain']['error'] = preflight_error

    for target in targets:
        directory = builds/'aarch64'/target.id/run_id
        directory.mkdir(parents=True,exist_ok=False)
        binary = directory/target.binary
        item = {'id':target.id,'language':target.language,'source_directory':target.directory,
                'profile':'aarch64','build_directory':str(directory),'status':'error',
                'expected_binary':str(binary),'binary':None,'command':None}
        missing = [name for name in ('common.mk',*target.inputs) if not (source/name).is_file()]
        if preflight_error:
            item['error'] = 'SDK preflight: '+preflight_error
        elif missing:
            item['error'] = 'Missing source inputs: '+', '.join(missing)
        else:
            key = 'cc' if target.language == 'c' else 'cxx'
            argv = [report['tools']['make']['path'],'-C',str(source/target.directory),
                    'PROJDIR='+str(source),'BUILDDIR='+str(directory),
                    ('CC=' if key == 'cc' else 'CXX=')+shlex.join(report['tools'][key]['argv'])]
            record = run_logged(argv,source,logs/(target.id+'.log'),timeout,env)
            commands.append(record)
            item.update(command=record,compiler=key)
            if record.get('error') or record['process_status'] == 'error':
                item['error'] = record.get('error','Managed build process failed')
            elif record['returncode'] != 0 or record['timed_out']:
                item.update(status='failed',error='Build timed out' if record['timed_out'] else 'Make returned a nonzero exit code')
            else:
                try:
                    info = elf_info(binary,expected_machine=lock['target']['elf_machine'],
                                    expected_bits=lock['target']['elf_class_bits'],
                                    expected_byte_order=lock['target']['byte_order'])
                    if info['interpreter'] != '/lib/ld-linux-aarch64.so.1':
                        raise ValueError('Unexpected AArch64 Linux program interpreter')
                    record,text = command([*report['tools']['readelf']['argv'],'-h','-l','-d','-V',str(binary)],target.id+'-readelf')
                    item['binary'] = {'path':str(binary),'sha256':sha256(binary),'size_bytes':binary.stat().st_size,
                                      'elf':info,'readelf':record,
                                      'needed_libraries':sorted(set(re.findall(r'Shared library: \[([^\]]+)\]',text))),
                                      'required_symbol_versions':sorted(set(re.findall(r'Name: ((?:GLIBC|GLIBCXX|CXXABI)_[\w.]+)',text)))}
                    item['status'] = 'passed'
                except (ValueError,OSError) as exc:
                    item.update(status='failed',error='Build artifact validation: '+str(exc))
        if item['command'] is None:
            (logs/(target.id+'.log')).write_text(item['error']+'\n')
        report['targets'].append(item)

    after = source_snapshot(source,targets)
    report['source']['inputs_unchanged_during_build'] = before == after
    if before != after:
        report['source']['inputs_after_build'] = after
    sdk_unchanged = False
    if verified:
        try:
            report['toolchain']['after_build'] = sdk.verify_tree(root,lock)
            sdk_unchanged = True
        except (ValueError,OSError,RuntimeError) as exc:
            report['toolchain']['after_build'] = {'status':'error','error':str(exc)}
    report['toolchain']['payload_unchanged_during_build'] = sdk_unchanged
    statuses = [item['status'] for item in report['targets']]
    report['status'] = ('error' if preflight_error or not sdk_unchanged or before != after or 'error' in statuses
                        else 'failed' if 'failed' in statuses else 'passed')
    report['execution']['arm64_build'] = report['status']
    report['finished_at'] = now()
    (out/'run.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'commands.jsonl').write_text(''.join(json.dumps(c)+'\n' for c in commands))
    return report

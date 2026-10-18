# SPDX-License-Identifier: Apache-2.0
"""Fail-closed CI evidence checks, independent of pytest and GitHub APIs."""
from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from . import reporting as r
from .build import PROJECT

PROFILES = ('host','serial','can','aarch64')
CONTRACT = PROJECT/'tests/ci-contract.json'


class AcceptanceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AcceptanceError(message)


def read(path):
    return json.loads(Path(path).read_text())


def contract():
    value = read(CONTRACT)
    require(value.get('schema_version') == 1,'Unsupported CI contract')
    require(set(value['profiles']) == set(PROFILES),'CI contract must define all four profiles')
    for name in ('host','serial','can'):
        nodes = value['profiles'][name]['required_nodes']
        require(nodes and len(nodes) == len(set(nodes)) and
                all(n.startswith('tests/'+name+'/') for n in nodes),'Invalid required CI case matrix')
    return value


def inventory(root):
    entries = []
    for path in sorted(Path(root).rglob('*')):
        require(not path.is_symlink(),'Evidence must not contain symlinks')
        if not path.is_file() or path == Path(root)/'ci.json':
            continue
        entries.append({'path':path.relative_to(root).as_posix(),'sha256':r.sha256(path),
                        'size_bytes':path.stat().st_size})
    return {'files':entries,'digest':r.digest_json(entries)}


def verify_inventory(root, manifest):
    require(manifest.get('files'),'CI evidence inventory is empty')
    require(manifest.get('digest') == r.digest_json(manifest['files']),'Evidence inventory digest differs')
    seen = set()
    for item in manifest['files']:
        require(item['path'] not in seen,'Duplicate evidence path')
        seen.add(item['path'])
        path = r.inside(Path(root),item['path'])
        require(path.is_file(),'Missing evidence: '+item['path'])
        require(path.stat().st_size == item['size_bytes'] and r.sha256(path) == item['sha256'],
                'Changed evidence: '+item['path'])


def validate_pytest(path, required_nodes, *, harness_digest=None, source_digest=None):
    path = Path(path)
    run = read(path)
    require(run.get('type') == 'testlab.run' and run.get('schema_version') == 1,'Unsupported pytest report')
    require(run.get('status') == 'passed' and run.get('pytest_exitcode') == 0,'Pytest did not pass')
    require(not run.get('policy_errors') and not run.get('selection',{}).get('collect_only'),
            'Pytest policy or collection-only run')
    cases = run.get('cases',[])
    require(cases and run.get('collected') == len(cases),'Empty or inconsistent collection')
    nodes = [case['nodeid'] for case in cases]
    require(len(nodes) == len(set(nodes)),'Duplicate pytest node')
    missing = sorted(set(required_nodes)-set(nodes))
    require(not missing,'Missing required cases: '+', '.join(missing[:5]))
    require(all(case['status'] == 'passed' for case in cases),'A case failed, skipped or did not run')
    require(run.get('counts') == {'passed':len(cases),'failed':0,'error':0,'skipped':0,'not_run':0},
            'Pytest counts disagree')
    if harness_digest is not None:
        require(run.get('harness',{}).get('digest') == harness_digest,'Pytest used a different harness')
    if source_digest is not None:
        require(run.get('source',{}).get('snapshot',{}).get('digest') == source_digest,'Pytest used different sources')
    for case in cases:
        value = read(r.inside(path.parent,case['result_artifact']))
        require(value['nodeid'] == case['nodeid'] and value['status'] == 'passed','Case report differs')
        phases = value.get('phases',[])
        require([p['phase'] for p in phases] == ['setup','call','teardown'] and
                all(p['outcome'] == 'passed' for p in phases),'Incomplete pytest phases')
        for item in value.get('artifacts',[]):
            artifact = r.inside(path.parent,item['path'])
            require(artifact.is_file() and artifact.stat().st_size == item['size_bytes'] and
                    r.sha256(artifact) == item['sha256'],'Case artifact differs')
    junit = ET.parse(path.parent/'junit.xml').getroot()
    xml_cases = junit.findall('.//testcase')
    require(len(xml_cases) == len(cases) and not any(junit.findall('.//'+name)
            for name in ('failure','error','skipped')),'JUnit and JSON disagree')
    return {'status':'passed','collected':len(cases),'required_cases':len(required_nodes),
            'pytest_exitcode':run['pytest_exitcode'],'run_id':run['run_id']}


def validate_build(report, profile, expected_ids):
    require(report.get('status') == 'passed','Build did not pass')
    targets = report.get('targets',[])
    require(Counter(t['id'] for t in targets) == Counter(expected_ids),'Build target matrix differs')
    expected_machine = 183 if profile == 'aarch64' else None
    for target in targets:
        require(target.get('status') == 'passed' and target.get('binary'),'Missing successful build artifact')
        elf = target['binary'].get('elf',{})
        require(elf.get('class_bits') == 64 and elf.get('machine') in (62,183),'Unsupported build ELF')
        if expected_machine:
            require(elf['machine'] == expected_machine and elf.get('byte_order') == 'little',
                    'Expected an AArch64 ELF')
    if profile == 'aarch64':
        require(report.get('execution_mode') == 'cross_build_only' and
                report.get('toolchain',{}).get('payload_unchanged_during_build'),'Unverified SDK build')
    return {'status':'passed','targets':len(targets),'profile':report['profile']}


def validate_lease(value):
    cleanup = value.get('cleanup',{})
    # Ownership tests intentionally trigger and record an initial refusal,
    # then restore their token and remove the owned interface in finally.
    # Keep that history; acceptance depends on the verified final state.
    require(cleanup.get('foreign_interface_touched') is False,'Foreign interface was touched or cleanup is unverified')
    require(not value.get('owned') or cleanup.get('owned_interface_removed') is True,
            'Owned interface was not removed')


def verify_profile(path):
    path = Path(path).resolve()
    value = read(path)
    require(value.get('type') == 'testlab.ci' and value.get('schema_version') == 1,'Unsupported CI report')
    require(value.get('profile') in PROFILES and value.get('status') == 'passed' and
            value.get('exitcode') == 0,'CI profile did not pass')
    require(value.get('inputs_unchanged') is True,'CI inputs changed during execution')
    require(value.get('contract_sha256') == r.sha256(CONTRACT),'CI contract differs')
    verify_inventory(path.parent,value['evidence'])
    rule = contract()['profiles'][value['profile']]
    validate_build(read(r.inside(path.parent,value['build_report'])),value['profile'],rule['targets'])
    if value['profile'] != 'aarch64':
        require(value.get('pytest_report'),'Missing required pytest report')
        validate_pytest(r.inside(path.parent,value['pytest_report']),rule['required_nodes'],
            harness_digest=value['harness']['digest'],source_digest=value['tested_source']['digest'])
    records = [read(p) for p in path.parent.rglob('process.json')]
    require(records,'No process evidence')
    for record in records:
        require(not record.get('cleanup_errors') and all(record.get('cleanup',{}).get(k)
                for k in ('group_gone','leader_reaped','owned_pipe_fds_closed','selector_closed')),
                'Process cleanup is incomplete')
    for lease in path.parent.rglob('lease.json'):
        validate_lease(read(lease))
    return value


def verify_profiles(paths, output, *, require_hosted=False, expected_commit=None, job_results=None,
                    expected_context=None):
    result = {'schema_version':1,'type':'testlab.ci_acceptance','started_at':r.now(),
              'status':'error','github_hosted_runner':'not_executed','profiles':[],'errors':[]}
    try:
        require(len(paths) == len(PROFILES),'Exactly four CI reports are required')
        values = [verify_profile(p) for p in paths]
        require(Counter(v['profile'] for v in values) == Counter(PROFILES),'Duplicate or missing CI profile')
        for field in ('contract_sha256',):
            require(len({v[field] for v in values}) == 1,'Mixed '+field)
        for field in ('source_input','harness'):
            require(len({v[field]['digest'] for v in values}) == 1,'Profiles tested different '+field)
        commits = {v['repository'].get('commit') for v in values}
        require(len(commits) == 1,'Profiles tested different commits')
        if expected_commit:
            require(commits == {expected_commit},'Tested commit does not match expected commit')
        if require_hosted:
            contexts = [v['github'] for v in values]
            require(all(c.get('actions') == 'true' and c.get('run_id') and c.get('repository') and
                        c.get('run_attempt') for c in contexts),'Missing hosted runner context')
            require(len({(c['repository'],c['run_id'],c['run_attempt']) for c in contexts}) == 1,
                    'Artifacts belong to different workflow attempts')
            require(expected_context and all(contexts[0].get(k) == expected_context.get(k)
                    for k in ('repository','run_id','run_attempt')),'Artifacts do not belong to this workflow attempt')
            require(expected_commit and next(iter(commits)),'Hosted acceptance requires an exact commit')
            require(isinstance(job_results,dict) and set(job_results) == set(PROFILES) and
                    all(v == 'success' for v in job_results.values()),'A required GitHub job failed or was skipped')
            result['github_hosted_runner'] = 'passed'
            context = contexts[0]
            result['run_url'] = 'https://github.com/'+context['repository']+'/actions/runs/'+context['run_id']
        result.update(status='passed',profiles=[v['profile'] for v in values],tested_commit=next(iter(commits)),
                      source_digest=values[0]['source_input']['digest'],harness_digest=values[0]['harness']['digest'])
    except (ValueError,OSError,KeyError,TypeError,ET.ParseError) as exc:
        result['errors'].append(str(exc))
    result.update(finished_at=r.now(),exitcode=0 if result['status'] == 'passed' else 1)
    r.save_json(Path(output).resolve(),result)
    return result

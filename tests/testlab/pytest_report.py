# SPDX-License-Identifier: Apache-2.0
"""Pytest owns outcomes and JUnit; this plugin adds portable case evidence."""
from collections import Counter
import json
from pathlib import Path
import shlex
import shutil
import pytest

from .build import PROJECT, default_source_root, git_state
from . import reporting as r


class RunReporter:
    def __init__(self, config):
        self.config = config
        self.root = r.run_directory(config.getoption('--evidence-root'))
        self.source_root = (config.getoption('--source-root') or default_source_root()).resolve()
        self.cases = {}
        self.collection_errors = []
        self.policy_errors = []
        self.manifest = {'schema_version': r.SCHEMA, 'type': 'testlab.run', 'run_id': self.root.name,
                         'status': 'running', 'started_at': r.now(), 'cases': []}
        self.persist()

    def persist(self):
        r.save_json(self.root/'run.json', self.manifest)

    def case_directory(self, nodeid):
        path = self.root/'cases'/r.case_id(nodeid)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def collect(self, session):
        for item in session.items:
            parameters = getattr(getattr(item, 'callspec', None), 'params', {})
            parameters = {name: {'type':'bytes','hex':value.hex()} if isinstance(value,bytes)
                          else value if value is None or isinstance(value,(str,int,float,bool))
                          else {'type':type(value).__name__} for name,value in parameters.items()}
            self.cases[item.nodeid] = {'id': r.case_id(item.nodeid), 'nodeid': item.nodeid,
                'suite': r.suite_of(item.nodeid), 'phases': [],
                'parameters': parameters,
                'required': bool(item.get_closest_marker('can') or item.get_closest_marker('serial'))}
            self.case_directory(item.nodeid)
        expected = self.config.getoption('--testlab-exact-node')
        if expected and [item.nodeid for item in session.items] != [expected]:
            self.policy_errors.append('exact_node_selection_did_not_collect_exactly_one_case')
            raise pytest.UsageError('Reproduction must collect exactly the recorded node')
        suites = {value['suite'] for value in self.cases.values()} or {
            r.suite_of(str(value)) for value in self.config.args}
        self.suites = suites
        try:
            source = r.source_manifest(self.source_root, suites, self.root/'inputs/source')
            lock = json.loads((PROJECT/'source.lock.json').read_text())
            self.manifest.update(
                source={'hint': str(self.source_root), 'snapshot': source, 'git': git_state(self.source_root),
                    'reference_repository': lock['repository'], 'reference_revision': lock['revision'],
                    'snapshot_directory': 'inputs/source'},
                harness=r.harness_manifest(), environment=r.environment(suites),
                context={'contracts': [name for suite, name in (('can', 'can_examples_v1'),
                           ('serial', 'serial_terminal_v1')) if suite in suites],
                    'backends': [name for suite, name in (('can', 'linux_vcan'), ('serial', 'linux_ptys'),
                                 ('host', 'linux_host')) if suite in suites],
                    'timeout_scale': self.config.getoption('--timeout-scale'),
                    'prebuilt_can_supplied': self.config.getoption('--can-prebuilt') is not None},
                selection={'nodes': list(self.cases), 'requested': [str(v) for v in self.config.args],
                           'collect_only': bool(self.config.option.collectonly)},
                execution={'host_runtime': 'not_run' if self.config.option.collectonly else 'selected',
                           'arm64_build': 'not_run', 'board_runtime': 'not_run'},
            )
            self.persist()
        except (OSError, ValueError) as exc:
            self.policy_errors.append('input_capture_failed: '+str(exc))
            raise pytest.UsageError('Cannot record test inputs: '+str(exc)) from exc

    def phase(self, item, call, report):
        case = self.cases.setdefault(item.nodeid, {'id': r.case_id(item.nodeid),
            'nodeid': item.nodeid, 'suite': r.suite_of(item.nodeid), 'required': False, 'phases': []})
        value = {'phase': report.when, 'outcome': report.outcome, 'duration_seconds': report.duration}
        if call.excinfo:
            value['error_type'] = call.excinfo.typename
            value['message'] = str(call.excinfo.value)[:8192]
        if report.failed or report.skipped:
            text = str(report.longrepr)
            value.update(detail=text[:65536], detail_truncated=len(text) > 65536)
        case['phases'].append(value)

    def finish(self, session, original_exitcode):
        provenance_ok = 'source' in self.manifest
        if provenance_ok:
            try:
                if r.source_manifest(self.source_root, self.suites)['digest'] != self.manifest['source']['snapshot']['digest']:
                    self.policy_errors.append('tested_source_changed_during_run')
                if r.harness_manifest()['digest'] != self.manifest['harness']['digest']:
                    self.policy_errors.append('test_harness_changed_during_run')
            except (OSError, ValueError) as exc:
                self.policy_errors.append('input_recheck_failed: '+str(exc))
        provenance_ok = provenance_ok and not self.policy_errors
        results = []
        for nodeid, case in self.cases.items():
            case['status'] = r.outcome(case['phases'])
            directory = self.case_directory(nodeid)
            try:
                case['expected'], case['actual'] = r.oracle(directory)
            except (OSError, ValueError, TypeError) as exc:
                case['expected'] = case['actual'] = None
                case['reporting_error'] = str(exc)
                self.policy_errors.append('case_evidence_unreadable: '+nodeid)
            case['artifacts'] = r.inventory(self.root, directory/'evidence')
            result = {'schema_version': r.SCHEMA, 'type': 'testlab.case', 'run_id': self.root.name, **case}
            r.save_json(directory/'result.json', result)
            if case['status'] in {'failed', 'error'}:
                reproduction = None
                if provenance_ok:
                    reproduction = {'schema_version': 1, 'nodeid': nodeid, 'suite': case['suite'],
                        'source_digest': self.manifest['source']['snapshot']['digest'],
                        'harness_digest': self.manifest['harness']['digest'],
                        'source_mode': 'packaged' if case['suite'] == 'host' else 'snapshot',
                        'timeout_scale': self.manifest['context']['timeout_scale']}
                    location = directory/'failure.json'
                    display = location.relative_to(PROJECT) if location.is_relative_to(PROJECT) else location
                    reproduction['command'] = ['python3','-m','tests.testlab','reproduce',str(display)]
                failure = {'schema_version': r.SCHEMA, 'type': 'testlab.case_failure',
                    'run_id': self.root.name, 'case': result, 'reproduction': reproduction}
                r.save_json(directory/'failure.json', failure)
                result['failure_artifact'] = (directory/'failure.json').relative_to(self.root).as_posix()
            if case['required'] and case['status'] == 'skipped':
                self.policy_errors.append('required_case_skipped: '+nodeid)
            results.append({key: result[key] for key in ('id', 'nodeid', 'suite', 'status') } |
                {'result_artifact': (directory/'result.json').relative_to(self.root).as_posix(),
                 **({'failure_artifact': result['failure_artifact']} if 'failure_artifact' in result else {})})
        # Keep pytest's public exit codes; a required skip/input-change gate uses
        # TESTS_FAILED (1), and the original pytest code remains visible.
        if self.policy_errors and int(session.exitstatus) == 0:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        counts = Counter(case['status'] for case in results)
        code = int(session.exitstatus)
        status = ('error' if self.policy_errors or self.collection_errors or code in (2,3,4,5) or counts['error'] else
                  'failed' if code or counts['failed'] else
                  'not_run' if self.config.option.collectonly else
                  'skipped' if counts['skipped'] and not counts['passed'] else
                  'passed' if counts['passed'] else 'not_run')
        commands = r.command_records(self.root)
        (self.root/'commands.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in commands))
        xml = Path(self.config.option.xmlpath).resolve()
        if xml.is_file() and xml != (self.root/'junit.xml'):
            shutil.copyfile(xml, self.root/'junit.xml')
        self.manifest.update(status=status, finished_at=r.now(), pytest_exitcode=code,
            original_pytest_exitcode=int(original_exitcode),
            counts={key: counts[key] for key in ('passed','failed','error','skipped','not_run')},
            collected=len(results), cases=results, collection_errors=self.collection_errors,
            policy_errors=self.policy_errors, command_records=len(commands),
            artifacts={'junit': 'junit.xml' if (self.root/'junit.xml').is_file() else None,
                       'commands': 'commands.jsonl'})
        self.persist()
        if self.collection_errors or self.policy_errors or (not results and code):
            r.save_json(self.root/'failure.json', {'schema_version':1, 'type':'testlab.run_failure',
                'run_id':self.root.name, 'pytest_exitcode':code,
                'collection_errors':self.collection_errors,'policy_errors':self.policy_errors})


def pytest_addoption(parser):
    parser.getgroup('testlab').addoption('--testlab-exact-node', help='Internal reproduction selection guard')


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    reporter = RunReporter(config)
    config._testlab_reporter = reporter
    if not config.option.xmlpath:
        config.option.xmlpath = str(reporter.root/'junit.xml')


def pytest_collection_finish(session):
    session.config._testlab_reporter.collect(session)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    result = yield
    item.config._testlab_reporter.phase(item, call, result.get_result())


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    result = yield
    session.config._testlab_reporter.finish(session, exitstatus)
    return result


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    result = yield
    report = result.get_result()
    if report.failed:
        text = str(report.longrepr)
        collector.config._testlab_reporter.collection_errors.append(
            {'nodeid': report.nodeid, 'detail': text[:65536], 'detail_truncated': len(text)>65536})


def pytest_terminal_summary(terminalreporter):
    reporter = terminalreporter.config._testlab_reporter
    terminalreporter.write_line('TestLab report: '+str(reporter.root/'run.json'))
    for nodeid, case in reporter.cases.items():
        if r.outcome(case['phases']) in {'failed','error'}:
            path = reporter.case_directory(nodeid)/'failure.json'
            display = path.relative_to(PROJECT) if path.is_relative_to(PROJECT) else path
            terminalreporter.write_line('TestLab reproduce: '+shlex.join(
                ['python3','-m','tests.testlab','reproduce',str(display)]))

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the actual pytest/vcan suite as UID 1000 in an isolated x86 Linux guest.

Requires an Ubuntu 24.04-compatible host runtime and the extracted QEMU/kernel
root described in docs/VM_REPRODUCTION.md. No host network privileges or KVM.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile
import zlib

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab.build import build_targets, default_source_root, sha256
from tests.testlab.process import run_process
from tests.testlab.reporting import source_names as all_source_names
from run_can_vm import cpio_newc


DISPATCH = r'''
import base64,gzip,hashlib,json,os,select,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path

def become_tester():
    os.setgroups([1000]); os.setgid(1000); os.setuid(1000)

config=json.loads(Path('/project/suite-config.json').read_text())
environment=os.environ.copy()
environment.update(PYTHONPATH='/opt/testlab-deps',PYTHONDONTWRITEBYTECODE='1',
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',HOME='/tmp',LC_ALL='C.UTF-8')
command=[sys.executable,'-m','pytest','-q','-p','no:cacheprovider',*config['nodes'],
         '--timeout-scale='+str(config['case_timeout_scale']),
         '--can-prebuilt=/project/prebuilt.json','--evidence-root=/artifacts/cases',
         '--junitxml=/artifacts/junit.xml']
if config['expected_tests']==1 and '::' in config['nodes'][0]:
    command += ['--testlab-exact-node',config['nodes'][0]]
if config.get('ci_profile'):
    command=[sys.executable,'-m','tests.testlab','ci','--profile','can',
             '--source-profile','proposed-fixes','--can-prebuilt','/project/prebuilt.json',
             '--output','/artifacts/ci-can','--timeout-scale',str(config['case_timeout_scale']),
             '--timeout',str(config['pytest_timeout']-15)]
print('TESTLAB_PYTEST_START '+json.dumps(config),flush=True)
child=subprocess.Popen(command,cwd='/project',env=environment,preexec_fn=become_tester,
                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
deadline=time.monotonic()+config['pytest_timeout']
size=0
try:
    with Path('/artifacts/pytest.log').open('wb',buffering=0) as log:
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise subprocess.TimeoutExpired(command,config['pytest_timeout'])
            if not select.select([child.stdout],[],[],min(0.25,remaining))[0]: continue
            chunk=os.read(child.stdout.fileno(),32768)
            if not chunk: break
            size+=len(chunk)
            if size>4*1024*1024: raise RuntimeError('pytest console exceeds 4 MiB')
            log.write(chunk)
            sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
    returncode=child.wait(timeout=5)
finally:
    if child.poll() is None: child.kill();child.wait(timeout=5)
    child.stdout.close()
cases=[json.loads(p.read_text()) for p in Path('/artifacts').rglob('case.json')]
leases=[json.loads(p.read_text()) for p in Path('/artifacts').rglob('lease.json')]
processes=[json.loads(p.read_text()) for p in Path('/artifacts').rglob('process.json')]
links=json.loads(subprocess.check_output(['/bin/ip','-details','-json','link','show']))
remaining=[p['ifname'] for p in links if p['ifname'].startswith('gtl')]
owned=[p for p in leases if p['owned']]
try:
    junit='/artifacts/ci-can/junit.xml' if config.get('ci_profile') else '/artifacts/junit.xml'
    suite=ET.parse(junit).getroot().find('testsuite')
except (OSError, ET.ParseError):
    suite=None
test_count=int(suite.get('tests','0')) if suite is not None else 0
def case_passed(case):
    common=(case['status']=='passed' and case['runner_uid']==1000 and case.get('target_uids')==[1000]*4)
    if case['kind']=='sender': return common and case['observer_closed']
    if case['kind']=='receiver': return common and case.get('publisher_closed') and case.get('pty_closed')
    if case['kind']=='argument': return common and case.get('returncode')==1
    return False
kind_counts={kind:sum(c.get('kind')==kind for c in cases) for kind in ('sender','receiver','argument')}
full=config['full_suite']
passed=(returncode==0 and suite is not None and test_count==config['expected_tests']
        and all(int(suite.get(k,'0'))==0 for k in ('failures','errors','skipped'))
        and all(case_passed(c) for c in cases)
        and (not full or (kind_counts=={'sender':3,'receiver':18,'argument':12} and len(owned)==24))
        and all(p.get('cleanup',{}).get('owned_interface_removed',False) for p in owned)
        and not remaining and all(p['cleanup']['group_gone'] and p['cleanup']['leader_reaped']
             and p['cleanup']['owned_pipe_fds_closed'] and not p.get('cleanup_errors') for p in processes))
summary={'status':'passed' if passed else 'failed','pytest_returncode':returncode,
 'context':{'python':sys.version,'kernel':os.uname().release,'machine':os.uname().machine,
            'case_timeout_scale':config['case_timeout_scale']},
 'tests':test_count,'expected_tests':config['expected_tests'],'scope':'full_suite' if full else 'selected_tests',
 'nodes':config['nodes'],'case_kinds':kind_counts,'runner_uid':1000,'cases':cases,'owned_interfaces':len(owned),
 'owned_interfaces_removed':sum(p.get('cleanup',{}).get('owned_interface_removed',False) for p in owned),
 'remaining_interfaces':remaining,'process_records':len(processes)}
if config.get('ci_profile'):
    ci_path=Path('/artifacts/ci-can/ci.json')
    ci=json.loads(ci_path.read_text()) if ci_path.exists() else {}
    summary.update(runner_mode='ci_profile',ci_returncode=returncode,pytest_returncode=ci.get('pytest_exitcode'))
    passed=passed and ci.get('status')=='passed' and ci.get('pytest_exitcode')==0
    summary['status']='passed' if passed else 'failed'
Path('/artifacts/guest-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
files={}
size=0
for p in Path('/artifacts').rglob('*'):
    if p.is_file() and (p.suffix in ('.json','.jsonl','.log','.xml') or '/inputs/source/' in p.as_posix()):
        data=p.read_bytes(); size+=len(data)
        if size>16*1024*1024: raise RuntimeError('Guest evidence exceeds 16 MiB')
        files[p.relative_to('/artifacts').as_posix()]=base64.b64encode(data).decode()
payload=gzip.compress(json.dumps(files).encode())
encoded=base64.b64encode(payload).decode()
print('WP05_EXPORT_BEGIN '+hashlib.sha256(payload).hexdigest(),flush=True)
for index in range(0,len(encoded),2048):
    print('WP05_EXPORT_CHUNK '+str(index//2048)+' '+encoded[index:index+2048],flush=True)
print('WP05_EXPORT_END',flush=True)
print('WP05_GUEST_RESULT '+json.dumps({'status':summary['status'],'tests':test_count,'uid':1000}),flush=True)
raise SystemExit(0 if passed else 1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest-root", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, help="Current examples tree; never checked out or reset")
    parser.add_argument('--ci-profile',action='store_true',help='Run the complete WP-09 CAN CI entry in the guest')
    parser.add_argument("--pytest-node", help="One selected pytest node, for focused reproductions")
    parser.add_argument("--expected-tests", type=int, help="Required positive count when --pytest-node is used")
    parser.add_argument("--timeout", type=float, default=600, help="Total QEMU budget in seconds (default: 600)")
    parser.add_argument("--case-timeout-scale", type=float, default=4,
                        help="Explicit TCG case budget multiplier (default: 4; native pytest defaults to 1)")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 30:
        parser.error("--timeout must be finite and exceed 30 seconds")
    if not math.isfinite(args.case_timeout_scale) or args.case_timeout_scale <= 0:
        parser.error("--case-timeout-scale must be finite and positive")
    if bool(args.pytest_node) != (args.expected_tests is not None) or (args.expected_tests is not None and args.expected_tests < 1):
        parser.error("Use --pytest-node and a positive --expected-tests together")
    if args.ci_profile and args.pytest_node:
        parser.error('--ci-profile runs the complete CAN matrix')
    root, out = args.guest_root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = (args.source_root or default_source_root()).resolve()
    build_source=source
    if args.ci_profile:
        build_source=out/'modified-examples'
        prepared=run_process([sys.executable,str(BASE/'tools/prepare_can_fix.py'),
            '--source-root',str(source),'--output',str(build_source)],cwd=BASE,
            log_dir=out/'prepare-prebuilt',timeout=30)
        if prepared['status']!='passed':raise RuntimeError('CI prebuilt source preparation failed')
    build = build_targets(source_root=build_source, target_ids=["can.c.sender", "can.cpp.sender", "can.c.receiver", "can.cpp.receiver"], output_root=out/"host-builds")
    if build["status"] != "passed":
        raise RuntimeError("Native CAN builds failed")
    assets = {}
    origins = {}

    def add(name, data, mode=0o644, origin="generated"):
        assets[name.lstrip("/")] = (stat.S_IFREG | mode, data)
        origins[name.lstrip("/")] = origin

    def file(path, name=None, mode=None):
        path = Path(path)
        add(str(name or path), path.read_bytes(), mode if mode is not None else stat.S_IMODE(path.stat().st_mode), str(path))

    def tree(path, destination):
        path = Path(path)
        for p in path.rglob("*"):
            if p.is_file() and not set(p.relative_to(path).parts) & {"__pycache__", "test", "tests", "dist-packages"}:
                file(p, Path(destination)/p.relative_to(path))

    file('/usr/bin/python3.12')
    tree('/usr/lib/python3.12', '/usr/lib/python3.12')
    file('/usr/bin/sudo', mode=0o4755)
    if args.ci_profile:
        file('/usr/bin/git')
    tree('/usr/libexec/sudo', '/usr/libexec/sudo')
    file('/lib/x86_64-linux-gnu/security/pam_permit.so')
    file('/usr/sbin/ip', '/bin/ip', mode=0o755)
    for name in ('libnss_files.so.2', 'libnss_dns.so.2'):
        if (Path('/lib/x86_64-linux-gnu')/name).exists():
            file(Path('/lib/x86_64-linux-gnu')/name)
    # Project sources include test files, so do not apply the stdlib tree filter.
    for path in (BASE/'tests').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            file(path, Path('/project')/path.relative_to(BASE), mode=0o644)
    source_names = {item['path'] for item in build['source']['inputs']['files']}
    if args.ci_profile:
        source_names.update(all_source_names(source,{'host'}))
        source_names.update(json.loads((BASE/'source.lock.json').read_text())['files'])
        for folder in ('tools','patches'):
            for path in (BASE/folder).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    file(path,Path('/project')/path.relative_to(BASE),mode=0o644)
    for role in ('sender', 'receiver'):
        source_names.update(p.relative_to(source).as_posix()
                            for p in (source/'canbus/python'/role).rglob('*.py'))
    for name in source_names:
        file(source/name, Path('/project/upstream/examples')/name, mode=0o644)
    for name in ('pytest.ini', 'source.lock.json'):
        file(BASE/name, '/project/'+name)
    lock = json.loads((BASE/'tests/python-dependencies.lock.json').read_text())
    for item in lock['packages']:
        wheel = args.wheels/item['file']
        if sha256(wheel) != item['sha256']:
            raise RuntimeError('Wheel checksum mismatch: '+wheel.name)
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.endswith('/'):
                    continue
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise RuntimeError('Invalid wheel member')
                add('/opt/testlab-deps/'+name, archive.read(name))
    prebuilt = {'source_digest': build['source']['inputs']['digest'], 'binaries': {}}
    for target in build['targets']:
        name = '/project/prebuilt/'+target['id']
        file(target['binary']['path'], name, mode=0o755)
        prebuilt['binaries'][target['id']] = {'path': name, 'sha256': target['binary']['sha256']}
    add('/project/prebuilt.json', json.dumps(prebuilt).encode())
    add('/project/suite-config.json', json.dumps({'nodes': [args.pytest_node] if args.pytest_node else ['tests/can'],
        'expected_tests': args.expected_tests if args.pytest_node else 36,
        'full_suite': not bool(args.pytest_node), 'pytest_timeout': args.timeout-30,
        'ci_profile':args.ci_profile,
        'case_timeout_scale': args.case_timeout_scale}).encode())
    # Include the dynamic loader and dependencies of trusted OS ELF files and
    # the binaries built above. No host configuration or credentials are copied.
    pending = [name for name, (_, data) in assets.items() if data[:4] == b'\x7fELF']
    scanned = set()
    while pending:
        name = pending.pop()
        if name in scanned:
            continue
        scanned.add(name)
        origin = origins[name]
        if origin == 'generated':
            continue
        result = subprocess.run(['ldd', origin], capture_output=True, text=True, timeout=10)
        if 'not found' in result.stdout:
            raise RuntimeError(result.stdout)
        for dependency in re.findall(r'(?:=>\s+|^\s*)(/[^\s]+)', result.stdout, re.M):
            key = dependency.lstrip('/')
            if key not in assets:
                file(dependency)
                pending.append(key)
    kernel = sorted((root/'boot').glob('vmlinuz-*'))[-1]
    version = kernel.name.removeprefix('vmlinuz-')
    modules = {p.name.split('.ko')[0].replace('_','-'): p for p in (root/'lib/modules'/version).rglob('*.ko*')}
    loaded = []

    def module(name):
        if name in loaded:
            return
        path = modules[name]
        if path.suffix == '.zst':
            data = subprocess.check_output(['zstd', '-d', '-c', str(path)])
        elif path.suffix == '.xz':
            import lzma
            data = lzma.decompress(path.read_bytes())
        else:
            data = path.read_bytes()
        match = re.search(rb'(?:^|\0)depends=([^\0]*)', data)
        for dep in (match.group(1).decode().split(',') if match else []):
            if dep:
                module(dep.replace('_','-'))
        add('/modules/'+name+'.ko', data)
        loaded.append(name)
    for name in ('can', 'can-raw', 'vcan'):
        module(name)
    busybox = root/'usr/bin/busybox'
    if not busybox.exists():
        busybox = root/'bin/busybox'
    file(busybox, '/bin/busybox', mode=0o755)
    add('/etc/passwd', b'root:x:0:0:root:/root:/bin/sh\ntester:x:1000:1000:TestLab:/tmp:/bin/sh\n')
    add('/etc/group', b'root:x:0:\ntester:x:1000:\n')
    add('/etc/nsswitch.conf', b'passwd: files\ngroup: files\nshadow: files\nhosts: files\n')
    add('/etc/hosts', b'127.0.0.1 localhost testlab\n')
    add('/etc/sudoers', b'Defaults !use_pty\nDefaults !pam_session\nDefaults secure_path="/usr/bin:/bin"\ntester ALL=(root) NOPASSWD: /bin/ip\n', mode=0o440)
    add('/etc/pam.d/sudo', b'auth sufficient /lib/x86_64-linux-gnu/security/pam_permit.so\naccount sufficient /lib/x86_64-linux-gnu/security/pam_permit.so\nsession sufficient /lib/x86_64-linux-gnu/security/pam_permit.so\n')
    add('/guest/dispatch.py', DISPATCH.encode())
    init = '#!/bin/sh\nexport PATH=/usr/bin:/bin\nset -eu\necho TESTLAB_INIT_START\nmount -t proc proc /proc\nmount -t sysfs sysfs /sys\nmount -t devtmpfs devtmpfs /dev\nmkdir -p /dev/pts\nmount -t devpts -o mode=0620,ptmxmode=0666 devpts /dev/pts\nln -sf pts/ptmx /dev/ptmx\nhostname testlab\n'
    init += ''.join('insmod /modules/'+name+'.ko\n' for name in loaded)
    init += 'echo TESTLAB_DISPATCH_START\nset +e\n/usr/bin/python3.12 -u /guest/dispatch.py\nrc=$?\necho "WP05_GUEST_EXIT $rc"\npoweroff -f\n'
    add('/init', init.encode(), mode=0o755)
    directories = {'bin','dev','dev/pts','proc','sys','tmp','artifacts','run/sudo/ts','var/lib/sudo','root'}
    for name in assets:
        directories.update(str(p) for p in Path(name).parents if str(p) != '.')
    entries = [(name, stat.S_IFDIR | (0o777 if name in ('tmp','artifacts') else 0o755), b'', 0, 0)
               for name in sorted(directories, key=lambda n: (n.count('/'), n))]
    entries.append(('dev/console', stat.S_IFCHR | 0o600, b'', 5, 1))
    for applet in ('sh','mount','insmod','hostname','poweroff','ln','mkdir'):
        entries.append(('bin/'+applet, stat.S_IFLNK | 0o777, b'busybox', 0, 0))
    entries.extend((name, mode, data, 0, 0) for name, (mode, data) in sorted(assets.items()))
    initramfs = out/'suite-initramfs.cpio'
    initramfs.write_bytes(cpio_newc(entries))
    (out/'guest-init.sh').write_text(init)
    (out/'guest-runtime.json').write_text(json.dumps({'kernel': version, 'kernel_sha256': sha256(kernel),
        'modules': loaded, 'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'origin': origins[name]}
                                   for name, (_,data) in assets.items()}}, indent=2)+'\n')
    qemu = root/'usr/bin/qemu-system-x86_64'
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(root/'usr/lib/x86_64-linux-gnu')
    env['QEMU_MODULE_DIR'] = str(root/'usr/lib/x86_64-linux-gnu/qemu')
    command = [str(qemu), '-L', str(root/'usr/share/qemu'), '-bios', str(root/'usr/share/seabios/bios-256k.bin'),
        '-machine','pc','-accel','tcg,thread=single','-cpu','max','-m','768M','-smp','1',
        '-nodefaults','-display','none','-serial','stdio','-monitor','none','-no-reboot',
        '-kernel',str(kernel),'-initrd',str(initramfs),'-append','console=ttyS0 rdinit=/init panic=1 loglevel=3']
    result = run_process(command, log_dir=out/'qemu', env=env, timeout=args.timeout, max_output_bytes=16*1024*1024)
    text = (out/'qemu/stdout.log').read_text(errors='replace').replace('\r','')
    (out/'guest-console.log').write_text('\n'.join(line for line in text.splitlines()
                                  if not line.startswith('WP05_EXPORT_CHUNK '))+'\n')
    begin = re.search(r'^WP05_EXPORT_BEGIN ([a-f0-9]+)$', text, re.M)
    if not begin:
        raise RuntimeError('Guest evidence was not exported; see guest-console.log and qemu/stderr.log')
    chunk_lines = re.findall(r'^WP05_EXPORT_CHUNK (\d+) ([A-Za-z0-9+/=]+)$', text, re.M)
    if [int(i) for i, _ in chunk_lines] != list(range(len(chunk_lines))):
        raise RuntimeError('Missing guest evidence chunks')
    payload = base64.b64decode(''.join(value for _, value in chunk_lines), validate=True)
    if hashlib.sha256(payload).hexdigest() != begin.group(1):
        raise RuntimeError('Guest evidence checksum mismatch')
    decoder = zlib.decompressobj(16+zlib.MAX_WBITS)
    raw = decoder.decompress(payload, 32*1024*1024)
    if not decoder.eof:
        raise RuntimeError('Guest export exceeds decoding budget or is incomplete')
    exports = json.loads(raw)
    target = out/'guest-artifacts'
    for name, encoded in exports.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts:
            raise RuntimeError('Invalid guest artifact path')
        destination = target/path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(base64.b64decode(encoded, validate=True))
    summary = json.loads((target/'guest-summary.json').read_text())
    passed = (summary['status']=='passed' and result['status']=='passed' and
              re.search(r'^WP05_GUEST_EXIT 0$',text,re.M) is not None)
    report = {'schema_version':2,'work_package':'WP-05','status':'passed' if passed else 'failed',
        'backend':'qemu_tcg_x86_linux_vcan','network':'none','runner_uid':summary['runner_uid'],
        'source_root':str(source),'source_digest':build['source']['inputs']['digest'],
        'summary':summary,'kernel':version,'initramfs_sha256':sha256(initramfs),
        'host_build_report':str(Path(build['report_directory'])/'run.json'),
        'qemu_report':str(out/'qemu/process.json'),'board_runtime':'not_run','github_hosted_runner':'not_executed'}
    (out/'run.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'tests':summary['tests'],'runner_uid':summary['runner_uid'],
                      'variants':[c['variant'] for c in summary['cases']],
                      'interfaces_removed':summary['owned_interfaces_removed'],'report':str(out/'run.json')},indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

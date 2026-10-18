# SPDX-License-Identifier: Apache-2.0
"""Build current sources or reproduce one recorded TestLab case."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tarfile

from .build import build_targets
from .targets import BY_ID, TARGETS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("targets", help="List the six compiled targets")
    ci = commands.add_parser('ci', help='Run one complete CI profile with mandatory evidence checks')
    ci.add_argument('--profile',required=True,choices=('host','serial','can','aarch64'))
    ci.add_argument('--output',required=True,type=Path,help='New evidence directory')
    ci.add_argument('--source-root',type=Path)
    ci.add_argument('--source-profile',choices=('working-tree','proposed-fixes'),default='working-tree')
    ci.add_argument('--toolchain-root',type=Path)
    ci.add_argument('--can-prebuilt',type=Path)
    ci.add_argument('--timeout',type=float,default=300)
    ci.add_argument('--timeout-scale',type=float,default=1)
    verify = commands.add_parser('ci-verify',help='Validate all four downloaded CI artifact reports')
    verify.add_argument('--report',required=True,action='append',type=Path)
    verify.add_argument('--output',required=True,type=Path)
    verify.add_argument('--require-hosted',action='store_true')
    install = commands.add_parser('toolchain', help='Verify and install the pinned Gemstone SDK')
    install.add_argument('--archive', type=Path, help='Existing archive; size and SHA-256 must match the lock')
    install.add_argument('--cache-root', type=Path, default=Path('build/toolchain-cache'))
    install.add_argument('--output', required=True, type=Path, help='New installation directory; never overwrite')
    install.add_argument('--timeout', type=float, default=300, help='Download deadline in seconds')
    replay = commands.add_parser('reproduce', help='Rebuild and run one verified case from failure.json')
    replay.add_argument('failure', type=Path)
    replay.add_argument('--output-root', type=Path, default=Path('artifacts/reproductions'))
    replay.add_argument('--source-root', type=Path, help='Optional existing tree; its input digest must match')
    replay.add_argument('--backend', choices=('native', 'can-vm'), default='native')
    replay.add_argument('--guest-root', type=Path)
    replay.add_argument('--wheels', type=Path)
    replay.add_argument('--timeout', type=float, default=180)
    build = commands.add_parser("build", help="Build the current example source tree")
    build.add_argument("--source-root", type=Path)
    build.add_argument("--target", action="append", choices=tuple(BY_ID))
    build.add_argument("--build-root", type=Path)
    build.add_argument("--output-root", type=Path)
    build.add_argument('--profile', choices=('host','aarch64'), default='host')
    build.add_argument('--toolchain-root', type=Path)
    build.add_argument("--cc", help="Host C compiler executable (default gcc), not a shell command")
    build.add_argument("--cxx", help="Host C++ compiler executable (default g++)")
    build.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if args.command == "targets":
        print(json.dumps([asdict(target) for target in TARGETS], indent=2))
        return 0
    if args.command == 'ci':
        from .ci import run_ci
        try:
            report = run_ci(profile=args.profile,output=args.output,source_root=args.source_root,
                source_profile=args.source_profile,toolchain_root=args.toolchain_root,
                can_prebuilt=args.can_prebuilt,timeout=args.timeout,timeout_scale=args.timeout_scale)
        except (ValueError,OSError) as exc:
            parser.error(str(exc))
        print(json.dumps({'status':report['status'],'profile':report['profile'],'exitcode':report['exitcode'],
            'report':str(args.output.resolve()/'ci.json'),'errors':report['errors']},indent=2))
        return report['exitcode']
    if args.command == 'ci-verify':
        from .ci import github_context
        from .ci_gate import verify_profiles
        results = None
        try:
            results = json.loads(os.environ.get('TESTLAB_JOB_RESULTS','null'))
        except ValueError:
            pass
        report = verify_profiles(args.report,args.output,require_hosted=args.require_hosted,
            expected_commit=os.environ.get('TESTLAB_EXPECTED_COMMIT'),job_results=results,
            expected_context=github_context())
        print(json.dumps(report,indent=2))
        return report['exitcode']
    if args.command == 'toolchain':
        from .toolchain import download_archive, extract_verified
        try:
            archive = args.archive or download_archive(args.cache_root,timeout=args.timeout)
            receipt = extract_verified(archive,args.output)
        except (ValueError,OSError,tarfile.TarError) as exc:
            print(json.dumps({'status':'error','error':str(exc)},indent=2))
            return 2
        print(json.dumps(receipt,indent=2))
        return 0
    if args.command == 'reproduce':
        from .reproduce import reproduce
        try:
            code, path, report = reproduce(args.failure, output_root=args.output_root,
                source_root=args.source_root, backend=args.backend, guest_root=args.guest_root,
                wheels=args.wheels, timeout=args.timeout)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            parser.error(str(exc))
        print(json.dumps({'status':report['status'],'pytest_exitcode':code,
                          'same_exact_node':report['same_exact_node'],'report':str(path)},indent=2))
        return code
    try:
        report = build_targets(source_root=args.source_root, target_ids=args.target,
                               build_root=args.build_root, output_root=args.output_root,
                               cc=args.cc, cxx=args.cxx, timeout=args.timeout,
                               profile=args.profile, toolchain_root=args.toolchain_root)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": report["status"], "run_id": report["run_id"],
                      "targets": [{"id": t["id"], "status": t["status"]} for t in report["targets"]],
                      "report": str(Path(report["report_directory"]) / "run.json")}, indent=2))
    return {"passed": 0, "failed": 1, "error": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

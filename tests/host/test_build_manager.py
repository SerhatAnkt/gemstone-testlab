# SPDX-License-Identifier: Apache-2.0
"""Regression checks for real source builds, provenance and failure reporting."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.testlab.build import PROJECT, build_targets
from tests.testlab.targets import select_targets


class BuildManagerTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get("TESTLAB_EVIDENCE_ROOT")
        if evidence:
            parent = Path(evidence).resolve()
            parent.mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=parent))
        else:
            temporary = tempfile.TemporaryDirectory(prefix="testlab-build-")
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.source = self.root / "source"
        shutil.copytree(PROJECT / "upstream/examples", self.source,
                        ignore=shutil.ignore_patterns("build", ".git"))

    def build(self, ids, **kwargs):
        return build_targets(source_root=self.source, target_ids=ids,
                             build_root=self.root / "binaries", output_root=self.root / "reports",
                             **kwargs)

    def cli_build(self, ids, *extra):
        argv = [sys.executable, "-m", "tests.testlab", "build", "--source-root", str(self.source),
                "--build-root", str(self.root / "binaries"),
                "--output-root", str(self.root / "reports")]
        for name in ids:
            argv.extend(["--target", name])
        result = subprocess.run([*argv, *extra], cwd=PROJECT, capture_output=True,
                                text=True, timeout=30)
        (self.root / "cli.stdout.log").write_text(result.stdout)
        (self.root / "cli.stderr.log").write_text(result.stderr)
        summary = json.loads(result.stdout)
        return result.returncode, json.loads(Path(summary["report"]).read_text())

    def test_changed_working_tree_changes_binary_and_provenance(self):
        git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
               "-c", "user.name=TestLab fixture", "-c", "user.email=testlab@example.invalid",
               "-C", str(self.source)]
        for args in (["init", "-q"], ["add", "."], ["commit", "-qm", "Local test fixture"]):
            subprocess.run([*git, *args], check=True, capture_output=True, timeout=5)
        first = self.build(["can.c.sender"])
        self.assertEqual(first["status"], "passed")
        self.assertFalse(first["source"]["git"]["dirty"])
        path = self.source / "canbus/c/sender/main.c"
        original_stat = path.stat()
        path.write_text(path.read_text().replace("Usage: %s", "WP02_CHANGED Usage: %s"))
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        second = self.build(["can.c.sender"])
        self.assertEqual(second["status"], "passed")
        self.assertTrue(second["source"]["git"]["dirty"])
        self.assertEqual(first["source"]["git"]["commit"], second["source"]["git"]["commit"])
        self.assertFalse(second["source"]["reference"]["selected_inputs_match"])
        self.assertNotEqual(first["source"]["inputs"]["digest"], second["source"]["inputs"]["digest"])
        binary = second["targets"][0]["binary"]["path"]
        result = subprocess.run([binary], capture_output=True, timeout=3)
        self.assertIn(b"WP02_CHANGED Usage:", result.stdout)
        (self.root / "changed-binary.stdout.log").write_bytes(result.stdout)

    def test_failed_rebuild_cannot_reuse_old_binary(self):
        first = self.build(["can.c.sender"])
        self.assertEqual(first["status"], "passed")
        old = first["targets"][0]["binary"]
        source = self.source / "canbus/c/sender/main.c"
        source.write_text("#error WP02_EXPECTED_COMPILE_FAILURE\n" + source.read_text())
        code, report = self.cli_build(["can.c.sender", "serial.c"])
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        failed, healthy = report["targets"]
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(healthy["status"], "passed")
        self.assertIsNone(failed["binary"])
        self.assertFalse(Path(failed["expected_binary"]).exists())
        self.assertNotEqual(failed["build_directory"], first["targets"][0]["build_directory"])
        self.assertIn("WP02_EXPECTED_COMPILE_FAILURE", Path(failed["command"]["log"]).read_text())
        self.assertEqual(hashlib.sha256(Path(old["path"]).read_bytes()).hexdigest(), old["sha256"])

    def test_missing_compiler_is_error_with_nonzero_cli_exit(self):
        code, report = self.cli_build(["can.c.sender"], "--cc", str(self.root / "missing-cc"))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["targets"][0]["status"], "error")
        self.assertIsNone(report["targets"][0]["binary"])
        self.assertIn("Executable not found", report["tools"]["cc"]["error"])

    def test_missing_header_is_reported_before_make(self):
        (self.source / "canbus/cpp/sender/can_sender.h").unlink()
        report = self.build(["can.cpp.sender"])
        self.assertEqual(report["status"], "error")
        target = report["targets"][0]
        self.assertIsNone(target["command"])
        self.assertIn("can_sender.h", target["error"])

    def test_empty_unknown_or_duplicate_selection_is_rejected(self):
        for ids in ([], ["unknown"], ["serial.c", "serial.c"]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                select_targets(ids)


if __name__ == "__main__":
    unittest.main()

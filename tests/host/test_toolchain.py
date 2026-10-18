# SPDX-License-Identifier: Apache-2.0
"""Small real archive fixtures test installer rejection without downloading an SDK."""
import io
import json
import os
from pathlib import Path
import shutil
import shlex
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tests.testlab.build import PROJECT, build_targets, elf_info
from tests.testlab import toolchain as sdk


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get('TESTLAB_EVIDENCE_ROOT')
        if evidence:
            parent = Path(evidence).resolve()
            parent.mkdir(parents=True,exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=parent))
        else:
            temporary = tempfile.TemporaryDirectory(prefix='testlab-sdk-')
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.expected = self.root/'expected'
        self.expected.mkdir()
        (self.expected/'env').write_bytes(b'# fixture SDK\n')
        self.destination = self.root/'installed'

    def archive(self, extra=(), normalized=()):
        path = self.root/'sdk.tar.gz'
        with tarfile.open(path,'w:gz') as package:
            info = tarfile.TarInfo('env')
            info.size = len((self.expected/'env').read_bytes())
            info.mode = 0o644
            package.addfile(info,io.BytesIO((self.expected/'env').read_bytes()))
            for name,target in extra:
                info = tarfile.TarInfo(name)
                if target is None:
                    info.size = 1
                    package.addfile(info,io.BytesIO(b'x'))
                else:
                    info.type = tarfile.SYMTYPE
                    info.linkname = target
                    package.addfile(info)
        manifest = sdk.tree_manifest(self.expected)
        lock = {'release':'test-fixture','archive':{'size_bytes':path.stat().st_size,
                'sha256':sdk.file_digest(path)},'normalized_symlinks':list(normalized),
                'installed_tree':{'sha256':manifest['digest'],'entries':len(manifest['files'])}}
        return path,lock

    def test_size_and_hash_rejected_before_creating_destination(self):
        archive,lock = self.archive()
        original = archive.read_bytes()
        for payload,reason in ((original+b'x','size'),(b'x'+original[1:],'SHA-256')):
            with self.subTest(reason=reason):
                archive.write_bytes(payload)
                with self.assertRaisesRegex(sdk.ToolchainError,reason):
                    sdk.extract_verified(archive,self.destination,lock)
                self.assertFalse(self.destination.exists())

    def test_traversal_and_external_links_are_rejected_and_owned_tree_removed(self):
        for name,target in (('../escape',None),('outside','../../host-file'),('external','/etc/passwd')):
            with self.subTest(name=name):
                archive,lock = self.archive([(name,target)])
                with self.assertRaises((tarfile.FilterError,sdk.ToolchainError)):
                    sdk.extract_verified(archive,self.destination,lock)
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.root/'escape').exists())

    def test_existing_user_directory_is_never_removed(self):
        archive,lock = self.archive()
        self.destination.mkdir()
        marker = self.destination/'keep-me'
        marker.write_text('owned by caller')
        with self.assertRaises(FileExistsError):
            sdk.extract_verified(archive,self.destination,lock)
        self.assertEqual(marker.read_text(),'owned by caller')

    def test_pinned_target_root_link_is_relocated_and_unlisted_link_is_rejected(self):
        link = self.expected/'sysroot/usr/lib/ssl/certs'
        link.parent.mkdir(parents=True)
        link.symlink_to('../../../etc/ssl/certs')
        transform = {'path':'sysroot/usr/lib/ssl/certs','archive_target':'/etc/ssl/certs',
                     'installed_target':'../../../etc/ssl/certs'}
        archive,lock = self.archive([(transform['path'],transform['archive_target'])],[transform])
        receipt = sdk.extract_verified(archive,self.destination,lock)
        self.assertEqual(receipt['status'],'passed')
        installed = self.destination/transform['path']
        self.assertTrue(installed.resolve().is_relative_to(self.destination.resolve()))
        self.assertEqual(os.readlink(installed),transform['installed_target'])
        shutil.rmtree(self.destination)
        lock['normalized_symlinks'] = []
        with self.assertRaises(sdk.ToolchainError):
            sdk.extract_verified(archive,self.destination,lock)
        self.assertFalse(self.destination.exists())

    def test_installed_content_mode_addition_removal_and_link_changes_are_detected(self):
        link = self.expected/'link'
        link.symlink_to('env')
        archive,lock = self.archive([('link','env')])
        sdk.extract_verified(archive,self.destination,lock)
        env = self.destination/'env'
        original = env.read_bytes()
        env.write_bytes(original+b'changed')
        with self.assertRaises(sdk.ToolchainError): sdk.verify_tree(self.destination,lock)
        env.write_bytes(original)
        env.chmod(0o755)
        with self.assertRaises(sdk.ToolchainError): sdk.verify_tree(self.destination,lock)
        env.chmod(0o644)
        extra = self.destination/'new-compiler'
        extra.write_text('unexpected')
        with self.assertRaises(sdk.ToolchainError): sdk.verify_tree(self.destination,lock)
        extra.unlink()
        env.unlink()
        with self.assertRaises(sdk.ToolchainError): sdk.verify_tree(self.destination,lock)
        env.write_bytes(original)
        installed_link = self.destination/'link'
        installed_link.unlink()
        installed_link.symlink_to('different-internal-path')
        with self.assertRaises(sdk.ToolchainError): sdk.verify_tree(self.destination,lock)
        installed_link.unlink()
        installed_link.symlink_to('env')
        self.assertEqual(sdk.verify_tree(self.destination,lock)['status'],'passed')

    def test_host_compiler_cannot_be_used_as_sdk_and_paths_with_spaces_are_parsed(self):
        root = self.root/'SDK with spaces'
        compiler = root/'toolchain/bin/aarch64-none-linux-gnu-gcc'
        compiler.parent.mkdir(parents=True)
        compiler.write_text('#!/bin/sh\nexit 0\n')
        compiler.chmod(0o755)
        environment = {'PATH':str(compiler.parent)+os.pathsep+os.environ['PATH']}
        with self.assertRaises(sdk.ToolchainError):
            sdk.compiler_spec(shutil.which('gcc'),root,environment)
        self.assertEqual(sdk.compiler_spec('aarch64-none-linux-gnu-gcc --sysroot='+str(root/'sysroot'),root,environment),
                         [str(compiler),'--sysroot='+str(root/'sysroot')])
        (root/'sysroot').mkdir()
        values = {'SDKTARGETSYSROOT':str(root/'sysroot'),'LDFLAGS':'-Wl,-O1 -L'+str(root/'sysroot/usr/lib')}
        selected,_ = sdk.parse_environment('TESTLAB_SDK_ENV='+json.dumps(values),root,{})
        self.assertEqual(shlex.split(selected['LDFLAGS']),['-Wl,-O1','-L'+str(root/'sysroot/usr/lib')])

    def test_wrong_machine_and_truncated_elf_are_rejected(self):
        native = Path(sys.executable).resolve()
        info = elf_info(native)
        with self.assertRaisesRegex(ValueError,'machine mismatch'):
            elf_info(native,expected_machine=183 if info['machine'] != 183 else 62)
        broken = self.root/'broken-elf'
        payload = bytearray(native.read_bytes()[:64])
        if info['class_bits'] == 64:
            struct.pack_into('<H' if info['byte_order'] == 'little' else '>H',payload,56,0)
        broken.write_bytes(payload)
        broken.chmod(0o755)
        with self.assertRaises(ValueError): elf_info(broken)

    def test_missing_sdk_and_compiler_override_produce_error_reports_without_fallback(self):
        for extra in ([],['--toolchain-root',str(self.root/'absent')],['--cc','gcc']):
            argv = [sys.executable,'-m','tests.testlab','build','--profile','aarch64','--target','can.c.sender',
                    '--build-root',str(self.root/'binaries'),'--output-root',str(self.root/'reports'),*extra]
            process = subprocess.run(argv,cwd=PROJECT,capture_output=True,text=True,timeout=20)
            self.assertEqual(process.returncode,2,process.stderr)
            report = json.loads(Path(json.loads(process.stdout)['report']).read_text())
            self.assertEqual(report['status'],'error')
            self.assertEqual(report['execution_mode'],'cross_build_only')
            self.assertFalse(report['tools'])
            self.assertEqual(report['targets'][0]['status'],'error')
            self.assertIsNone(report['targets'][0]['binary'])
            self.assertIsNone(report['targets'][0]['command'])
            self.assertFalse(Path(report['targets'][0]['expected_binary']).exists())


if __name__ == '__main__':
    unittest.main()

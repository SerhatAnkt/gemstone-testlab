# SPDX-License-Identifier: Apache-2.0
"""Pinned Gemstone SDK acquisition, extraction and complete payload verification."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import posixpath
import shlex
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.request

LOCK_PATH = Path(__file__).resolve().parents[1]/'toolchain.lock.json'
RECEIPTS = {'.testlab-toolchain-install.json', '.testlab-toolchain-manifest.json'}
SDK_KEYS = ('PATH','CC','CXX','SDKTARGETSYSROOT','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS',
            'ARCH','CROSS_COMPILE','READELF','PKG_CONFIG_PATH','PKG_CONFIG_SYSROOT_DIR')
CLEARED = ('MAKEFLAGS','GNUMAKEFLAGS','MFLAGS','MAKEOVERRIDES','MAKEFILES',
           'CC','CXX','CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS','CROSS_COMPILE',
           'BASH_ENV','ENV','LD_PRELOAD','LD_LIBRARY_PATH','GCC_EXEC_PREFIX',
           'COMPILER_PATH','LIBRARY_PATH','CPATH','C_INCLUDE_PATH','CPLUS_INCLUDE_PATH',
           'OBJC_INCLUDE_PATH','DEPENDENCIES_OUTPUT','SUNPRO_DEPENDENCIES','CCACHE_PREFIX')


class ToolchainError(ValueError):
    pass


def lock_data():
    return json.loads(LOCK_PATH.read_text())


def file_digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def digest_entries(entries):
    return hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_archive(path, lock=None):
    lock = lock or lock_data()
    path = Path(path)
    if path.stat().st_size != lock['archive']['size_bytes']:
        raise ToolchainError('Toolchain archive size does not match the lock')
    digest = file_digest(path)
    if digest != lock['archive']['sha256']:
        raise ToolchainError('Toolchain archive SHA-256 does not match the lock')
    return {'path':str(path.resolve()),'sha256':digest,'size_bytes':path.stat().st_size}


def tree_manifest(root):
    root = Path(root).resolve()
    entries, inode_hashes = [], {}
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            path = Path(directory)/name
            relative = path.relative_to(root).as_posix()
            if relative in RECEIPTS:
                continue
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                if not path.resolve().is_relative_to(root):
                    raise ToolchainError('SDK symlink escapes installation root: '+relative)
                entries.append({'path':relative,'kind':'symlink','target':target})
            elif stat.S_ISREG(info.st_mode):
                identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                digest = inode_hashes.get(identity)
                if digest is None:
                    digest = file_digest(path)
                    inode_hashes[identity] = digest
                entries.append({'path':relative,'kind':'file','size_bytes':info.st_size,
                                'sha256':digest,'executable':bool(info.st_mode & 0o111)})
            elif not stat.S_ISDIR(info.st_mode):
                raise ToolchainError('Unsupported installed SDK entry: '+relative)
    entries.sort(key=lambda item:item['path'])
    return {'files':entries,'digest':digest_entries(entries)}


def verify_tree(root, lock=None):
    lock = lock or lock_data()
    root = Path(root).resolve()
    if not root.is_dir():
        raise ToolchainError('Toolchain root does not exist: '+str(root))
    manifest = tree_manifest(root)
    if manifest['digest'] != lock['installed_tree']['sha256']:
        raise ToolchainError('Installed toolchain payload differs from the locked tree')
    if len(manifest['files']) != lock['installed_tree']['entries']:
        raise ToolchainError('Installed toolchain entry count mismatch')
    return {'status':'passed','root':str(root),'payload_sha256':manifest['digest'],
            'payload_entries':len(manifest['files']),'archive':lock['archive'],
            'release':lock['release'],'env_sha256':file_digest(root/'env')}


def normalized_members(package, destination, lock):
    """Relocate the two pinned target-root links, never links into the host."""
    members = package.getmembers()
    if len(members)>20000 or sum(m.size for m in members if m.isfile())>2*1024**3:
        raise ToolchainError('SDK archive exceeds extraction limits')
    transformations, names = [], set()
    for member in members:
        if member.name in names:
            raise ToolchainError('Duplicate SDK archive path: '+member.name)
        names.add(member.name)
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ToolchainError('Unsupported SDK archive entry')
        if member.issym() and member.linkname.startswith('/'):
            if not member.name.startswith('sysroot/'):
                raise ToolchainError('Absolute link outside SDK sysroot')
            original = member.linkname
            target = posixpath.relpath('sysroot/'+original.lstrip('/'),posixpath.dirname(member.name))
            transformations.append({'path':member.name,'archive_target':original,'installed_target':target})
            member = member.replace(linkname=target)
        # data_filter rejects traversal, special files, external and absolute hard links.
        tarfile.data_filter(member,str(destination))
        yield member
    if sorted(transformations,key=lambda x:x['path']) != lock.get('normalized_symlinks',[]):
        raise ToolchainError('SDK link normalization differs from the lock')


def extract_verified(archive, destination, lock=None):
    lock = lock or lock_data()
    verified = verify_archive(archive,lock)
    destination = Path(destination).resolve()
    # Ownership starts only after mkdir succeeds; never remove a caller's tree.
    destination.mkdir(parents=True,exist_ok=False)
    try:
        if not hasattr(tarfile,'data_filter'):
            raise ToolchainError('SDK extraction requires Python 3.12 or newer')
        with tarfile.open(archive,'r:gz') as package:
            members = list(normalized_members(package,destination,lock))
            package.extractall(destination,members=members,filter='data')
        payload = verify_tree(destination,lock)
        manifest = tree_manifest(destination)
        (destination/'.testlab-toolchain-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        receipt = {'schema_version':1,'status':'passed','verified_archive':verified,
                   'installed_tree':payload,'normalized_symlinks':lock.get('normalized_symlinks',[]),
                   'execution_mode':'cross_build_only'}
        (destination/'.testlab-toolchain-install.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return receipt
    except BaseException:
        shutil.rmtree(destination)
        raise


def download_archive(cache_root, *, timeout=300):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Download timeout must be finite and positive')
    lock = lock_data()
    cache = Path(cache_root).resolve()
    cache.mkdir(parents=True,exist_ok=True)
    target = cache/lock['archive']['name']
    if target.exists():
        verify_archive(target,lock)
        return target
    descriptor, temporary = tempfile.mkstemp(prefix='.testlab-sdk-',suffix='.partial',dir=cache)
    path = Path(temporary)
    started = time.monotonic()
    try:
        request = urllib.request.Request(lock['archive']['url'],
                                        headers={'User-Agent':'Gemstone-TestLab','Accept-Encoding':'identity'})
        with os.fdopen(descriptor,'wb') as output, urllib.request.urlopen(request,timeout=min(timeout,30)) as response:
            size = 0
            while chunk := response.read(1024*1024):
                if time.monotonic()-started > timeout:
                    raise TimeoutError('Toolchain download exceeded its deadline')
                size += len(chunk)
                if size > lock['archive']['size_bytes']:
                    raise ToolchainError('Downloaded SDK exceeds locked size')
                output.write(chunk)
        verify_archive(path,lock)
        path.replace(target)
        return target
    finally:
        path.unlink(missing_ok=True)


def clean_environment():
    result = os.environ.copy()
    for key in CLEARED:
        result.pop(key,None)
    return result


def environment_command(root):
    # Arguments are positional parameters, never interpolated shell fragments.
    script = '. "$1"\nexec "$2" -c "$3"'
    code = 'import os,json; print("TESTLAB_SDK_ENV="+json.dumps({k:os.environ.get(k) for k in '+repr(SDK_KEYS)+'}))'
    return ['/bin/bash','--noprofile','--norc','-c',script,'testlab-sdk',
            str(Path(root).resolve()/'env'),sys.executable,code]


def parse_environment(output, root, base):
    lines = [line.removeprefix('TESTLAB_SDK_ENV=') for line in output.splitlines()
             if line.startswith('TESTLAB_SDK_ENV=')]
    if len(lines) != 1:
        raise ToolchainError('SDK environment did not produce exactly one selected-variable record')
    values = json.loads(lines[0])
    environment = dict(base)
    for key in SDK_KEYS:
        if values.get(key) is not None:
            environment[key] = values[key]
    expected = (Path(root).resolve()/'sysroot').resolve()
    if Path(environment.get('SDKTARGETSYSROOT','')).resolve() != expected or not expected.is_dir():
        raise ToolchainError('SDK sysroot does not match the verified installation')
    # Make recipes expand flag strings through a shell. Upstream env does not
    # quote its -L paths, so keep the verified sysroot as one shell argument.
    for key in ('CFLAGS','CXXFLAGS','CPPFLAGS','LDFLAGS'):
        if key in environment:
            environment[key] = environment[key].replace(str(expected),shlex.quote(str(expected)))
    return environment,values


def compiler_spec(value, root, environment):
    # Upstream's env leaves the sysroot argument unquoted inside CC/CXX.
    # Quote that known path before parsing, including SDK paths with spaces.
    sysroot = str(Path(root).resolve()/'sysroot')
    argv = shlex.split((value or '').replace('--sysroot='+sysroot,'--sysroot='+shlex.quote(sysroot)))
    if not argv:
        raise ToolchainError('SDK compiler is not configured')
    resolved = shutil.which(argv[0],path=environment.get('PATH'))
    if resolved is None or not Path(resolved).resolve().is_relative_to(Path(root).resolve()):
        raise ToolchainError('SDK compiler must resolve inside the verified toolchain')
    return [str(Path(resolved).resolve()),*argv[1:]]

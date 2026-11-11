"""Real Git snapshots, failed upgrades, concurrency and read-only installs; no public network."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import library_location as lib
from managed_library_cache import online
from runtime_paths import library_paths
from runtime_storage import atomic_json, exclusive_lock


class ManagedCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='epoint-cache-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.install = self.base / '只读 安装'
        self.install.mkdir()
        self.origin = self.base / '源 库'
        self.origin.mkdir()
        self.cfg = {'version': 'test', 'mode': 'git', 'git_url': 'https://fixture.invalid/library.git',
                    'git_branch': 'main', 'git_repository_directory': '.',
                    'manifest': 'knowledge-manifest.json', 'git_checkout_path': 'legacy',
                    'cache_path': 'old-cache', 'offline_pack_path': 'minimal'}
        for args in (['init', '-b', 'main'], ['config', 'user.name', 'Test'],
                     ['config', 'user.email', 'test@example.com'], ['config', 'core.autocrlf', 'false']):
            lib._git(args, self.origin)
        self.initial = self.commit_revision('第一版')
        self.write_pack(self.install / 'minimal', '离线最小包', self.initial)
        (self.install / 'knowledge-base.json').write_bytes(json.dumps(self.cfg).encode())
        self.env = patch.dict(os.environ, {
            'EPOINT_CACHE_DIR': str(self.base / '用户 缓存'),
            # Redirect only this fixture URL using Git's own local test configuration.
            'GIT_CONFIG_COUNT': '1',
            'GIT_CONFIG_KEY_0': 'url.' + self.origin.as_uri() + '.insteadOf',
            'GIT_CONFIG_VALUE_0': self.cfg['git_url'],
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.skill = patch.object(lib, 'SKILL', self.install)
        self.skill.start()
        self.addCleanup(self.skill.stop)
        self.paths = library_paths(self.cfg)

    def write_pack(self, root, value, commit=None):
        root.mkdir(exist_ok=True, parents=True)
        data = json.dumps({'layouts': [], 'test_text': value}, ensure_ascii=False).encode('utf-8')
        (root / 'catalog.json').write_bytes(data)
        record = {'version': 'test', 'file_count': 1,
                  'files': {'catalog.json': hashlib.sha256(data).hexdigest()}}
        if commit:
            record['source_commit'] = commit
        (root / 'knowledge-manifest.json').write_bytes(json.dumps(record).encode())

    def commit_revision(self, text, valid=True):
        self.write_pack(self.origin, text)
        if not valid:
            (self.origin / 'catalog.json').write_bytes(b'corrupt update')
        lib._git(['add', '.'], self.origin)
        lib._git(['commit', '-m', 'test revision'], self.origin)
        return lib._git(['rev-parse', 'HEAD'], self.origin)

    def snapshot(self):
        return online(self.cfg, lib._git, lib.validate_manifest)

    def child(self, code):
        return subprocess.Popen([sys.executable, '-B', '-c',
            'import sys; sys.path.insert(0, ' + repr(str(SCRIPTS)) + '); ' + code],
            cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

    def test_online_then_offline_no_remote_call_or_install_write(self):
        before = {str(p.relative_to(self.install)): p.read_bytes() for p in self.install.rglob('*') if p.is_file()}
        root = self.snapshot()
        with patch.object(lib, 'git_library', side_effect=AssertionError('offline used network')):
            result = lib.resolve_library(cache_only=True)
        self.assertEqual(result[:3], (root, 'verified_full_cache', self.initial))
        after = {str(p.relative_to(self.install)): p.read_bytes() for p in self.install.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(root.is_relative_to(self.paths['root']))

    def test_upgrade_keeps_old_snapshot_and_marks_previous(self):
        first = self.snapshot()
        original = (first / 'catalog.json').read_bytes()
        newer = self.commit_revision('第二版')
        second = self.snapshot()
        self.assertNotEqual(first, second)
        self.assertEqual((first / 'catalog.json').read_bytes(), original)
        marker = json.loads(self.paths['marker'].read_text())
        self.assertEqual(marker['commit'], newer)
        self.assertEqual(marker['previous']['commit'], self.initial)

    def test_bad_upgrade_leaves_marker_and_active_snapshot_intact(self):
        first = self.snapshot()
        marker = self.paths['marker'].read_bytes()
        bad = self.commit_revision('坏版本', valid=False)
        result = lib.resolve_library()
        self.assertEqual(result[:3], (first, 'verified_full_cache', self.initial))
        self.assertIn('manifest_hash_mismatch', result[3])
        self.assertEqual(self.paths['marker'].read_bytes(), marker)
        self.assertFalse((self.paths['snapshots'] / bad).exists())
        self.assertEqual(list(self.paths['root'].glob('.candidate-*')), [])

    def test_dirty_active_recovers_previous(self):
        first = self.snapshot()
        self.commit_revision('第二版')
        second = self.snapshot()
        (second / 'catalog.json').write_bytes(b'dirty')
        result = lib.resolve_library(cache_only=True)
        self.assertEqual(result[0], first)
        self.assertIn('recovered_previous_snapshot: full_cache_dirty', result[3])

    def test_first_use_offline_uses_bundled_pack(self):
        with patch.object(lib, 'git_library', side_effect=AssertionError('offline used network')):
            result = lib.resolve_library(cache_only=True)
        self.assertEqual(result[:3], (self.install / 'minimal', 'local_verified_template', self.initial))

    def test_malformed_marker_does_not_block_valid_online_refresh(self):
        for value in ([], 'bad string', {'commit': 'wrong'}, None):
            atomic_json(self.paths['marker'], value)
            root = self.snapshot()
            self.assertEqual(root.name, self.initial)
        self.paths['marker'].write_bytes(b'{broken')
        self.assertEqual(self.snapshot().name, self.initial)

    def test_malformed_manifest_is_rejected_without_losing_previous(self):
        first = self.snapshot()
        marker = self.paths['marker'].read_bytes()
        (self.origin / 'knowledge-manifest.json').write_bytes(b'[]')
        lib._git(['add', '.'], self.origin)
        lib._git(['commit', '-m', 'invalid manifest'], self.origin)
        result = lib.resolve_library()
        self.assertEqual(result[0], first)
        self.assertIn('manifest_invalid_object', result[3])
        self.assertEqual(self.paths['marker'].read_bytes(), marker)

    def test_bad_origin_record_falls_to_minimal(self):
        self.snapshot()
        marker = json.loads(self.paths['marker'].read_text(encoding='utf-8'))
        marker['url'] = 'https://other.invalid/library.git'
        atomic_json(self.paths['marker'], marker)
        result = lib.resolve_library(cache_only=True)
        self.assertEqual(result[1], 'local_verified_template')
        self.assertIn('full_cache_origin_mismatch', result[3])

    def test_git_error_categories_and_credential_redaction(self):
        cases = [('CONNECT tunnel failed, response 502', 'git_proxy'),
                 ('SSL certificate problem', 'git_tls'),
                 ('Authentication failed https://user:secret@fixture.invalid/repo', 'git_permission'),
                 ('Could not resolve host', 'git_network')]
        for message, category in cases:
            with self.subTest(category=category), patch.object(lib.subprocess, 'run', return_value=
                    subprocess.CompletedProcess([], 1, '', message)):
                with self.assertRaises(RuntimeError) as raised:
                    lib._git(['probe'])
                self.assertTrue(str(raised.exception).startswith(category))
                self.assertNotIn('secret', str(raised.exception))

    def test_concurrent_updates_produce_one_valid_snapshot(self):
        code = ('import json; from managed_library_cache import online; '
                'from library_location import _git, validate_manifest; '
                'print(json.dumps(str(online(' + repr(self.cfg) + ', _git, validate_manifest))))')
        children = [self.child(code), self.child(code)]
        try:
            for child in children:
                stdout, stderr = child.communicate(timeout=40)
                self.assertEqual(child.returncode, 0, stderr)
                self.assertIn(self.initial, stdout)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=5)
        self.assertEqual(len(list(self.paths['snapshots'].iterdir())), 1)
        self.assertEqual(lib.resolve_library(cache_only=True)[2], self.initial)

    def test_process_crash_releases_lock(self):
        # Same process tries to acquire a lock already held by a separate process.
        code = ('from runtime_storage import exclusive_lock; import os, sys; '
                'lock = exclusive_lock(' + repr(str(self.paths['lock'])) + '); '
                'lock.__enter__(); print("locked", flush=True); sys.stdin.read()')
        child = subprocess.Popen([sys.executable, '-B', '-c',
            'import sys; sys.path.insert(0, ' + repr(str(SCRIPTS)) + '); ' + code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8')
        try:
            self.assertEqual(child.stdout.readline().strip(), 'locked')
            with self.assertRaisesRegex(RuntimeError, 'CACHE_LOCK_TIMEOUT'):
                with exclusive_lock(self.paths['lock'], timeout=.2):
                    self.fail('acquired a lock owned by another process')
        finally:
            child.kill()
            child.communicate(timeout=5)
        with exclusive_lock(self.paths['lock'], timeout=1):
            pass

    @unittest.skipIf(os.name == 'nt', 'POSIX permission enforcement; Windows uses byte-invariance check')
    def test_readonly_install_online_and_offline(self):
        all_paths = [self.install, *self.install.rglob('*')]
        try:
            for path in all_paths:
                path.chmod(0o555 if path.is_dir() else 0o444)
            self.assertFalse(os.access(self.install, os.W_OK), 'test requires unprivileged user')
            self.snapshot()
            self.assertEqual(lib.resolve_library(cache_only=True)[1], 'verified_full_cache')
        finally:
            for path in all_paths:
                path.chmod(0o755 if path.is_dir() else 0o644)


if __name__ == '__main__':
    unittest.main()

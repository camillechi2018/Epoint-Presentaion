"""The network fallback must not silently accept a dirty or corrupted checkout."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import library_location as lib


class FullCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env_patch = patch.dict(os.environ, {'EPOINT_CACHE_DIR': str(self.root / 'user-cache')})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.repo = self.root / 'checkout'
        self.repo.mkdir()
        self.cfg = {'version': 'test', 'mode': 'git', 'git_url': 'https://example.com/library.git',
                    'git_branch': 'main', 'git_checkout_path': 'checkout',
                    'git_repository_directory': '.', 'manifest': 'knowledge-manifest.json',
                    'cache_path': 'cache', 'offline_pack_path': 'minimal'}
        (self.repo / 'catalog.json').write_text('{"layouts":[]}', encoding='utf-8')
        digest = hashlib.sha256((self.repo / 'catalog.json').read_bytes()).hexdigest()
        (self.repo / 'knowledge-manifest.json').write_text(json.dumps({
            'version': 'test', 'file_count': 1, 'files': {'catalog.json': digest}}), encoding='utf-8')
        for args in (('init', '-b', 'main'), ('config', 'user.email', 'test@example.com'),
                     ('config', 'user.name', 'Test'), ('remote', 'add', 'origin', self.cfg['git_url']),
                     ('add', '.'), ('commit', '-m', 'fixture')):
            subprocess.run(['git', *args], cwd=self.repo, check=True, capture_output=True)
        self.commit = lib._git(['rev-parse', 'HEAD'], self.repo)
        self.marker = self.root / 'cache' / 'last-good.json'
        self.marker.parent.mkdir()
        self.marker.write_text(json.dumps({
            'root': str(self.repo.resolve()), 'commit': self.commit,
            'manifest_sha256': hashlib.sha256((self.repo / 'knowledge-manifest.json').read_bytes()).hexdigest()}),
            encoding='utf-8')
        self.skill_patch = patch.object(lib, 'SKILL', self.root)
        self.skill_patch.start()
        self.addCleanup(self.skill_patch.stop)

    def test_valid_cache_matches_committed_checkout(self):
        root, commit = lib.verified_full_cache(self.cfg, self.marker)
        self.assertEqual(root, self.repo.resolve())
        self.assertEqual(commit, self.commit)
        with patch.object(lib, 'config', return_value=self.cfg), patch.object(
                lib, 'git_library', side_effect=RuntimeError('git_network: 502')):
            resolved = lib.resolve_library()
        self.assertEqual(resolved[1:3], ('verified_full_cache', self.commit))

    def make_minimal_pack(self):
        pack = self.root / 'minimal'
        pack.mkdir(exist_ok=True)
        (pack / 'catalog.json').write_text('{"layouts":[]}', encoding='utf-8')
        digest = hashlib.sha256((pack / 'catalog.json').read_bytes()).hexdigest()
        (pack / 'knowledge-manifest.json').write_text(json.dumps({
            'version': 'test', 'source_commit': self.commit, 'files': {'catalog.json': digest}}), encoding='utf-8')
        return pack

    def test_resolver_leaves_legacy_marker_unchanged(self):
        self.make_minimal_pack()
        before = self.marker.read_bytes()
        with patch.object(lib, 'config', return_value=self.cfg), patch.object(
                lib, 'git_library', return_value=self.repo.resolve()):
            resolved = lib.resolve_library()
        self.assertEqual(resolved[1:3], ('remote_template', self.commit))
        self.assertEqual(json.loads(self.marker.read_text(encoding='utf-8'))['commit'], self.commit)
        self.assertEqual(self.marker.read_bytes(), before)

    def test_dirty_cache_is_rejected(self):
        (self.repo / 'catalog.json').write_text('{"layouts":[1]}', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'full_cache_dirty'):
            lib.verified_full_cache(self.cfg, self.marker)

    def test_explicit_worktree_retains_actual_commit(self):
        worktree = self.root / 'linked-worktree'
        lib._git(['worktree', 'add', '--detach', str(worktree), self.commit], self.repo)
        self.assertTrue((worktree / '.git').is_file())
        with patch.object(lib, 'config', return_value=self.cfg):
            resolved = lib.resolve_library(worktree)
        self.assertEqual(resolved[1:3], ('explicit_verified', self.commit))

    def test_corrupted_manifest_is_rejected(self):
        self.marker.write_text(self.marker.read_text(encoding='utf-8').replace(self.commit, '0' * 40), encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'full_cache_commit_mismatch'):
            lib.verified_full_cache(self.cfg, self.marker)

    def test_corrupt_full_cache_falls_to_minimal(self):
        self.make_minimal_pack()
        (self.repo / 'catalog.json').write_text('{"layouts":[1]}', encoding='utf-8')
        with patch.object(lib, 'config', return_value=self.cfg), patch.object(
                lib, 'git_library', side_effect=RuntimeError('git_network: 502')):
            resolved = lib.resolve_library()
        self.assertEqual(resolved[1], 'local_verified_template')
        self.assertIn('full_cache_dirty', resolved[3])

    def test_first_use_falls_to_minimal_pack(self):
        self.marker.unlink()
        self.make_minimal_pack()
        with patch.object(lib, 'config', return_value=self.cfg), patch.object(
                lib, 'git_library', side_effect=RuntimeError('git_network: 502')):
            resolved = lib.resolve_library()
        self.assertEqual(resolved[1], 'local_verified_template')
        self.assertIn('full_cache_missing', resolved[3])


if __name__ == '__main__':
    unittest.main()

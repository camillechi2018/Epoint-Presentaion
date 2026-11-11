"""Cross-platform release integrity and diagnostics when optional packages are absent."""
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
from distribution import canonical_bytes, normalize_files, refresh_manifest, verify_manifest, write_json
from runtime_paths import state_root


class DistributionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='epoint test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'catalog.json').write_bytes(b'{"layouts":[]}\r\n')
        (self.root / 'asset.pptx').write_bytes(b'PK\x03\x04\r\n\xff\x00')
        write_json(self.root / 'knowledge-manifest.json', {'version': 'test', 'files': {}})
        self.paths = ['catalog.json', 'asset.pptx']
        normalize_files(self.root, self.paths)
        refresh_manifest(self.root, self.paths)

    def test_canonical_policy_preserves_binary_and_ps1_bom(self):
        binary = b'PK\xff\r\n'
        self.assertEqual(canonical_bytes('x.pptx', binary), binary)
        self.assertEqual(canonical_bytes('x.ps1', b'abc\r\n'), b'\xef\xbb\xbfabc\n')
        self.assertEqual(canonical_bytes('x.json', b'\xef\xbb\xbf{}\r\n'), b'{}\n')
        with self.assertRaises(UnicodeDecodeError):
            canonical_bytes('x.json', b'\xff')

    def test_build_and_validation_are_idempotent_and_read_only(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(normalize_files(self.root, self.paths), [])
        verify_manifest(self.root)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_changed_newline_and_binary_are_rejected(self):
        for name, contents in [('catalog.json', b'{"layouts":[]}\r\n'), ('asset.pptx', b'changed')]:
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(contents)
            with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
                verify_manifest(self.root)
            self.assertEqual(path.read_bytes(), contents)
            path.write_bytes(original)

    def test_unsafe_or_empty_manifests_are_rejected(self):
        for files in [{}, {'catalog.json': 'x', '../escape': 'x'}]:
            write_json(self.root / 'knowledge-manifest.json', {'files': files})
            with self.assertRaises(ValueError):
                verify_manifest(self.root)

    def test_doctor_starts_without_site_packages_from_other_cwd(self):
        for script, extra in [('doctor.py', []), ('run_presentation.py', ['--doctor'])]:
            run = subprocess.run([sys.executable, '-S', str(SCRIPTS / script), *extra,
                                  '--library', str(self.root), '--goal', 'fill'],
                                 cwd=self.root, capture_output=True, timeout=60,
                                 env={**os.environ, 'PYTHONIOENCODING': 'ascii'})
            data = json.loads(run.stdout)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertIn('DEPENDENCY_IMPORT_FAILED', data['blockers'])
            self.assertEqual(data['library']['status'], 'available')
            self.assertEqual(data['rendering']['status'], 'untested')
            self.assertFalse((self.root / 'venv').exists())

    def test_state_override_does_not_write_to_installation(self):
        with patch.dict(os.environ, {'EPOINT_STATE_DIR': str(self.root / '中文 state')}):
            target = state_root()
            self.assertEqual(target, (self.root / '中文 state').resolve())
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()

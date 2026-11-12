"""Cross-platform release integrity and diagnostics when optional packages are absent."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from distribution import canonical_bytes, normalize_files, refresh_manifest, verify_manifest, write_json
from runtime_paths import state_root
import install_runtime


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

    def test_installer_reuses_valid_active_runtime_before_bootstrap_python(self):
        state = self.root / 'state'
        python = state / 'venvs' / 'Darwin-arm64-3.14-fixture' / 'bin' / 'python'
        python.parent.mkdir(parents=True)
        python.write_bytes(b'fixture')
        requirements = (SCRIPTS.parent / 'requirements-core.txt').read_bytes()
        versions = {name: '1.0' for name in install_runtime.PACKAGES}
        record = {'python': str(python), 'requirements_sha256': hashlib.sha256(requirements).hexdigest(),
                  'versions': versions, 'previous_python': None}
        marker = state / 'runtime.json'
        marker.write_text(json.dumps(record), encoding='utf-8')
        before = marker.read_bytes()

        def fake_capture(args, **_kwargs):
            self.assertNotIn('venv', args, 'A valid active runtime must not create a second environment')
            stdout = json.dumps(versions) if '-c' in args else '{"blockers": []}'
            return {'returncode': 0, 'stdout': stdout, 'stderr': '', 'error': None}

        output = io.StringIO()
        with patch.object(install_runtime, 'state_root', return_value=state), \
             patch.object(install_runtime, 'capture', side_effect=fake_capture), \
             patch.object(sys, 'argv', ['install_runtime.py']), redirect_stdout(output):
            self.assertEqual(install_runtime.main(), 0)
        self.assertTrue(json.loads(output.getvalue())['reused_active_runtime'])
        self.assertEqual(marker.read_bytes(), before)

    def test_venv_failure_keeps_specific_redacted_diagnostic(self):
        state = self.root / 'fresh state'
        failure = {'returncode': 1, 'stdout': '',
                   'stderr': 'Permission denied deleting pip/__pycache__/temp.pyc; https://user:secret@example.com',
                   'error': None}
        output = io.StringIO()
        with patch.object(install_runtime, 'state_root', return_value=state), \
             patch.object(install_runtime, 'capture', return_value=failure) as run, \
             patch.object(sys, 'argv', ['install_runtime.py']), redirect_stdout(output):
            self.assertEqual(install_runtime.main(), 2)
        result = json.loads(output.getvalue())
        self.assertEqual(result['error_code'], 'VENV_CREATE_FAILED')
        self.assertIn('Permission denied deleting', result['detail'])
        self.assertNotIn('secret', result['detail'])
        self.assertNotIn('install the system venv', result['error'])
        self.assertEqual(run.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertIn('-B', run.call_args.args[0])

    @unittest.skipIf(os.name == 'nt', 'POSIX virtualenv interpreter symlink')
    def test_installer_retains_virtualenv_symlink_path(self):
        target = self.root / 'venvs' / 'test' / 'bin' / 'python'
        target.parent.mkdir(parents=True)
        target.symlink_to(sys.executable)
        success = {'returncode': 0, 'stdout': '{}', 'stderr': '', 'error': None}
        def fake_capture(args, **kwargs):
            if 'doctor.py' in str(args[1]):
                return {**success, 'stdout': '{"blockers":[]}'}
            return success
        # Freeze the package hash and platform path to point at the symlink fixture.
        with patch.object(install_runtime, 'state_root', return_value=self.root), \
             patch.object(install_runtime.hashlib, 'sha256') as digest, \
             patch.object(install_runtime.platform, 'system', return_value='X'), \
             patch.object(install_runtime.platform, 'machine', return_value='Y'), \
             patch.object(install_runtime, 'capture', side_effect=fake_capture), \
             patch.object(sys, 'argv', ['install_runtime.py']):
            digest.return_value.hexdigest.return_value = 'fixture'
            expected = self.root / 'venvs' / f'X-Y-{sys.version_info.major}.{sys.version_info.minor}-fixture' / 'bin' / 'python'
            expected.parent.mkdir(parents=True)
            expected.symlink_to(sys.executable)
            self.assertEqual(install_runtime.main(), 0)
            record = json.loads((self.root / 'runtime.json').read_text(encoding='utf-8'))
            self.assertEqual(record['python'], str(expected.absolute()))
            self.assertNotEqual(record['python'], str(expected.resolve()))


if __name__ == '__main__':
    unittest.main()

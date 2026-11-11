"""Install an isolated, versioned environment; keep the previous active interpreter on failure."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from runtime_paths import SKILL_ROOT, state_root
from runtime_process import capture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--wheelhouse', type=Path, help='Install offline only from this wheel directory')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        print(json.dumps({'status': 'blocked', 'error_code': 'PYTHON_VERSION_UNSUPPORTED'}))
        return 2
    root = state_root(args.state_dir)
    requirements = SKILL_ROOT / 'requirements-core.txt'
    key = hashlib.sha256(requirements.read_bytes()).hexdigest()[:12]
    target = root / 'venvs' / f'{platform.system()}-{platform.machine()}-{sys.version_info.major}.{sys.version_info.minor}-{key}'
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    stage = 'create_environment'
    lock = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents two installers from mutating an environment together.
        lock = (root / 'install.lock').open('x', encoding='utf-8')
        lock.write(str(os.getpid()))
        lock.flush()
        # A failed ensurepip can leave python behind; retry must repair that partial venv.
        if not python.is_file() or capture([python, '-m', 'pip', '--version'])['returncode'] != 0:
            create = capture([sys.executable, '-m', 'venv', str(target)], timeout=90)
            if create['returncode'] != 0:
                raise RuntimeError('VENV_CREATE_FAILED: install the system venv/ensurepip component')
        stage = 'install_dependencies'
        command = [str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--no-input', '--retries', '1', '--timeout', '20', '-r', str(requirements)]
        if args.wheelhouse:
            command += ['--no-index', '--find-links', str(args.wheelhouse.resolve())]
        result = capture(command, timeout=240)
        if result['returncode'] != 0:
            # Avoid printing proxy credentials or index URLs from pip output.
            raise RuntimeError(result['error'] or 'DEPENDENCY_INSTALL_FAILED: check package source/network or use --wheelhouse')
        stage = 'verify_environment'
        result = capture([python, SKILL_ROOT / 'scripts' / 'doctor.py', '--goal', 'fill'], timeout=45)
        if result['returncode'] != 0:
            raise RuntimeError('INSTALLED_RUNTIME_VALIDATION_FAILED: run doctor.py for details')
        doctor = json.loads(result['stdout'])
        if doctor['blockers']:
            raise RuntimeError('INSTALLED_RUNTIME_VALIDATION_FAILED')
        versions = capture([python, '-c', 'import importlib.metadata,json; print(json.dumps({p:importlib.metadata.version(p) for p in ["python-pptx","Pillow","lxml","XlsxWriter","typing_extensions"]}))'])
        if versions['returncode'] != 0:
            raise RuntimeError('DEPENDENCY_VERSION_REPORT_FAILED')
        # Do not resolve a POSIX venv symlink to /usr/bin/python: it loses venv discovery.
        record = {'schema_version': '1.0', 'python': str(python.absolute()),
                  'requirements_sha256': hashlib.sha256(requirements.read_bytes()).hexdigest(),
                  'versions': json.loads(versions['stdout']), 'previous_python': None}
        active = root / 'runtime.json'
        if active.is_file():
            old = json.loads(active.read_text(encoding='utf-8'))
            record['previous_python'] = (old.get('previous_python') if old.get('python') == record['python']
                                         else old.get('python'))
        with tempfile.NamedTemporaryFile(dir=root, suffix='.json', delete=False) as handle:
            pending = Path(handle.name)
            handle.write((json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode())
        try:
            os.replace(pending, active)
        finally:
            if pending.exists():
                pending.unlink()
        print(json.dumps({'status': 'passed', 'python': record['python'], 'runtime_record': str(active),
                          'scope': 'dependencies_and_library_checks_only', 'versions': record['versions']}))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'stage': stage, 'error': str(exc)}, ensure_ascii=True))
        return 2
    finally:
        if lock is not None:
            lock.close()
            (root / 'install.lock').unlink()


if __name__ == '__main__':
    raise SystemExit(main())

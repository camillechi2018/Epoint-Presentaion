"""Install an isolated, versioned environment; keep the previous active interpreter on failure."""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from runtime_paths import SKILL_ROOT, state_root
from runtime_process import capture
from runtime_storage import atomic_json, exclusive_lock

PACKAGES = ('python-pptx', 'Pillow', 'lxml', 'openpyxl', 'xlrd', 'python-docx',
            'et-xmlfile', 'XlsxWriter', 'typing_extensions')


class InstallFailure(RuntimeError):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code = code
        self.detail = detail


def safe_process_detail(result):
    """Retain the useful subprocess failure without exposing URL credentials."""
    detail = (result.get('stderr') or result.get('stdout') or result.get('error') or
              f"process exited with code {result.get('returncode')}").strip()
    detail = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', detail)
    detail = re.sub(r'(?i)\b(token|password|authorization)\s*[:=]\s*[^\s]+',
                    r'\1=[REDACTED]', detail)
    return detail[-1600:]


def installed_versions(python):
    code = ('import importlib.metadata,json; print(json.dumps({p:importlib.metadata.version(p) '
            'for p in ' + repr(PACKAGES) + '}))')
    result = capture([python, '-c', code], timeout=25)
    if result['returncode'] != 0:
        raise InstallFailure('DEPENDENCY_VERSION_REPORT_FAILED', safe_process_detail(result))
    return json.loads(result['stdout'])


def active_runtime(root, requirements_sha256):
    """Reuse a validated active venv before considering the bootstrap Python."""
    marker = root / 'runtime.json'
    try:
        record = json.loads(marker.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('requirements_sha256') != requirements_sha256:
            return None
        python = Path(record['python'])
        # The record is user-writable; never execute a path outside our state venvs.
        if not python.is_absolute() or not Path(os.path.abspath(python)).is_relative_to(root / 'venvs'):
            return None
        if not python.is_file() or installed_versions(python) != record.get('versions'):
            return None
        for goal in ('fill', 'read'):
            result = capture([python, SKILL_ROOT / 'scripts' / 'doctor.py', '--goal', goal], timeout=45)
            if result['returncode'] != 0 or json.loads(result['stdout']).get('blockers'):
                return None
        return record
    except (OSError, ValueError, KeyError, TypeError, InstallFailure, json.JSONDecodeError):
        return None


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
    requirements_sha256 = hashlib.sha256(requirements.read_bytes()).hexdigest()
    key = requirements_sha256[:12]
    target = root / 'venvs' / f'{platform.system()}-{platform.machine()}-{sys.version_info.major}.{sys.version_info.minor}-{key}'
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    stage = 'create_environment'
    lock = None
    try:
        root.mkdir(parents=True, exist_ok=True)
        # OS lock is released on a crashed installer; the persistent file is not a stale owner flag.
        guard = exclusive_lock(root / 'install.lock', timeout=10)
        guard.__enter__()
        lock = guard
        existing = active_runtime(root, requirements_sha256)
        if existing:
            print(json.dumps({'status': 'passed', 'python': existing['python'],
                              'runtime_record': str(root / 'runtime.json'),
                              'reused_active_runtime': True,
                              'scope': 'dependencies_and_library_checks_only',
                              'versions': existing['versions']}))
            return 0
        # A failed ensurepip can leave python behind; retry must repair that partial venv.
        if not python.is_file() or capture([python, '-m', 'pip', '--version'])['returncode'] != 0:
            create = capture([sys.executable, '-B', '-m', 'venv', str(target)], timeout=90,
                             env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if create['returncode'] != 0:
                raise InstallFailure('VENV_CREATE_FAILED', safe_process_detail(create))
        stage = 'install_dependencies'
        command = [str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--no-input', '--retries', '1', '--timeout', '20', '-r', str(requirements)]
        if args.wheelhouse:
            command += ['--no-index', '--find-links', str(args.wheelhouse.resolve())]
        result = capture(command, timeout=240)
        if result['returncode'] != 0:
            # Avoid printing proxy credentials or index URLs from pip output.
            if args.wheelhouse and ('No matching distribution found' in result['stderr'] or
                                    'Could not find a version' in result['stderr']):
                raise RuntimeError('OFFLINE_WHEEL_INCOMPATIBLE: provide wheels matching this Python version and OS/architecture')
            raise RuntimeError(result['error'] or 'DEPENDENCY_INSTALL_FAILED: check package source/network or use --wheelhouse')
        stage = 'verify_environment'
        result = capture([python, SKILL_ROOT / 'scripts' / 'doctor.py', '--goal', 'fill'], timeout=45)
        if result['returncode'] != 0:
            raise RuntimeError('INSTALLED_RUNTIME_VALIDATION_FAILED: run doctor.py for details')
        doctor = json.loads(result['stdout'])
        if doctor['blockers']:
            raise RuntimeError('INSTALLED_RUNTIME_VALIDATION_FAILED')
        material_check = capture([python, SKILL_ROOT / 'scripts' / 'doctor.py', '--goal', 'read'], timeout=45)
        if material_check['returncode'] != 0 or json.loads(material_check['stdout'])['blockers']:
            raise RuntimeError('MATERIAL_RUNTIME_VALIDATION_FAILED: run doctor.py --goal read for details')
        versions = installed_versions(python)
        # Do not resolve a POSIX venv symlink to /usr/bin/python: it loses venv discovery.
        record = {'schema_version': '1.0', 'python': str(python.absolute()),
                  'requirements_sha256': requirements_sha256,
                  'versions': versions, 'previous_python': None}
        active = root / 'runtime.json'
        if active.is_file():
            old = json.loads(active.read_text(encoding='utf-8'))
            record['previous_python'] = (old.get('previous_python') if old.get('python') == record['python']
                                         else old.get('python'))
        atomic_json(active, record)
        print(json.dumps({'status': 'passed', 'python': record['python'], 'runtime_record': str(active),
                          'scope': 'dependencies_and_library_checks_only', 'versions': record['versions']}))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        result = {'status': 'blocked', 'stage': stage, 'error': str(exc),
                  'error_code': exc.code if isinstance(exc, InstallFailure) else str(exc).split(':', 1)[0]}
        if isinstance(exc, InstallFailure) and exc.detail:
            result['detail'] = exc.detail
        if stage == 'create_environment':
            result['candidate_python'] = sys.executable
            result['partial_environment'] = str(target) if target.exists() else None
            result['active_runtime_preserved'] = (root / 'runtime.json').is_file()
            result['hint'] = ('Check the subprocess detail and filesystem policy; the failure does not '
                              'by itself prove venv or ensurepip is missing. Use a supported Python '
                              'directly with scripts/install_runtime.py if the launcher selected the wrong one.')
        print(json.dumps(result, ensure_ascii=True))
        return 2
    finally:
        if lock is not None:
            lock.__exit__(None, None, None)


if __name__ == '__main__':
    raise SystemExit(main())

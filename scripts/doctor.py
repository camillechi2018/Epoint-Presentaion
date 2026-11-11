"""Dependency-free diagnostics. Does not install packages or launch Office applications."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

from distribution import verify_manifest, write_json
from runtime_paths import SKILL_ROOT, locations
from runtime_process import capture

IMPORTS = {'pptx': 'python-pptx', 'PIL': 'Pillow', 'lxml': 'lxml'}


def probe_import(module):
    # Preserve -S for clean-runtime tests; probe crashes/timeouts cannot kill the doctor.
    command = [sys.executable] + (['-S'] if sys.flags.no_site else [])
    command += ['-c', 'import importlib; importlib.import_module(' + repr(module) + ')']
    result = capture(command)
    ok = result['returncode'] == 0
    return {'status': 'available' if ok else 'unavailable',
            'error_code': None if ok else result['error'] or 'DEPENDENCY_IMPORT_FAILED',
            'package': IMPORTS[module], 'returncode': result['returncode']}


def probe_command(name):
    path = shutil.which(name)
    if not path:
        return {'status': 'unavailable', 'path': None, 'error_code': 'COMMAND_NOT_FOUND'}
    result = capture([path, '--version'])
    ok = result['returncode'] == 0
    return {'status': 'available' if ok else 'unavailable', 'path': path,
            'version': result['stdout'].splitlines()[0][:160] if ok and result['stdout'] else None,
            'error_code': None if ok else result['error'] or 'COMMAND_PROBE_FAILED'}


def report(*, library=None, state_dir=None, goal='inspect'):
    paths = locations(state_dir)
    root = Path(library).resolve() if library else SKILL_ROOT / 'assets' / 'minimal-template-pack'
    dependencies = {name: probe_import(name) for name in IMPORTS}
    try:
        manifest = verify_manifest(root)
        library_check = {'status': 'available', 'path': str(root),
                         'files': len(manifest['files']), 'source_commit': manifest.get('source_commit'),
                         'error_code': None}
    except (OSError, ValueError) as exc:
        library_check = {'status': 'unavailable', 'path': str(root),
                         'error_code': 'LIBRARY_VALIDATION_FAILED', 'detail': str(exc)}
    git = probe_command('git')
    assembly = {'status': 'unavailable', 'backend': None,
                'error_code': 'PPTX_BACKEND_UNAVAILABLE'}
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, 'PowerPoint.Application'):
                pass
            shell = shutil.which('pwsh') or shutil.which('powershell')
            if shell:
                assembly = {'status': 'untested', 'backend': 'windows_powerpoint_com',
                            'shell': shell, 'error_code': 'BACKEND_SMOKE_TEST_REQUIRED'}
        except OSError:
            pass
    blockers = []
    if sys.version_info < (3, 10):
        blockers.append('PYTHON_VERSION_UNSUPPORTED')
    if library_check['status'] != 'available':
        blockers.append(library_check['error_code'])
    if goal in {'fill', 'assemble'} and any(x['status'] != 'available' for x in dependencies.values()):
        blockers.append('DEPENDENCY_IMPORT_FAILED')
    if goal == 'assemble' and assembly['status'] != 'available':
        blockers.append(assembly['error_code'])
    # Basic detection never claims fonts, Office opening or rendering have been tested.
    return {'schema_version': '1.0', 'status': 'blocked' if blockers else 'passed',
            'scope': 'environment_inspection_only', 'goal': goal, 'blockers': blockers,
            'runtime': {'os': platform.system(), 'architecture': platform.machine(),
                        'python': platform.python_version(), 'executable': sys.executable,
                        'site_packages_enabled': not bool(sys.flags.no_site)},
            'paths': paths, 'dependencies': dependencies, 'git': git, 'library': library_check,
            'assembly': assembly, 'rendering': {'status': 'untested'}, 'fonts': {'status': 'untested'},
            'guidance': ['Use the dedicated environment installer for missing Python dependencies.',
                         'An available package or registered application is not a rendered-deck acceptance.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--state-dir', type=Path)
    parser.add_argument('--goal', choices=['inspect', 'fill', 'assemble'], default='inspect')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(argv)
    result = report(library=args.library, state_dir=args.state_dir, goal=args.goal)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.out, result)
    # ASCII-safe JSON works even when a host redirects stdout using a legacy encoding.
    print(json.dumps(result, ensure_ascii=True))
    return 2 if result['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

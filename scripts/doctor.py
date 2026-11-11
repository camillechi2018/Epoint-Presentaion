"""Dependency-free diagnostics. Does not install packages or launch Office applications."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

from distribution import verify_manifest, write_json
from runtime_paths import SKILL_ROOT, locations
from runtime_process import capture

IMPORTS = {'pptx': 'python-pptx', 'PIL': 'Pillow', 'lxml': 'lxml',
           'openpyxl': 'openpyxl', 'xlrd': 'xlrd', 'docx': 'python-docx'}
PPTX_IMPORTS = ('pptx', 'PIL', 'lxml')
MATERIAL_IMPORTS = ('openpyxl', 'xlrd', 'docx')


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


def deep_probe(paths):
    """Explicit local writes and editable PPTX roundtrip; no Office UI is launched."""
    outcome = {}
    for name in ('state', 'cache'):
        try:
            root = Path(paths[name])
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='epoint-doctor-', dir=root) as folder:
                marker = Path(folder) / 'probe.txt'
                marker.write_bytes(b'epoint')
                if marker.read_bytes() != b'epoint':
                    raise OSError('write/read mismatch')
            outcome[name + '_write'] = {'status': 'available'}
        except OSError as exc:
            outcome[name + '_write'] = {'status': 'unavailable', 'error_code': 'DIRECTORY_NOT_WRITABLE',
                                         'detail': type(exc).__name__}
    code = ('import tempfile; from pathlib import Path; from pptx import Presentation; '
            'p=Presentation(); s=p.slides.add_slide(p.slide_layouts[6]); '
            't=s.shapes.add_textbox(0,0,1000000,300000); t.text="Epoint 测试"; '
            'f=Path(tempfile.mkdtemp())/"probe.pptx"; p.save(f); '
            'q=Presentation(f); assert len(q.slides)==1; '
            'assert q.slides[0].shapes[0].text=="Epoint 测试"; f.unlink(); f.parent.rmdir()')
    result = capture([sys.executable, '-c', code], timeout=30)
    outcome['pptx_roundtrip'] = {'status': 'available' if result['returncode'] == 0 else 'unavailable',
                                 'error_code': None if result['returncode'] == 0 else
                                 result['error'] or 'PPTX_ROUNDTRIP_FAILED'}
    return outcome


def report(*, library=None, state_dir=None, goal='inspect', deep=False):
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
    required = MATERIAL_IMPORTS if goal == 'read' else PPTX_IMPORTS if goal in {'fill', 'assemble'} else ()
    if any(dependencies[name]['status'] != 'available' for name in required):
        blockers.append('DEPENDENCY_IMPORT_FAILED')
    if goal == 'assemble' and assembly['status'] != 'available':
        blockers.append(assembly['error_code'])
    deep_checks = deep_probe(paths) if deep else None
    if deep_checks:
        if goal in {'fill', 'assemble'} and deep_checks['pptx_roundtrip']['status'] != 'available':
            blockers.append(deep_checks['pptx_roundtrip']['error_code'])
        for name in ('state_write', 'cache_write'):
            if deep_checks[name]['status'] != 'available':
                blockers.append(deep_checks[name]['error_code'])
    # Basic detection never claims fonts, Office opening or rendering have been tested.
    return {'schema_version': '1.0', 'status': 'blocked' if blockers else 'passed',
            'scope': 'local_pptx_roundtrip_only' if deep else 'environment_inspection_only',
            'goal': goal, 'blockers': blockers, 'deep_checks': deep_checks,
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
    parser.add_argument('--goal', choices=['inspect', 'read', 'fill', 'assemble'], default='inspect')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--deep', action='store_true')
    args = parser.parse_args(argv)
    result = report(library=args.library, state_dir=args.state_dir, goal=args.goal, deep=args.deep)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.out, result)
    # ASCII-safe JSON works even when a host redirects stdout using a legacy encoding.
    print(json.dumps(result, ensure_ascii=True))
    return 2 if result['blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

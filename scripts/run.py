"""Run the workflow using the installer-selected interpreter, independent of cwd."""
import json
import subprocess
import sys
from pathlib import Path
from runtime_paths import SKILL_ROOT, state_root


def main():
    marker = state_root() / 'runtime.json'
    try:
        record = json.loads(marker.read_text(encoding='utf-8'))
        python = Path(record['python'])
        if not python.is_file():
            raise FileNotFoundError(str(python))
    except (OSError, ValueError, KeyError):
        print(json.dumps({'status': 'blocked', 'error_code': 'RUNTIME_NOT_INSTALLED',
                          'hint': 'Run install_runtime.py or install.ps1/install.sh first.'}))
        return 2
    args = sys.argv[1:]
    routes = {'--read-material': 'read_material.py', '--structure-content': 'structure_content.py'}
    entry = routes.get(args[0] if args else None, 'run_presentation.py')
    if entry != 'run_presentation.py':
        args = args[1:]
    return subprocess.call([str(python), str(SKILL_ROOT / 'scripts' / entry), *args])


if __name__ == '__main__':
    raise SystemExit(main())

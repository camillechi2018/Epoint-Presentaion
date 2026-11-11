"""Task-wide editable-text fonts and host resource checks.

The default preserves the existing Windows deck baseline. A non-Windows task
must explicitly select its native profile; it never silently substitutes a font.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


PROFILES = {
    'windows': {'east_asian': 'Microsoft YaHei', 'latin': 'Arial'},
    'macos': {'east_asian': 'PingFang SC', 'latin': 'Helvetica Neue'},
    'linux': {'east_asian': 'Noto Sans CJK SC', 'latin': 'Noto Sans'},
}


def resolve(name: str | None = None) -> dict:
    selected = name or os.environ.get('EPOINT_FONT_PROFILE') or 'windows'
    if selected not in PROFILES:
        raise ValueError('FONT_PROFILE_UNKNOWN: ' + selected)
    return {'id': selected, **PROFILES[selected]}


def _font_families() -> set[str]:
    if not shutil.which('fc-list'):
        return set()
    proc = subprocess.run(['fc-list', '-f', '%{family}\n'], capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=20)
    if proc.returncode:
        return set()
    return {part.strip() for line in proc.stdout.splitlines()
            for part in line.split(',') if part.strip()}


def probe(name: str | None = None) -> dict:
    profile = resolve(name)
    host = platform.system()
    available = {}
    if host == 'Windows':
        fonts = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        known = {'Microsoft YaHei': ('msyh.ttc', 'msyhbd.ttc'),
                 'Arial': ('arial.ttf', 'arialbd.ttf')}
        available = {font: any((fonts / file).is_file() for file in known.get(font, ()))
                     for font in (profile['east_asian'], profile['latin'])}
    elif host == 'Darwin':
        paths = {'PingFang SC': ('/System/Library/Fonts/PingFang.ttc',),
                 'Helvetica Neue': ('/System/Library/Fonts/HelveticaNeue.ttc',
                                    '/System/Library/Fonts/HelveticaNeue.dfont')}
        families = _font_families()
        available = {font: font in families or any(Path(file).is_file() for file in paths.get(font, ()))
                     for font in (profile['east_asian'], profile['latin'])}
    else:
        families = _font_families()
        available = {font: font in families for font in (profile['east_asian'], profile['latin'])}
    missing = [font for font, found in available.items() if not found]
    return {'profile': profile, 'host': host, 'font_available': available,
            'status': 'available' if not missing else 'unavailable',
            'error_code': None if not missing else 'FONT_PROFILE_RESOURCE_MISSING',
            'missing': missing}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=tuple(PROFILES))
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = probe(args.profile)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result['status'] == 'available' else 2


if __name__ == '__main__':
    raise SystemExit(main())

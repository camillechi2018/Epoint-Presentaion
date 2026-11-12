"""Task-wide editable-text fonts and host resource checks.

The default preserves the existing Windows deck baseline. A non-Windows task
must explicitly select its native profile; it never silently substitutes a font.
"""
from __future__ import annotations

import argparse
import ctypes
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


def _coretext_font_families() -> set[str] | None:
    """Ask macOS for registered families, including dynamically installed fonts.

    None means the API could not be queried. An empty set means it answered but
    exposed no families, which must not be treated as a successful font check.
    """
    try:
        coretext = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
        foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        coretext.CTFontManagerCopyAvailableFontFamilyNames.restype = ctypes.c_void_p
        foundation.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        foundation.CFArrayGetCount.restype = ctypes.c_long
        foundation.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        foundation.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        foundation.CFStringGetLength.argtypes = [ctypes.c_void_p]
        foundation.CFStringGetLength.restype = ctypes.c_long
        foundation.CFStringGetMaximumSizeForEncoding.argtypes = [ctypes.c_long, ctypes.c_uint32]
        foundation.CFStringGetMaximumSizeForEncoding.restype = ctypes.c_long
        foundation.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                  ctypes.c_long, ctypes.c_uint32]
        foundation.CFStringGetCString.restype = ctypes.c_bool
        foundation.CFRelease.argtypes = [ctypes.c_void_p]
        array = coretext.CTFontManagerCopyAvailableFontFamilyNames()
        if not array:
            return None
        try:
            names = set()
            utf8 = 0x08000100  # kCFStringEncodingUTF8
            for index in range(foundation.CFArrayGetCount(array)):
                value = foundation.CFArrayGetValueAtIndex(array, index)
                length = foundation.CFStringGetLength(value)
                capacity = foundation.CFStringGetMaximumSizeForEncoding(length, utf8) + 1
                buffer = ctypes.create_string_buffer(capacity)
                if foundation.CFStringGetCString(value, buffer, capacity, utf8):
                    names.add(buffer.value.decode('utf-8'))
            return names
        finally:
            foundation.CFRelease(array)
    except (AttributeError, OSError, ValueError, TypeError, UnicodeError, ctypes.ArgumentError):
        return None


def _mac_font_file_exists(font: str) -> bool:
    filenames = {'PingFang SC': ('PingFang.ttc',),
                 'Helvetica Neue': ('HelveticaNeue.ttc', 'HelveticaNeue.dfont')}
    names = filenames.get(font, ())
    roots = (Path('/System/Library/Fonts'), Path('/Library/Fonts'),
             Path.home() / 'Library/Fonts')
    if any((root / name).is_file() for root in roots for name in names):
        return True
    if font == 'PingFang SC':
        assets = Path('/System/Library/AssetsV2')
        try:
            return any(path.is_file() for path in assets.glob(
                'com_apple_MobileAsset_Font*/*.asset/AssetData/PingFang.ttc'))
        except OSError:
            return False
    return False


def probe(name: str | None = None) -> dict:
    profile = resolve(name)
    host = platform.system()
    available = {}
    detection = None
    if host == 'Windows':
        detection = 'windows_font_files'
        fonts = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
        known = {'Microsoft YaHei': ('msyh.ttc', 'msyhbd.ttc'),
                 'Arial': ('arial.ttf', 'arialbd.ttf')}
        available = {font: any((fonts / file).is_file() for file in known.get(font, ()))
                     for font in (profile['east_asian'], profile['latin'])}
    elif host == 'Darwin':
        families = _coretext_font_families()
        if families is None:
            detection = 'fontconfig_or_font_file_fallback'
            families = _font_families()
            registered = {name.casefold() for name in families}
            available = {font: font.casefold() in registered
                         or _mac_font_file_exists(font)
                         for font in (profile['east_asian'], profile['latin'])}
        else:
            detection = 'macos_coretext'
            registered = {font.casefold() for font in families}
            available = {font: font.casefold() in registered
                         for font in (profile['east_asian'], profile['latin'])}
    else:
        detection = 'fontconfig'
        families = _font_families()
        available = {font: font in families for font in (profile['east_asian'], profile['latin'])}
    missing = [font for font, found in available.items() if not found]
    return {'profile': profile, 'host': host, 'font_available': available,
            'detection': detection,
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

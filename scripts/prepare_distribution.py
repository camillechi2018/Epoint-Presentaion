"""Explicitly normalize tracked release files; rebuild only the named manifest.

No untracked files are added to the manifest. Stage intended new assets first.
Verification is read-only by default; --write is a release-maintainer operation.
"""
import argparse
import json
import subprocess
from pathlib import Path
from distribution import normalize_files, refresh_manifest, verify_manifest


def tracked_files(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                            check=True, capture_output=True)
    return [p for p in result.stdout.decode('utf-8').split('\0') if p]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest-root', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    target = (args.manifest_root or root).resolve()
    if not target.is_relative_to(root):
        parser.error('--manifest-root must be inside --root')
    changed = []
    if args.write:
        changed = normalize_files(root, tracked_files(root))
        refresh_manifest(target, tracked_files(target))
    manifest = verify_manifest(target)
    print(json.dumps({'status': 'passed', 'files': manifest['file_count'],
                      'normalized_files': len(changed)}, ensure_ascii=True))


if __name__ == '__main__':
    main()

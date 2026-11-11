"""Normalize tracked release bytes before hashing; verification never rewrites files."""
import argparse
import json
import subprocess
from pathlib import Path
from distribution import normalize_files, refresh_manifest

def prepare(root):
    root = Path(root).resolve()
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    tracked = [p for p in tracked if p and (root / p).is_file()]
    changed = normalize_files(root, tracked)
    pack = root / 'assets/minimal-template-pack'
    if pack.is_dir():
        manifest = json.loads((pack / 'knowledge-manifest.json').read_text(encoding='utf-8'))
        refresh_manifest(pack, manifest['files'])
    elif (root / 'knowledge-manifest.json').is_file():
        refresh_manifest(root, tracked)
    return {'normalized': len(changed)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    print(json.dumps(prepare(parser.parse_args().root)))

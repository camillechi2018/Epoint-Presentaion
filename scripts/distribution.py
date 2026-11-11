"""Build-time byte policy and read-only, raw-byte manifest verification (stdlib only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

TEXT_SUFFIXES = {'.json', '.jsonl', '.md', '.py', '.ps1', '.sh', '.js', '.cjs', '.mjs', '.html',
                 '.css', '.svg', '.yml', '.yaml', '.txt', '.cmd', '.bat'}
TEXT_NAMES = {'.gitattributes', '.gitignore', 'LICENSE'}


def canonical_bytes(path, data):
    path = Path(path)
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
        return data  # PPTX, PNG and every unrecognized format are byte-preserved.
    text = data.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    if path.suffix.lower() in {'.cmd', '.bat'}:
        text = text.replace('\n', '\r\n')
    encoding = 'utf-8-sig' if path.suffix.lower() == '.ps1' else 'utf-8'
    return text.encode(encoding)


def normalize_files(root, relative_paths):
    """Explicit build operation; never called by verification or cache loading."""
    changed = []
    for relative in relative_paths:
        path = safe_file(root, relative)
        original = path.read_bytes()
        canonical = canonical_bytes(path, original)
        if canonical != original:
            path.write_bytes(canonical)
            changed.append(relative)
    return changed


def write_json(path, data):
    Path(path).write_bytes((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def safe_file(root, relative):
    root = Path(root).resolve()
    rel = PurePosixPath(relative)
    if not relative or '\\' in relative or ':' in relative or rel.is_absolute() or '..' in rel.parts:
        raise ValueError('manifest_invalid_path: ' + relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('manifest_missing_or_unsafe_file: ' + relative)
    return path


def verify_manifest(root, manifest_name='knowledge-manifest.json', version=None):
    root = Path(root).resolve()
    manifest = json.loads(safe_file(root, manifest_name).read_text(encoding='utf-8'))
    if not isinstance(manifest, dict):
        raise ValueError('manifest_invalid_object')
    if version is not None and manifest.get('version') != version:
        raise ValueError('manifest_version_mismatch')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files or 'catalog.json' not in files:
        raise ValueError('manifest_empty_or_missing_catalog')
    if manifest.get('file_count', len(files)) != len(files):
        raise ValueError('manifest_file_count_mismatch')
    for relative, expected in files.items():
        actual = hashlib.sha256(safe_file(root, relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('manifest_hash_mismatch: ' + relative)
    return manifest


def refresh_manifest(root, paths):
    root = Path(root)
    manifest_path = root / 'knowledge-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    files = {rel: hashlib.sha256(safe_file(root, rel).read_bytes()).hexdigest()
             for rel in sorted(set(paths)) if rel not in {'knowledge-manifest.json', 'audit-report.json'}}
    manifest.update(files=files, file_count=len(files))
    write_json(manifest_path, manifest)
    verify_manifest(root)
    return manifest

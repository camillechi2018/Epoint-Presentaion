"""Immutable, commit-addressed library snapshots outside the installation directory."""
import json
import re
import tempfile
from hashlib import sha256
from pathlib import Path

from runtime_paths import library_paths
from runtime_storage import atomic_json, exclusive_lock

COMMIT = re.compile(r'[0-9a-f]{40}')


def source_root(checkout, cfg):
    root = (checkout / cfg.get('git_repository_directory', '.')).resolve()
    if not root.is_relative_to(checkout.resolve()):
        raise ValueError('LIBRARY_SUBDIRECTORY_INVALID')
    return root


def verify_record(cfg, record, git, validate):
    if not isinstance(record, dict):
        raise ValueError('full_cache_record_invalid')
    paths = library_paths(cfg)
    commit = record.get('commit', '')
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError('full_cache_commit_invalid')
    checkout = paths['snapshots'] / commit
    root = source_root(checkout, cfg)
    if record.get('root') != str(root) or record.get('url') != cfg['git_url'] or record.get('branch') != cfg.get('git_branch', 'main'):
        raise ValueError('full_cache_origin_mismatch')
    if not (checkout / '.git').exists():
        raise ValueError('full_cache_missing')
    if git(['config', '--get', 'remote.origin.url'], checkout) != cfg['git_url']:
        raise ValueError('full_cache_origin_mismatch')
    if git(['status', '--porcelain', '--untracked-files=all'], checkout):
        raise ValueError('full_cache_dirty')
    if git(['rev-parse', 'HEAD'], checkout) != commit:
        raise ValueError('full_cache_commit_mismatch')
    manifest = root / cfg.get('manifest', 'knowledge-manifest.json')
    if sha256(manifest.read_bytes()).hexdigest() != record.get('manifest_sha256'):
        raise ValueError('full_cache_manifest_hash_mismatch')
    validate(root, cfg)
    return root, commit


def cached(cfg, git, validate):
    marker = library_paths(cfg)['marker']
    if not marker.is_file():
        raise ValueError('full_cache_missing')
    record = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(record, dict):
        raise ValueError('full_cache_record_invalid')
    failures = []
    for candidate in [record, record.get('previous')]:
        if not isinstance(candidate, dict):
            continue
        try:
            root, commit = verify_record(cfg, candidate, git, validate)
            return root, commit, '; '.join(failures) or None
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append(str(exc))
    raise ValueError('full_cache_invalid: ' + '; '.join(failures))


def online(cfg, git, validate):
    paths = library_paths(cfg)
    url = cfg.get('git_url', '')
    branch = cfg.get('git_branch', 'main')
    if not url.startswith('https://'):
        raise ValueError('Git 知识库需要 HTTPS git_url')
    git(['check-ref-format', '--branch', branch])
    with exclusive_lock(paths['lock'], timeout=cfg.get('cache_lock_timeout', 10)):
        remote = git(['ls-remote', '--exit-code', url, 'refs/heads/' + branch])
        lines = [row.split() for row in remote.splitlines() if row.strip()]
        if len(lines) != 1 or len(lines[0]) != 2 or not COMMIT.fullmatch(lines[0][0]):
            raise ValueError('GIT_REMOTE_COMMIT_INVALID')
        commit = lines[0][0]
        checkout = paths['snapshots'] / commit
        root = source_root(checkout, cfg)
        old = None
        try:
            old_root, old_commit, _ = cached(cfg, git, validate)
            old = make_record(cfg, old_root, old_commit)
        except (OSError, RuntimeError, ValueError):
            pass
        if not checkout.exists():
            paths['snapshots'].mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.candidate-', dir=paths['root']) as temporary:
                candidate_dir = Path(temporary).resolve()
                # Temporary cleanup is restricted to this task-owned cache namespace.
                if not candidate_dir.is_relative_to(paths['root'].resolve()):
                    raise ValueError('CACHE_TEMP_PATH_INVALID')
                candidate = candidate_dir / 'checkout'
                # No partial/blob-filtered clone: an accepted snapshot must be usable offline.
                git(['-c', 'core.autocrlf=false', 'clone', '--depth', '1', '--single-branch',
                     '--branch', branch, url, str(candidate)], timeout=cfg.get('git_download_timeout', 180))
                if git(['rev-parse', 'HEAD'], candidate) != commit:
                    raise ValueError('GIT_REMOTE_CHANGED_DURING_DOWNLOAD')
                validate(source_root(candidate, cfg), cfg)
                candidate.rename(checkout)
        record = make_record(cfg, root, commit)
        verify_record(cfg, record, git, validate)
        if old and old['commit'] != commit:
            record['previous'] = old
        elif paths['marker'].is_file():
            try:
                existing = json.loads(paths['marker'].read_text(encoding='utf-8'))
                previous = existing.get('previous') if isinstance(existing, dict) else None
                if previous:
                    verify_record(cfg, previous, git, validate)
                    record['previous'] = previous
            except (OSError, RuntimeError, ValueError):
                pass
        atomic_json(paths['marker'], record)
        return root


def make_record(cfg, root, commit):
    manifest = root / cfg.get('manifest', 'knowledge-manifest.json')
    return {'schema_version': '2.0', 'commit': commit, 'root': str(root),
            'url': cfg['git_url'], 'branch': cfg.get('git_branch', 'main'),
            'manifest_sha256': sha256(manifest.read_bytes()).hexdigest()}

"""Resolve verified knowledge snapshots without modifying the installation directory."""
from pathlib import Path
import json
import os
import subprocess
from hashlib import sha256
import time
import re

from distribution import verify_manifest
from managed_library_cache import online as managed_online, cached as managed_cached

SKILL = Path(__file__).resolve().parents[1]


def config():
    return json.loads((SKILL / 'knowledge-base.json').read_text(encoding='utf-8-sig'))


def _git(args, cwd=None, timeout=35):
    attempts = 2 if args and args[0] in ('fetch', 'ls-remote') else 1
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                ['git', *args], cwd=cwd, capture_output=True, text=True,
                encoding='utf-8', errors='strict', timeout=timeout,
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never',
                     'GIT_OPTIONAL_LOCKS': '0'},
            )
        except subprocess.TimeoutExpired as exc:
            error = 'git_timeout: ' + ' '.join(args[:2])
        except UnicodeDecodeError:
            error = 'git_output_encoding'
        except FileNotFoundError:
            raise RuntimeError('git_not_installed')
        else:
            if result.returncode == 0:
                return result.stdout.strip()
            detail = result.stderr.strip() or result.stdout.strip()
            detail = re.sub(r'https?://[^\s/@]+:[^\s/@]+@', 'https://[REDACTED]@', detail)
            lowered = detail.lower()
            if any(x in lowered for x in ('403', '401', 'authentication', 'permission denied', 'repository not found')):
                category = 'git_permission'
            elif 'proxy' in lowered or 'connect tunnel' in lowered:
                category = 'git_proxy'
            elif any(x in lowered for x in ('ssl certificate', 'certificate verify', 'server certificate')):
                category = 'git_tls'
            elif any(x in lowered for x in ('502', '503', 'timed out', 'could not resolve', 'connection')):
                category = 'git_network'
            else:
                category = 'git_command'
            error = category + ': ' + detail
        if attempt + 1 < attempts:
            time.sleep(0.5)
    raise RuntimeError(error)


def verified_full_cache(cfg, marker):
    """Use only the previously validated, clean checkout at the marked commit."""
    checkout = (SKILL / cfg['git_checkout_path']).resolve()
    if not marker.is_file() or not (checkout / '.git').exists():
        raise RuntimeError('full_cache_missing')
    record = json.loads(marker.read_text(encoding='utf-8'))
    if not isinstance(record, dict):
        raise ValueError('full_cache_record_invalid')
    if record.get('root') != str((checkout / cfg.get('git_repository_directory', '.')).resolve()):
        raise RuntimeError('full_cache_origin_mismatch: root')
    if _git(['remote', 'get-url', 'origin'], checkout) != cfg['git_url']:
        raise RuntimeError('full_cache_origin_mismatch: origin')
    if _git(['branch', '--show-current'], checkout) != cfg.get('git_branch', 'main'):
        raise RuntimeError('full_cache_branch_mismatch')
    if _git(['status', '--porcelain'], checkout):
        raise RuntimeError('full_cache_dirty')
    commit = _git(['rev-parse', 'HEAD'], checkout)
    if not commit or commit != record.get('commit'):
        raise RuntimeError('full_cache_commit_mismatch')
    root = (checkout / cfg.get('git_repository_directory', '.')).resolve()
    manifest = root / cfg.get('manifest', 'knowledge-manifest.json')
    if not manifest.is_file() or sha256(manifest.read_bytes()).hexdigest() != record.get('manifest_sha256'):
        raise RuntimeError('full_cache_manifest_hash_mismatch')
    validate_manifest(root, cfg)
    return root, commit


def git_library(cfg):
    return managed_online(cfg, _git, validate_manifest)


def validate_manifest(root, cfg):
    """Validate every distributed file before a checkout becomes reusable."""
    root = Path(root).resolve()
    if not (root / 'catalog.json').is_file():
        raise FileNotFoundError('知识库目录缺少 catalog.json：' + str(root))
    manifest = root / cfg.get('manifest', 'knowledge-manifest.json')
    if not manifest.is_file():
        raise FileNotFoundError('知识库目录缺少清单：' + str(manifest))
    return verify_manifest(root, cfg.get('manifest', 'knowledge-manifest.json'), cfg['version'])


def resolve_library(override=None, *, allow_verified_cache=True, cache_only=False):
    """Return (root, source, commit, warning). A failed fetch never validates an unknown cache."""
    cfg = config()
    if override is not None:
        root = Path(override).resolve()
        manifest = validate_manifest(root, cfg)
        commit = _git(['rev-parse', 'HEAD'], root) if (root / '.git').exists() else manifest.get('source_commit')
        return root, 'explicit_verified', commit, None
    if cfg.get('mode') != 'git':
        root = (SKILL / cfg['local_path']).resolve()
        validate_manifest(root, cfg)
        return root, 'local_verified_template', None, None
    pack = (SKILL / cfg['offline_pack_path']).resolve()
    try:
        if cache_only:
            raise RuntimeError('offline_cache_only')
        root = git_library(cfg)
        validate_manifest(root, cfg)
        commit = _git(['rev-parse', 'HEAD'], root)
        # Full snapshots already provide offline access. Never regenerate the bundled
        # minimum package or write last-good state into an installation directory.
        return root, 'remote_template', commit, None
    except (RuntimeError, OSError, ValueError) as exc:
        failures = [] if cache_only else [str(exc)]
        if allow_verified_cache:
            try:
                root, commit, recovery = managed_cached(cfg, _git, validate_manifest)
                if recovery:
                    failures.append('recovered_previous_snapshot: ' + recovery)
                return root, 'verified_full_cache', commit, '; '.join(failures) or None
            except (RuntimeError, OSError, ValueError) as cache_exc:
                failures.append(str(cache_exc))
            # Compatibility only: validate old last-good records but never update or
            # modify the old checkout. New successful downloads use managed snapshots.
            try:
                marker = (SKILL / cfg['cache_path']).resolve() / 'last-good.json'
                root, commit = verified_full_cache(cfg, marker)
                return root, 'verified_full_cache', commit, '; '.join(failures + ['legacy_cache_read_only'])
            except (RuntimeError, OSError, ValueError, KeyError) as legacy_exc:
                failures.append(str(legacy_exc))
        if not allow_verified_cache:
            raise RuntimeError('; '.join(failures)) from exc
        if not pack.is_dir():
            raise RuntimeError('; '.join(failures)) from exc
        manifest = validate_manifest(pack, cfg)
        return pack, 'local_verified_template', manifest['source_commit'], '; '.join(failures) or None


def get_library(override=None):
    if override is not None:
        root = Path(override).resolve()
        if not (root / 'catalog.json').is_file():
            raise FileNotFoundError('知识库目录缺少 catalog.json：' + str(root))
        return root
    return resolve_library()[0]

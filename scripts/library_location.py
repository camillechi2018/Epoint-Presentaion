"""Resolve the configured knowledge base, updating the Git checkout when used."""
from pathlib import Path
import json
import os
import subprocess
from hashlib import sha256
import tempfile
import time

from build_minimal_pack import build as build_minimal_pack

SKILL = Path(__file__).resolve().parents[1]


def config():
    return json.loads((SKILL / 'knowledge-base.json').read_text(encoding='utf-8-sig'))


def _git(args, cwd=None):
    attempts = 2 if args and args[0] in ('fetch', 'clone') else 1
    for attempt in range(attempts):
        try:
            result = subprocess.run(
                ['git', *args], cwd=cwd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=35,
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'},
            )
        except subprocess.TimeoutExpired as exc:
            error = 'git_timeout: ' + ' '.join(args[:2])
        else:
            if result.returncode == 0:
                return result.stdout.strip()
            detail = result.stderr.strip() or result.stdout.strip()
            lowered = detail.lower()
            if any(x in lowered for x in ('403', '401', 'authentication', 'permission denied', 'repository not found')):
                category = 'git_permission'
            elif any(x in lowered for x in ('proxy', '502', '503', 'timed out', 'could not resolve', 'connection')):
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
    url = cfg.get('git_url')
    branch = cfg.get('git_branch', 'main')
    checkout = (SKILL / cfg['git_checkout_path']).resolve()
    if not url or not url.startswith('https://'):
        raise ValueError('Git 知识库需要 HTTPS git_url')
    if not (checkout / '.git').exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        _git(['-c', 'core.autocrlf=false', 'clone', '--depth', '1', '--filter=blob:none', '--single-branch',
              '--branch', branch, url, str(checkout)])
    if _git(['remote', 'get-url', 'origin'], checkout) != url:
        raise RuntimeError('知识库缓存的 origin 与配置不符：' + str(checkout))
    _git(['config', 'core.autocrlf', 'false'], checkout)
    if _git(['branch', '--show-current'], checkout) != branch:
        raise RuntimeError('知识库缓存不在指定分支：' + str(checkout))
    if _git(['status', '--porcelain'], checkout):
        raise RuntimeError('知识库缓存有本地改动，无法安全更新：' + str(checkout))
    _git(['fetch', 'origin', branch], checkout)
    remote_head = _git(['rev-parse', 'FETCH_HEAD'], checkout)
    local_head = _git(['rev-parse', 'HEAD'], checkout)
    if local_head != remote_head:
        # Check the incoming tree before changing the last known good checkout.
        with tempfile.TemporaryDirectory(prefix='epoint-candidate-', dir=checkout.parent) as temporary:
            _git(['worktree', 'add', '--detach', temporary, remote_head], checkout)
            try:
                validate_manifest(Path(temporary) / cfg.get('git_repository_directory', '.'), cfg)
            finally:
                _git(['worktree', 'remove', '--force', temporary], checkout)
        _git(['merge', '--ff-only', 'FETCH_HEAD'], checkout)
    directory = cfg.get('git_repository_directory', '.')
    root = (checkout / directory).resolve()
    if not root.is_relative_to(checkout):
        raise ValueError('非法 Git 知识库子目录：' + directory)
    return root


def validate_manifest(root, cfg):
    """Validate every distributed file before a checkout becomes reusable."""
    root = Path(root).resolve()
    if not (root / 'catalog.json').is_file():
        raise FileNotFoundError('知识库目录缺少 catalog.json：' + str(root))
    manifest = root / cfg.get('manifest', 'knowledge-manifest.json')
    if not manifest.is_file():
        raise FileNotFoundError('知识库目录缺少清单：' + str(manifest))
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('version') != cfg['version']:
        raise RuntimeError(f'知识库版本 {data.get("version")} 与 Skill 配置 {cfg["version"]} 不一致')
    for relative, expected in data.get('files', {}).items():
        file = (root / relative).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise RuntimeError('知识库清单缺失或非法文件：' + relative)
        if sha256(file.read_bytes()).hexdigest() != expected:
            raise RuntimeError('知识库文件哈希不匹配：' + relative)
    return data


def resolve_library(override=None, *, allow_verified_cache=True, cache_only=False):
    """Return (root, source, commit, warning). A failed fetch never validates an unknown cache."""
    cfg = config()
    if override is not None:
        root = Path(override).resolve()
        manifest = validate_manifest(root, cfg)
        commit = _git(['rev-parse', 'HEAD'], root) if (root / '.git').is_dir() else manifest.get('source_commit')
        return root, 'explicit_verified', commit, None
    if cfg.get('mode') != 'git':
        root = (SKILL / cfg['local_path']).resolve()
        validate_manifest(root, cfg)
        return root, 'local_verified_template', None, None
    marker = (SKILL / cfg['cache_path']).resolve() / 'last-good.json'
    pack = (SKILL / cfg['offline_pack_path']).resolve()
    try:
        if cache_only:
            raise RuntimeError('offline_cache_only')
        root = git_library(cfg)
        validate_manifest(root, cfg)
        commit = _git(['rev-parse', 'HEAD'], root)
        pack_manifest = pack / cfg.get('manifest', 'knowledge-manifest.json')
        needs_pack = True
        if pack_manifest.is_file():
            try:
                needs_pack = validate_manifest(pack, cfg).get('source_commit') != commit
            except (RuntimeError, FileNotFoundError, ValueError):
                needs_pack = True
        if needs_pack:
            build_minimal_pack(root, pack)
            if validate_manifest(pack, cfg).get('source_commit') != commit:
                raise RuntimeError('离线模板包版本与远端知识库不一致')
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({'commit': commit,
                                      'manifest_sha256': sha256((root / cfg.get('manifest', 'knowledge-manifest.json')).read_bytes()).hexdigest(),
                                      'root': str(root)}, ensure_ascii=False, indent=2), encoding='utf-8')
        return root, 'remote_template', commit, None
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        if allow_verified_cache:
            try:
                root, commit = verified_full_cache(cfg, marker)
                return root, 'verified_full_cache', commit, None if cache_only else str(exc)
            except (RuntimeError, FileNotFoundError, ValueError) as cache_exc:
                cache_warning = str(exc) + '; ' + str(cache_exc)
        else:
            cache_warning = str(exc)
        if not allow_verified_cache or not pack.is_dir():
            raise RuntimeError(cache_warning) from exc
        manifest = validate_manifest(pack, cfg)
        return pack, 'local_verified_template', manifest['source_commit'], None if cache_only else cache_warning


def get_library(override=None):
    if override is not None:
        root = Path(override).resolve()
        if not (root / 'catalog.json').is_file():
            raise FileNotFoundError('知识库目录缺少 catalog.json：' + str(root))
        return root
    return resolve_library()[0]

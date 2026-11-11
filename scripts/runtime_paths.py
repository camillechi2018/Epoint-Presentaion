"""Platform-aware locations, without creating directories at import time."""
import os
import sys
import hashlib
import json
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]


def state_root(override=None):
    explicit = override or os.environ.get('EPOINT_STATE_DIR')
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state'))
    return (base / 'epoint-presentation').resolve()


def locations(override=None):
    state = state_root(override)
    return {'skill': str(SKILL_ROOT), 'state': str(state),
            'cache': str(Path(os.environ.get('EPOINT_CACHE_DIR', state / 'cache')).expanduser().resolve()),
            'venv': str(state / 'venv')}


def library_paths(cfg):
    identity = {key: cfg.get(key) for key in ('git_url', 'git_branch', 'git_repository_directory', 'version')}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode('utf-8')).hexdigest()[:24]
    root = Path(locations()['cache']) / 'libraries' / key
    return {'root': root, 'snapshots': root / 'snapshots', 'marker': root / 'last-good.json',
            'lock': root / 'update.lock'}

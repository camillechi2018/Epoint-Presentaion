"""Atomic JSON records and crash-released locks for user-owned runtime state."""
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pending-', delete=False) as handle:
        pending = Path(handle.name)
        handle.write((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(pending, path)
    finally:
        if pending.exists():
            pending.unlink()


@contextmanager
def exclusive_lock(path, timeout=10):
    """OS lock releases on process termination; the persistent lock file is not an owner flag."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'0')
            handle.flush()
        deadline = time.monotonic() + timeout
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('CACHE_LOCK_TIMEOUT')
                time.sleep(0.1)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)

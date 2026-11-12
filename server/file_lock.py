"""Cross-process JSON store locking.

The JSON stores are single-writer by design. This guard prevents lost updates
when more than one process (for example uvicorn workers) performs a
read-modify-write cycle. It is re-entrant for nested calls in one thread.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

_local = threading.local()


@contextmanager
def file_lock(path: str | Path):
    lock_path = Path(str(path) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    depth = getattr(_local, "depth", 0)
    if depth:
        # A nested public mutator already holds the lock for this process.
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    if fcntl is None:
        _local.depth = 1
        try:
            yield
        finally:
            _local.depth = 0
        return
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _local.depth = 1
        try:
            yield
        finally:
            _local.depth = 0
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def locked(path_getter):
    """Decorator for a public read-modify-write function."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with file_lock(path_getter()):
                return func(*args, **kwargs)
        return wrapper
    return decorator

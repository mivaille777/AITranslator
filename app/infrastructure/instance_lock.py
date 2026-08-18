"""Single-instance protection for the desktop application."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QLockFile

DEFAULT_LOCK_PATH = (
    Path(tempfile.gettempdir()) / "AITranslator.DesktopTranslator.lock"
)


class SingleInstanceLock:
    """Hold a machine-wide lock shared by all Python environments."""

    def __init__(self, path: str | Path = DEFAULT_LOCK_PATH) -> None:
        self.path = Path(path)
        self._lock = QLockFile(str(self.path))
        # A normal application process owns the lock for its full lifetime;
        # an abandoned lock can be recovered after a short crash grace period.
        self._lock.setStaleLockTime(30_000)

    def acquire(self) -> bool:
        """Try to acquire the lock without blocking the Qt startup path."""

        return bool(self._lock.tryLock(0))

    def release(self) -> None:
        """Release the lock if this process owns it."""

        self._lock.unlock()

    def __enter__(self) -> "SingleInstanceLock":
        if not self.acquire():
            raise RuntimeError("another application instance is already running")
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.release()

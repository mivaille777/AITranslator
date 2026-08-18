"""Thread-safe request versioning for concurrent translation work."""

from __future__ import annotations

from threading import Lock


class RequestVersionController:
    """Allocate monotonically increasing IDs and identify the latest one."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._latest_request_id = 0

    @property
    def latest_request_id(self) -> int:
        """Return the newest allocated request ID safely."""

        with self._lock:
            return self._latest_request_id

    def next_request_id(self) -> int:
        """Allocate and return the next request ID."""

        with self._lock:
            self._latest_request_id += 1
            return self._latest_request_id

    def is_latest(self, request_id: int) -> bool:
        """Return whether ``request_id`` is still the newest request."""

        with self._lock:
            return request_id == self._latest_request_id


__all__ = ["RequestVersionController"]

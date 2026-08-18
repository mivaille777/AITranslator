"""Tests for the application's single-instance guard."""

from __future__ import annotations

from app.infrastructure.instance_lock import SingleInstanceLock


def test_single_instance_lock_blocks_a_second_owner(tmp_path) -> None:
    lock_path = tmp_path / "desktop-translator.lock"
    first = SingleInstanceLock(lock_path)
    second = SingleInstanceLock(lock_path)

    assert first.acquire()
    try:
        assert not second.acquire()
    finally:
        first.release()

    assert second.acquire()
    second.release()

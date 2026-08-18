"""Tests for Step9 request version allocation and freshness checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.translation.request_version import RequestVersionController


def test_request_ids_are_monotonic_and_latest_is_identifiable() -> None:
    versions = RequestVersionController()

    first = versions.next_request_id()
    second = versions.next_request_id()

    assert (first, second) == (1, 2)
    assert versions.latest_request_id == 2
    assert versions.is_latest(first) is False
    assert versions.is_latest(second) is True


def test_request_id_allocation_is_thread_safe() -> None:
    versions = RequestVersionController()

    with ThreadPoolExecutor(max_workers=8) as executor:
        request_ids = list(executor.map(lambda _index: versions.next_request_id(), range(100)))

    assert sorted(request_ids) == list(range(1, 101))
    assert versions.latest_request_id == 100

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from time import monotonic


@dataclass(frozen=True, slots=True)
class CompanionConversationLease:
    conversation_id: str
    owner_id: str
    owner_surface: str
    request_id: int
    acquired_at: float
    touched_at: float


@dataclass(frozen=True, slots=True)
class CompanionOwnershipClaim:
    acquired: bool
    reason: str
    lease: CompanionConversationLease | None


class CompanionConversationOwnershipService:
    """Process-local lease registry for one active generation per conversation.

    The FastAPI backend is the final concurrency authority. Main and overlay
    WebViews may race, so frontend flags are only advisory. A lease is released
    when the owning WebSocket reaches a terminal state or disconnects. A long
    TTL is kept as a final stale-owner recovery mechanism for abnormal task
    termination; normal streaming calls ``touch`` while provider output arrives.
    """

    def __init__(
        self,
        *,
        stale_after_seconds: float = 15 * 60,
        duplicate_window_seconds: float = 2 * 60,
    ) -> None:
        self._stale_after_seconds = max(30.0, float(stale_after_seconds))
        self._duplicate_window_seconds = max(5.0, float(duplicate_window_seconds))
        self._lock = RLock()
        self._leases: dict[str, CompanionConversationLease] = {}
        self._recent_requests: dict[tuple[str, str, int], float] = {}

    @property
    def stale_after_seconds(self) -> float:
        return self._stale_after_seconds

    @staticmethod
    def _conversation_id(value: object) -> str:
        return str(value or "").strip()[:128]

    @staticmethod
    def _owner_id(value: object) -> str:
        return str(value or "").strip()[:128]

    @staticmethod
    def _owner_surface(value: object) -> str:
        candidate = str(value or "unknown").strip().lower()
        return candidate if candidate in {"main", "overlay", "unknown"} else "unknown"

    def _cleanup_locked(self, now: float) -> None:
        stale_ids = [
            conversation_id
            for conversation_id, lease in self._leases.items()
            if now - lease.touched_at >= self._stale_after_seconds
        ]
        for conversation_id in stale_ids:
            self._leases.pop(conversation_id, None)

        stale_request_keys = [
            key
            for key, completed_at in self._recent_requests.items()
            if now - completed_at >= self._duplicate_window_seconds
        ]
        for key in stale_request_keys:
            self._recent_requests.pop(key, None)

    def acquire(
        self,
        conversation_id: str,
        *,
        owner_id: str,
        owner_surface: str,
        request_id: int,
    ) -> CompanionOwnershipClaim:
        candidate = self._conversation_id(conversation_id)
        normalized_owner = self._owner_id(owner_id)
        normalized_surface = self._owner_surface(owner_surface)
        normalized_request = max(0, int(request_id))
        if not candidate or not normalized_owner:
            return CompanionOwnershipClaim(False, "invalid_owner", None)

        now = monotonic()
        with self._lock:
            self._cleanup_locked(now)
            existing = self._leases.get(candidate)
            if existing is not None:
                if (
                    existing.owner_id == normalized_owner
                    and existing.request_id == normalized_request
                ):
                    return CompanionOwnershipClaim(False, "duplicate_active_request", existing)
                return CompanionOwnershipClaim(False, "conversation_busy", existing)

            if normalized_request > 0:
                recent_key = (candidate, normalized_owner, normalized_request)
                if recent_key in self._recent_requests:
                    return CompanionOwnershipClaim(False, "duplicate_request", None)

            lease = CompanionConversationLease(
                conversation_id=candidate,
                owner_id=normalized_owner,
                owner_surface=normalized_surface,
                request_id=normalized_request,
                acquired_at=now,
                touched_at=now,
            )
            self._leases[candidate] = lease
            return CompanionOwnershipClaim(True, "acquired", lease)

    def touch(
        self,
        conversation_id: str,
        *,
        owner_id: str,
        request_id: int,
    ) -> bool:
        candidate = self._conversation_id(conversation_id)
        normalized_owner = self._owner_id(owner_id)
        normalized_request = max(0, int(request_id))
        if not candidate or not normalized_owner:
            return False

        now = monotonic()
        with self._lock:
            self._cleanup_locked(now)
            lease = self._leases.get(candidate)
            if (
                lease is None
                or lease.owner_id != normalized_owner
                or lease.request_id != normalized_request
            ):
                return False
            self._leases[candidate] = CompanionConversationLease(
                conversation_id=lease.conversation_id,
                owner_id=lease.owner_id,
                owner_surface=lease.owner_surface,
                request_id=lease.request_id,
                acquired_at=lease.acquired_at,
                touched_at=now,
            )
            return True

    def release(
        self,
        conversation_id: str,
        *,
        owner_id: str,
        request_id: int,
    ) -> bool:
        candidate = self._conversation_id(conversation_id)
        normalized_owner = self._owner_id(owner_id)
        normalized_request = max(0, int(request_id))
        if not candidate or not normalized_owner:
            return False

        now = monotonic()
        with self._lock:
            self._cleanup_locked(now)
            lease = self._leases.get(candidate)
            if (
                lease is None
                or lease.owner_id != normalized_owner
                or lease.request_id != normalized_request
            ):
                return False
            self._leases.pop(candidate, None)
            if normalized_request > 0:
                self._recent_requests[(candidate, normalized_owner, normalized_request)] = now
            return True

    def snapshot(self, conversation_id: str) -> CompanionConversationLease | None:
        candidate = self._conversation_id(conversation_id)
        if not candidate:
            return None
        now = monotonic()
        with self._lock:
            self._cleanup_locked(now)
            return self._leases.get(candidate)

    def clear(self) -> None:
        with self._lock:
            self._leases.clear()
            self._recent_requests.clear()


__all__ = [
    "CompanionConversationLease",
    "CompanionConversationOwnershipService",
    "CompanionOwnershipClaim",
]

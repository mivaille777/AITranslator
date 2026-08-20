from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CompanionHandoffState:
    revision: int
    handoff_id: str
    created_at: str
    source_text: str
    translated_text: str = ""
    source_language: str = "auto"
    target_language: str = "zh-CN"
    resource_url: str = ""
    resource_title: str = ""
    section_heading: str = ""
    context_before: str = ""
    context_after: str = ""
    source_kind: str = "browser_selection"
    ai_content: str = ""
    ai_action: str = ""
    suggested_prompt: str = ""


class CompanionHandoffService:
    """Thread-safe latest-context handoff between overlay and the main workspace."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._revision = 0
        self._handoff: CompanionHandoffState | None = None

    def snapshot(self) -> CompanionHandoffState | None:
        with self._lock:
            return self._handoff

    def create(
        self,
        *,
        source_text: str,
        translated_text: str = "",
        source_language: str = "auto",
        target_language: str = "zh-CN",
        resource_url: str = "",
        resource_title: str = "",
        section_heading: str = "",
        context_before: str = "",
        context_after: str = "",
        source_kind: str = "browser_selection",
        ai_content: str = "",
        ai_action: str = "",
        suggested_prompt: str = "",
    ) -> CompanionHandoffState:
        text = str(source_text).strip()
        if not text:
            raise ValueError("Companion handoff requires selected source text.")

        with self._lock:
            self._revision += 1
            self._handoff = CompanionHandoffState(
                revision=self._revision,
                handoff_id=uuid4().hex,
                created_at=_now_iso(),
                source_text=text,
                translated_text=str(translated_text or "").strip(),
                source_language=str(source_language or "auto").strip() or "auto",
                target_language=str(target_language or "zh-CN").strip() or "zh-CN",
                resource_url=str(resource_url or "").strip(),
                resource_title=str(resource_title or "").strip(),
                section_heading=str(section_heading or "").strip(),
                context_before=str(context_before or "").strip(),
                context_after=str(context_after or "").strip(),
                source_kind=str(source_kind or "browser_selection").strip()
                or "browser_selection",
                ai_content=str(ai_content or "").strip(),
                ai_action=str(ai_action or "").strip(),
                suggested_prompt=str(suggested_prompt or "").strip(),
            )
            return self._handoff

    def clear(self, *, handoff_id: str = "") -> CompanionHandoffState | None:
        """Clear only the handoff the caller observed.

        A stale main-window dismissal must never erase a newer overlay handoff.
        """

        identifier = str(handoff_id or "").strip()
        with self._lock:
            current = self._handoff
            if current is None:
                return None
            if identifier and identifier != current.handoff_id:
                return current
            self._revision += 1
            self._handoff = None
            return None

from __future__ import annotations

from threading import Lock

from backend.services.agent_trace_store_service import AgentTraceStoreService

_agent_trace_store_service: AgentTraceStoreService | None = None
_agent_trace_store_service_lock = Lock()


def get_agent_trace_store_service() -> AgentTraceStoreService:
    global _agent_trace_store_service
    if _agent_trace_store_service is not None:
        return _agent_trace_store_service

    with _agent_trace_store_service_lock:
        if _agent_trace_store_service is None:
            _agent_trace_store_service = AgentTraceStoreService()
        return _agent_trace_store_service


def close_agent_trace_store_service() -> None:
    global _agent_trace_store_service
    with _agent_trace_store_service_lock:
        _agent_trace_store_service = None


__all__ = ["get_agent_trace_store_service", "close_agent_trace_store_service"]

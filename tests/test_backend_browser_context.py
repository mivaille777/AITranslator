from fastapi.testclient import TestClient

from app.selection.browser_page_bridge import BrowserReadingBridge
from backend.api.dependencies import get_browser_context_service
from backend.main import app
from backend.services.browser_context_service import BrowserContextService


def _service_with_browser_context() -> BrowserContextService:
    bridge = BrowserReadingBridge(port=0, clock=lambda: 11.5)
    bridge.ingest_payload(
        {
            "version": 1,
            "type": "page",
            "url": "https://example.com/paper",
            "title": "Example Paper",
            "heading": "Introduction",
            "frame_url": "https://example.com/paper",
        },
        received_at=10.0,
    )
    bridge.ingest_payload(
        {
            "version": 1,
            "type": "selection",
            "text": "Selected research text",
            "url": "https://example.com/paper",
            "title": "Example Paper",
            "heading": "Introduction",
            "context_before": "Before context",
            "context_after": "After context",
            "frame_url": "https://example.com/paper",
            "top_level": True,
            "captured_at_ms": 1234,
        },
        received_at=11.0,
    )
    return BrowserContextService(bridge=bridge)


def test_browser_context_endpoints_expose_existing_bridge_snapshots() -> None:
    service = _service_with_browser_context()
    app.dependency_overrides[get_browser_context_service] = lambda: service
    try:
        client = TestClient(app)

        status_response = client.get("/api/browser/status")
        selection_response = client.get("/api/browser/selection")
        page_response = client.get("/api/browser/page")

        assert status_response.status_code == 200
        assert status_response.json()["has_extension_activity"] is True

        assert selection_response.status_code == 200
        selection = selection_response.json()["selection"]
        assert selection["text"] == "Selected research text"
        assert selection["heading"] == "Introduction"
        assert selection["context_before"] == "Before context"
        assert selection["context_after"] == "After context"

        assert page_response.status_code == 200
        page = page_response.json()["page"]
        assert page["title"] == "Example Paper"
        assert page["url"] == "https://example.com/paper"
    finally:
        app.dependency_overrides.pop(get_browser_context_service, None)


def test_browser_context_endpoints_return_null_when_no_snapshot_exists() -> None:
    service = BrowserContextService(bridge=BrowserReadingBridge(port=0))
    app.dependency_overrides[get_browser_context_service] = lambda: service
    try:
        client = TestClient(app)
        assert client.get("/api/browser/selection").json() == {"selection": None}
        assert client.get("/api/browser/page").json() == {"page": None}
    finally:
        app.dependency_overrides.pop(get_browser_context_service, None)

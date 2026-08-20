from __future__ import annotations

from app.ai import browser_link_opener
from app.ai.browser_link_opener import BrowserChoice, open_url_with_choice


def test_explicit_browser_launch_uses_argument_vector_without_shell(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeProcess:
        pass

    def fake_popen(args, **kwargs):
        captured["args"] = list(args)
        captured["kwargs"] = dict(kwargs)
        return FakeProcess()

    monkeypatch.setattr(browser_link_opener.subprocess, "Popen", fake_popen)

    assert open_url_with_choice(
        BrowserChoice("Browser", r"C:\Browser\browser.exe"),
        "https://example.com/paper?q=agent",
    )
    assert captured["args"] == [
        r"C:\Browser\browser.exe",
        "https://example.com/paper?q=agent",
    ]
    assert captured["kwargs"] == {"close_fds": True}


def test_non_http_link_is_rejected_before_browser_launch(monkeypatch) -> None:
    called = False

    def fake_popen(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("must not launch")

    monkeypatch.setattr(browser_link_opener.subprocess, "Popen", fake_popen)

    assert not open_url_with_choice(
        BrowserChoice("Browser", r"C:\Browser\browser.exe"),
        "file:///C:/private/paper.pdf",
    )
    assert not called

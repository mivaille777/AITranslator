"""Clipboard operating-system access isolated behind a mockable adapter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from time import sleep
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QMimeData
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True, slots=True)
class ClipboardSnapshot:
    """Serialized clipboard data sufficient for the selection workflow."""

    formats: tuple[tuple[str, bytes], ...]
    text: str = ""


def _read_win32_sequence_number() -> int | None:
    """Read the Windows clipboard sequence number when available."""

    try:
        import win32clipboard

        return int(win32clipboard.GetClipboardSequenceNumber())
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        return None


class ClipboardAdapter:
    """Access the clipboard through native Windows text or Qt MIME APIs."""

    def __init__(
        self,
        clipboard: Any | None = None,
        *,
        sequence_number_reader: Callable[[], int | None] | None = None,
        restore_attempts: int = 3,
        restore_delay_seconds: float = 0.05,
        sleeper: Callable[[float], None] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._clipboard_object = clipboard
        self._sequence_number_reader = (
            sequence_number_reader
            if sequence_number_reader is not None
            else _read_win32_sequence_number
        )
        self._restore_attempts = max(1, int(restore_attempts))
        self._restore_delay_seconds = max(0.0, float(restore_delay_seconds))
        self._sleeper = sleeper or sleep
        self._native_windows = clipboard is None and (
            platform_name or sys.platform
        ) == "win32"

    @property
    def clipboard(self) -> Any:
        """Return the configured or process-wide Qt clipboard object."""

        if self._clipboard_object is None:
            if QGuiApplication.instance() is None:
                raise RuntimeError("QGuiApplication is required for clipboard access")
            self._clipboard_object = QGuiApplication.clipboard()
        return self._clipboard_object

    def snapshot(self) -> ClipboardSnapshot:
        """Capture the current clipboard MIME payloads."""

        # QClipboard uses OLE to read and write Windows clipboard data. Some
        # Chromium versions keep private MIME formats open for a short time,
        # which can make an otherwise harmless Qt restore fail. The native
        # path therefore stays text-only for ordinary text, but captures safe
        # Qt MIME formats when a non-text payload such as a screenshot exists.
        if self._native_windows:
            text = self.read_text()
            formats = (
                self._read_qt_formats()
                if self._native_clipboard_has_non_text_data()
                else ()
            )
            return ClipboardSnapshot(formats, text=text)

        text = self.read_text()
        formats = list(self._read_qt_formats())

        # Some clipboard implementations expose text without listing a MIME
        # format. Keep a restorable text representation in that case.
        if not formats:
            if text:
                formats.append(("text/plain", text.encode("utf-8")))

        return ClipboardSnapshot(tuple(formats), text=text)

    def read_text(self) -> str:
        """Return current plain text, or an empty string for non-text data."""

        if self._native_windows:
            return self._read_native_text()

        text = self.clipboard.text()
        return "" if text is None else str(text)

    def write_text(self, text: str) -> None:
        """Replace the clipboard with plain text and verify the write."""

        normalized_text = str(text)
        if self._native_windows:
            self._write_native_text(normalized_text)
        else:
            mime_data = QMimeData()
            mime_data.setText(normalized_text)
            self.clipboard.setMimeData(mime_data)

        if self.read_text() != normalized_text:
            raise RuntimeError("clipboard write could not be verified")

    def get_change_token(self) -> object:
        """Return a token that changes when Windows clipboard content changes."""

        sequence_number = self._sequence_number_reader()
        if sequence_number is not None:
            return sequence_number
        snapshot = self.snapshot()
        return snapshot.formats, snapshot.text

    def restore(self, snapshot: ClipboardSnapshot) -> None:
        """Restore a snapshot while tolerating browser-owned clipboard data."""

        if self._native_windows:
            if snapshot.formats:
                self._restore_qt_formats(snapshot)
                return
            self._restore_native_text(snapshot.text)
            return

        self._restore_qt_formats(snapshot)

    def _read_qt_formats(self) -> tuple[tuple[str, bytes], ...]:
        """Serialize the current Qt MIME payload when a GUI clipboard exists."""

        try:
            mime_data = self.clipboard.mimeData()
        except Exception:
            return ()
        formats: list[tuple[str, bytes]] = []
        if mime_data is not None:
            for mime_format in mime_data.formats():
                formats.append(
                    (str(mime_format), bytes(mime_data.data(mime_format)))
                )
        return tuple(formats)

    def _restore_qt_formats(self, snapshot: ClipboardSnapshot) -> None:
        """Restore safe MIME payloads and verify text or non-text formats."""

        safe_formats = tuple(
            (mime_format, payload)
            for mime_format, payload in snapshot.formats
            if not self._is_unsafe_browser_format(mime_format)
        )

        last_error: Exception | None = None
        for attempt in range(self._restore_attempts):
            try:
                # QClipboard takes ownership of each QMimeData instance, so a
                # fresh object is required for every retry.
                mime_data = QMimeData()
                for mime_format, payload in safe_formats:
                    mime_data.setData(mime_format, QByteArray(payload))
                self.clipboard.setMimeData(mime_data)
                current_formats = {
                    str(item) for item in self.clipboard.mimeData().formats()
                }
                expected_formats = {mime_format for mime_format, _ in safe_formats}
                formats_restored = (
                    not expected_formats
                    or bool(expected_formats.intersection(current_formats))
                )
                if formats_restored and self.read_text() == snapshot.text:
                    return
            except Exception as exc:
                last_error = exc

            if attempt + 1 < self._restore_attempts:
                self._sleeper(self._restore_delay_seconds)

        if last_error is not None:
            raise RuntimeError("clipboard restore failed") from last_error
        raise RuntimeError("clipboard restore could not be verified")

    def _native_clipboard_has_non_text_data(self) -> bool:
        """Check for non-text formats without asking Qt to materialize them."""

        def has_non_text(clipboard_module: Any, constants: Any) -> bool:
            text_formats = {
                getattr(constants, "CF_TEXT", 1),
                getattr(constants, "CF_OEMTEXT", 7),
                getattr(constants, "CF_UNICODETEXT", 13),
            }
            format_id = 0
            while True:
                format_id = int(clipboard_module.EnumClipboardFormats(format_id))
                if not format_id:
                    return False
                if format_id not in text_formats:
                    return True

        try:
            return bool(self._native_clipboard_call(has_non_text))
        except Exception:
            # A locked or unsupported clipboard should not prevent the text
            # selection fallback from proceeding.
            return False

    def _read_native_text(self) -> str:
        """Read CF_UNICODETEXT without asking Qt/OLE to materialize MIME data."""

        def read_formats(clipboard_module: Any, constants: Any) -> str:
            formats = (
                (constants.CF_UNICODETEXT, "utf-16-le"),
                (constants.CF_TEXT, "mbcs"),
            )
            for format_id, encoding in formats:
                try:
                    if not clipboard_module.IsClipboardFormatAvailable(format_id):
                        continue
                except Exception:
                    # GetClipboardData below is still authoritative on older
                    # pywin32 builds that do not expose the availability call.
                    pass

                try:
                    value = clipboard_module.GetClipboardData(format_id)
                except Exception:
                    continue

                if isinstance(value, bytes):
                    value = value.rstrip(b"\x00").decode(
                        encoding,
                        errors="replace",
                    )
                return str(value).rstrip("\x00")
            return ""

        return str(self._native_clipboard_call(read_formats))

    def _restore_native_text(self, text: str) -> None:
        """Restore plain text through the native Windows clipboard API."""

        last_error: Exception | None = None
        for attempt in range(self._restore_attempts):
            try:
                self._write_native_text(text)
                if self.read_text() == text:
                    return
                last_error = RuntimeError(
                    "native clipboard restore could not be verified"
                )
            except Exception as exc:
                last_error = exc

            if attempt + 1 < self._restore_attempts:
                self._sleeper(self._restore_delay_seconds)

        if last_error is not None:
            raise RuntimeError("clipboard restore failed") from last_error
        raise RuntimeError("clipboard restore could not be verified")

    def _write_native_text(self, text: str) -> None:
        """Write CF_UNICODETEXT through a retrying native clipboard lock."""

        def write_text(clipboard_module: Any, constants: Any) -> None:
            clipboard_module.EmptyClipboard()
            if text:
                clipboard_module.SetClipboardData(
                    constants.CF_UNICODETEXT,
                    text,
                )

        self._native_clipboard_call(write_text)

    def _native_clipboard_call(
        self,
        operation: Callable[[Any, Any], Any],
    ) -> Any:
        """Run an operation with a retrying native clipboard ownership lock."""

        try:
            import win32clipboard
            import win32con
        except (ImportError, AttributeError) as exc:
            raise RuntimeError("pywin32 clipboard support is unavailable") from exc

        last_error: Exception | None = None
        open_attempts = max(3, self._restore_attempts)
        for attempt in range(open_attempts):
            opened = False
            try:
                win32clipboard.OpenClipboard()
                opened = True
                return operation(win32clipboard, win32con)
            except Exception as exc:
                last_error = exc
            finally:
                if opened:
                    try:
                        win32clipboard.CloseClipboard()
                    except Exception:
                        # Preserve the operation error, if any. A subsequent
                        # operation will retry opening the clipboard.
                        pass

            if attempt + 1 < open_attempts:
                self._sleeper(self._restore_delay_seconds)

        if last_error is not None:
            raise RuntimeError("native clipboard operation failed") from last_error
        raise RuntimeError("native clipboard operation failed")

    @staticmethod
    def _is_unsafe_browser_format(mime_format: str) -> bool:
        """Exclude browser-private payloads that Qt cannot safely recreate."""

        normalized = str(mime_format).lower()
        return "chromium" in normalized or "rfh token" in normalized

    # These aliases keep the adapter convenient for small integration callers.
    save = snapshot
    get_text = read_text
    set_text = write_text
    change_token = get_change_token

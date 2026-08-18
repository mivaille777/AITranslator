"""Centralized application logging setup."""

from __future__ import annotations

import logging as std_logging
from pathlib import Path
from types import TracebackType

from app.infrastructure.paths import logs_dir

LOGGER_NAME = "desktop_translator"
LOG_FILENAME = "app.log"
_MANAGED_HANDLER_ATTRIBUTE = "_desktop_translator_handler"


def sanitized_exception_info(
    exc: BaseException,
) -> tuple[type[BaseException], BaseException, TracebackType | None]:
    """Return a traceback tuple without copying an exception's message.

    Provider and OS exceptions can occasionally echo a URL, selected text, or
    another request detail.  Keeping the original traceback frames is useful
    for diagnosis, but replacing the value shown after the traceback prevents
    that message from becoming application log content.
    """

    def sanitize(
        error: BaseException,
        seen: set[int],
    ) -> BaseException:
        if id(error) in seen:
            return RuntimeError(type(error).__name__)
        seen.add(id(error))
        try:
            safe_error = type(error)(type(error).__name__)
        except Exception:
            safe_error = RuntimeError(type(error).__name__)
        if error.__cause__ is not None:
            safe_error.__cause__ = sanitize(error.__cause__, seen)
            safe_error.__cause__ = safe_error.__cause__.with_traceback(
                error.__cause__.__traceback__
            )
        elif error.__context__ is not None and not error.__suppress_context__:
            safe_error.__context__ = sanitize(error.__context__, seen)
            safe_error.__context__ = safe_error.__context__.with_traceback(
                error.__context__.__traceback__
            )
        return safe_error.with_traceback(error.__traceback__)

    safe_exception = sanitize(exc, set())
    return type(safe_exception), safe_exception, exc.__traceback__


def _resolve_level(level: int | str) -> int:
    if isinstance(level, int):
        return level

    resolved = std_logging.getLevelName(level.upper())
    if not isinstance(resolved, int):
        raise ValueError(f"Unknown log level: {level}")
    return resolved


def _remove_managed_handlers(logger: std_logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _MANAGED_HANDLER_ATTRIBUTE, False):
            logger.removeHandler(handler)
            handler.close()


def _mark_handler(handler: std_logging.Handler) -> std_logging.Handler:
    setattr(handler, _MANAGED_HANDLER_ATTRIBUTE, True)
    return handler


def configure_logging(
    log_dir: str | Path | None = None,
    level: int | str = std_logging.INFO,
) -> std_logging.Logger:
    """Configure and return the application's dedicated logger.

    The logger writes human-readable messages to both stderr and
    ``<log_dir>/app.log``. Calling this function repeatedly is safe and
    replaces only handlers created by this module.
    """

    logger = std_logging.getLogger(LOGGER_NAME)
    logger.setLevel(_resolve_level(level))
    logger.propagate = False
    _remove_managed_handlers(logger)

    formatter = std_logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = _mark_handler(std_logging.StreamHandler())
    console_handler.setLevel(logger.level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    resolved_log_dir = Path(log_dir) if log_dir is not None else logs_dir()
    try:
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = _mark_handler(
            std_logging.FileHandler(
                resolved_log_dir / LOG_FILENAME,
                encoding="utf-8",
            )
        )
    except OSError as exc:
        # Logging must not prevent the application from starting when the
        # configured log directory is unavailable.
        logger.warning("file_logging_unavailable error=%s", exc)
    else:
        file_handler.setLevel(logger.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

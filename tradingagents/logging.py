"""Structured logging setup via structlog."""

import logging
import sys

import structlog

from tradingagents.config import get_settings


def setup_logging() -> None:
    """Configure structlog for the application.

    Call once at application startup. Subsequent calls are no-ops.
    """
    settings = get_settings()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure stdlib logging to pipe through structlog
    # Stream to stderr (terminal) AND to a file for background monitoring
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        from pathlib import Path
        log_dir = Path.home() / ".tradingagents" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "debug.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        handlers.append(fh)
    except Exception:
        pass  # File logging is best-effort

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=handlers,
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
            pad_event=25,
        )

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                }
            ),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Quiet noisy third-party loggers
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "openai",
        "yfinance",
        "akshare",
        "matplotlib",
        "PIL",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger instance."""
    return structlog.get_logger(name or __name__.replace("tradingagents.", ""))

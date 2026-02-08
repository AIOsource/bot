"""Structured JSON logging with structlog."""
import logging
import sys
import structlog
from datetime import datetime, timezone


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with structlog."""
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Use JSON renderer for production
    processors.append(structlog.processors.JSONRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Also configure standard logging for third-party libs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a bound logger instance."""
    return structlog.get_logger(name)


def bind_trace_id(trace_id: str):
    """Bind trace_id to current context for all subsequent log calls.
    
    Usage:
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        # ... all logs in this context will include trace_id
        structlog.contextvars.unbind_contextvars("trace_id")
    """
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def unbind_trace_id():
    """Remove trace_id from context."""
    try:
        structlog.contextvars.unbind_contextvars("trace_id")
    except KeyError:
        pass


class TraceContext:
    """Context manager for trace_id propagation."""
    
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
    
    def __enter__(self):
        bind_trace_id(self.trace_id)
        return self
    
    def __exit__(self, *args):
        unbind_trace_id()

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once at startup.

    TODO (Day 4): switch to structured JSON logs (e.g. python-json-logger or structlog)
    and attach a request_id from a middleware.
    """
    logging.basicConfig(
        level=level.upper(),
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )

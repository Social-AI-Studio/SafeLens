import os
import logging
from logging.config import dictConfig

_configured = False


def configure_logging() -> None:
    """Configure minimal, consistent console logging for the app and uvicorn.

    Honors environment variables:
    - LOG_LEVEL (default: INFO)
    - LOG_UVICORN_LEVEL (default: INFO)
    - LOG_SQLALCHEMY_LEVEL (default: WARNING)
    """
    global _configured
    if _configured:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    uvicorn_level = os.getenv("LOG_UVICORN_LEVEL", "INFO").upper()
    sa_level = os.getenv("LOG_SQLALCHEMY_LEVEL", "WARNING").upper()

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {
            # Application root
            "": {"handlers": ["console"], "level": level, "propagate": False},
            # Uvicorn loggers
            "uvicorn.error": {
                "handlers": ["console"],
                "level": uvicorn_level,
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console"],
                "level": uvicorn_level,
                "propagate": False,
            },
            # SQLAlchemy engine (reduce noise by default)
            "sqlalchemy.engine": {
                "handlers": ["console"],
                "level": sa_level,
                "propagate": False,
            },
        },
    })

    _configured = True
    logging.getLogger(__name__).debug("Logging configured (level=%s)" % level)

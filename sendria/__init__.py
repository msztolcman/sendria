__all__ = ['__version__']

import sys
from typing import NoReturn

import structlog

__version__ = '2.1.0'

logger = structlog.get_logger()


def exit_err(msg: str, exit_code: int = 1, **kwargs) -> NoReturn:
    logger.error(msg, **kwargs)
    sys.exit(exit_code)

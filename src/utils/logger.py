import logging
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from src.config.settings import settings

def setup_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True
        )
        
        formatter = logging.Formatter(
            "%(message)s",
            datefmt="[%X]"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

logger = setup_logger("orchestrator")

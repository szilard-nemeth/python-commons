import logging
import types
from enum import Enum
from typing import List, Sized, Callable

LOG = logging.getLogger(__name__)

COLLECTION_PLACEHOLDER = "$$coll$$"


class LoggingUtils:
    pass


class LoggerProperties(Enum):
    COMBINED_COLLECTION_LOGGING = (COLLECTION_PLACEHOLDER, "combined")

    def __init__(self, placeholder, func: str):
        self.placeholder = placeholder
        self.func = func


class LoggerFactory:
    @staticmethod
    def get_logger(name: str, props: List[LoggerProperties] = None):
        if not props:
            props = [LoggerProperties.COMBINED_COLLECTION_LOGGING]

        logger = logging.getLogger(name)
        for prop in props:
            real_func = getattr(LoggerFactory, prop.func)
            setattr(logger, prop.func, types.MethodType(real_func, logger))
        return logger

    def combined(self: logging.Logger, msg: str, coll: Sized, coll_func: Callable[[Sized], str] = None):
        if self.level not in [logging.INFO, logging.DEBUG]:
            LOG.error(
                f"Logger level was not among: {[logging.getLevelName(logging.INFO), logging.getLevelName(logging.DEBUG)]}")
            return

        replace = True
        if COLLECTION_PLACEHOLDER not in msg:
            LOG.warning(f"Placeholder not found in message: {msg}. Will append collection to the end of the message.")
            replace = False

        len_coll = str(len(coll))
        info_msg = f"{msg} {len_coll}"
        if replace:
            info_msg = msg.replace(COLLECTION_PLACEHOLDER, len_coll)

        if self.level == logging.INFO:
            self.info(info_msg)
        elif self.level == logging.DEBUG:
            if coll_func:
                coll_str = coll_func(coll)
            else:
                coll_str = str(coll)
            if replace:
                debug_msg = msg.replace(COLLECTION_PLACEHOLDER, coll_str)
            else:
                debug_msg = f"{msg} {coll_str}"
            self.info(info_msg)
            self.debug(debug_msg)

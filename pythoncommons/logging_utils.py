import logging
import types
from enum import Enum
from typing import List, Sized, Callable

LOG = logging.getLogger(__name__)

COLLECTION_PLACEHOLDER = "$$coll$$"


class LoggingUtils:
    pass


class LoggerProperties(Enum):
    COMBINED_COLLECTION_LOGGING = (COLLECTION_PLACEHOLDER, "combined_log")

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

    def combined_log(self: logging.Logger, msg: str,
                     coll: Sized = None,
                     info_coll: Sized = None,
                     debug_coll: Sized = None,
                     info_coll_func: Callable[[Sized], str] = len,
                     debug_coll_func: Callable[[Sized], str] = str,
                     show_warnings: bool = False):
        if not any(e is not None for e in [coll, info_coll, debug_coll]):
            raise ValueError("Wrong collection configuration, one of coll, info_coll or debug_coll should not be None!"
                             "Please verify arguments!")
        if not info_coll:
            info_coll = coll
        if not debug_coll:
            debug_coll = coll
        if not all([info_coll is not None, debug_coll is not None]):
            raise ValueError("Wrong collection configuration, one of info_coll or debug_coll is None! "
                             "Please verify arguments!")

        level = self.getEffectiveLevel()
        # if self.level != logging.NOTSET and self.level not in [logging.INFO, logging.DEBUG]:
        if level not in [logging.INFO, logging.DEBUG]:
            LOG.error(
                f"Logger level was not among: {[logging.getLevelName(logging.INFO), logging.getLevelName(logging.DEBUG)]}")
            return

        replace = True
        if COLLECTION_PLACEHOLDER not in msg:
            if show_warnings:
                LOG.warning(f"Placeholder not found in message: {msg}. Will append collection to the end of the message.")
            replace = False

        len_info_coll = str(info_coll_func(info_coll))
        info_msg = f"{msg} {len_info_coll}"
        if replace:
            info_msg = msg.replace(COLLECTION_PLACEHOLDER, len_info_coll)

        if level == logging.INFO:
            self.info(info_msg)
        elif level == logging.DEBUG:
            debug_coll_str = debug_coll_func(debug_coll)
            if replace:
                debug_msg = msg.replace(COLLECTION_PLACEHOLDER, debug_coll_str)
            else:
                debug_msg = f"{msg} {debug_coll_str}"
            self.info(info_msg)
            self.debug(debug_msg)

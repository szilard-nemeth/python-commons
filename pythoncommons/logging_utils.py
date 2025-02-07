import logging
import os
import sys
import types
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from os.path import expanduser
from typing import List, Sized, Callable
from copy import copy

from pythoncommons.constants import ExecutionMode, PROJECT_NAME
from pythoncommons.logging_setup import SimpleLoggingSetup, DEFAULT_FORMAT, SimpleLoggingSetupConfig
from pythoncommons.project_utils import ProjectRootDeterminationStrategy, ProjectUtils

LOG = logging.getLogger(__name__)

COLLECTION_PLACEHOLDER = "$$coll$$"


class LoggingUtils:
    @staticmethod
    def print_logger_info(logger):
        if not logger:
            return
        print("Logger name: {}".format(logger.name))
        print("Logger effective level: {}".format(logging.getLevelName(logger.getEffectiveLevel())))
        print("Logger handlers: {}".format(logger.handlers))
        print("Logger disabled: {}".format(logger.disabled))
        print("Logger propagate: {}".format(logger.propagate))
        logger.info("here is a test record")
        LoggingUtils.print_logger_info(logger.parent)

    @staticmethod
    def ensure_loggers_are_on_level(loggers: List[str], level: int, project_name_prefix=None):
        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            LoggingUtils.ensure_logger_is_on_level(
                logger,
                level,
                raise_error_if_not_enabled_for=True,
                print_logger_info=True,
                print_additional_details=True,
                project_name_prefix=project_name_prefix,
            )

    @staticmethod
    def ensure_logger_is_on_level(
        logger: logging.Logger,
        level: int,
        raise_error_if_not_enabled_for=False,
        print_logger_info=True,
        print_additional_details=True,
        project_name_prefix=None,
    ):
        if not logger:
            return
        if print_logger_info:
            LoggingUtils.print_logger_info(logger)
        enabled = logger.isEnabledFor(level)
        if raise_error_if_not_enabled_for and not enabled:
            err_message = "Logger {} is not enabled for level {}. Current effective level is: {}".format(
                logger.name, logging.getLevelName(level), logging.getLevelName(logger.getEffectiveLevel())
            )

            if print_additional_details:
                logger_names, all_loggers = SimpleLoggingSetup.get_all_loggers_from_loggerdict()
                pythoncommons_loggers = SimpleLoggingSetup.get_pythoncommons_loggers(all_loggers)
                error_details = f"ALL LOGGERS: {all_loggers}\n" f"PYTHON COMMONS LOGGERS: {pythoncommons_loggers}"
                if project_name_prefix:
                    project_specific_loggers = SimpleLoggingSetup.get_project_specific_loggers(
                        all_loggers, project_name_prefix
                    )
                    error_details += f"\nPROJECT SPECIFIC LOGGERS: {project_specific_loggers}"
                err_message += f"\n{error_details}"
            raise ValueError(err_message)

    @staticmethod
    def create_file_handler(log_file_dir, level: int, fname: str):
        log_file_path = os.path.join(log_file_dir, f"{fname}.log")
        fh = TimedRotatingFileHandler(log_file_path, when="midnight")
        fh.suffix = "%Y_%m_%d.log"
        fh.setLevel(level)
        return fh

    @staticmethod
    def configure_file_logging(level, session_dir, dry_run=False):
        root_logger = logging.getLogger()
        handlers = copy(root_logger.handlers)
        file_handler = LoggingUtils.create_file_handler(session_dir, level, fname="dexter-session")
        file_handler.formatter = None
        LOG.info("Logging to file: %s", file_handler.baseFilename)
        handlers.append(file_handler)

        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if dry_run:
            fmt = f"[DRY-RUN] {fmt}"
        logging.basicConfig(force=True, format=fmt, level=level, handlers=handlers)

    @staticmethod
    def project_setup(execution_mode: ExecutionMode = ExecutionMode.PRODUCTION, dry_run=False):
        strategy = None
        if execution_mode == ExecutionMode.PRODUCTION:
            strategy = ProjectRootDeterminationStrategy.SYS_PATH
        elif execution_mode == ExecutionMode.TEST:
            strategy = ProjectRootDeterminationStrategy.SYS_PATH
        if not strategy:
            raise ValueError("Unknown project root determination strategy!")
        LOG.info("Project root determination strategy is: %s", strategy)
        ProjectUtils.project_root_determine_strategy = strategy
        ProjectUtils.FORCE_SITE_PACKAGES_IN_PATH_NAME = False
        ProjectUtils.ALLOW_PYTHON_COMMONS_AS_PROJECT = True
        _ = ProjectUtils.get_output_basedir(PROJECT_NAME, basedir=expanduser("~"))
        _ = ProjectUtils.get_test_output_basedir(PROJECT_NAME)

        fmt = DEFAULT_FORMAT
        if dry_run:
            fmt = f"[DRY-RUN] {fmt}"
        logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logger(
            project_name=PROJECT_NAME,
            logger_name_prefix=PROJECT_NAME,
            execution_mode=ExecutionMode.TEST,
            console_debug=True,
            postfix=None,
            verbose_git_log=True,
            format_str=fmt,
            add_console_handler=False,
        )
        _log = logging.getLogger()
        _log.info("Logging to files: %s", logging_config.log_file_paths)
        return list(logging_config.log_file_paths.values())

    @staticmethod
    def remove_console_handler(logger):
        filtered_handlers = list(
            filter(
                lambda h: isinstance(h, logging.StreamHandler) and h.stream in (sys.stdout, sys.stderr), logger.handlers
            )
        )

        for handler in filtered_handlers:
            logger.removeHandler(handler)


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

    def combined_log(
        self: logging.Logger,
        msg: str,
        coll: Sized = None,
        info_coll: Sized = None,
        debug_coll: Sized = None,
        info_coll_func: Callable[[Sized], str] = len,
        debug_coll_func: Callable[[Sized], str] = str,
        show_warnings: bool = False,
    ):
        if not any(e is not None for e in [coll, info_coll, debug_coll]):
            raise ValueError(
                "Wrong collection configuration, one of coll, info_coll or debug_coll should not be None!"
                "Please verify arguments!"
            )
        if coll is not None and not info_coll:
            info_coll = coll
        if coll is not None and not debug_coll:
            debug_coll = coll
        if not all([info_coll is not None, debug_coll is not None]):
            raise ValueError(
                "Wrong collection configuration, one of info_coll or debug_coll is None! " "Please verify arguments!"
            )

        level = self.getEffectiveLevel()
        # if self.level != logging.NOTSET and self.level not in [logging.INFO, logging.DEBUG]:
        if level not in [logging.INFO, logging.DEBUG]:
            LOG.error(
                f"Logger level was not among: {[logging.getLevelName(logging.INFO), logging.getLevelName(logging.DEBUG)]}"
            )
            return

        replace = True
        if COLLECTION_PLACEHOLDER not in msg:
            if show_warnings:
                LOG.warning(
                    f"Placeholder not found in message: {msg}. Will append collection to the end of the message."
                )
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

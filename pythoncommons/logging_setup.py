import logging
import os
import sys
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
import logging.config
from typing import List, Dict

from pythoncommons.constants import PROJECT_NAME as PYTHONCOMMONS_PROJECT_NAME, ExecutionMode
from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils
from pythoncommons.project_utils import ProjectUtils

DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

DEFAULT_LOG_YAML_FILENAME = 'logging_default.yaml'


def _get_timestamp_as_str():
    return DateUtils.now_formatted('%Y_%m_%d_%H_%M_%S')


def get_project_logger(project_name, module_name, postfix=None):
    if postfix:
        if postfix.startswith("."):
            postfix = postfix[1:]
        return logging.getLogger("{}.{}.{}".format(project_name, module_name, postfix))
    return logging.getLogger("{}.{}".format(project_name, module_name))


def get_root_logger():
    return logging.getLogger("")


_ROOT_LOG = get_root_logger()
DEFAULT_LOG_LEVEL: int = logging.INFO


@dataclass
class SimpleLoggingSetupConfig:
    project_name: str
    execution_mode: ExecutionMode
    file_log_level_name: str
    console_log_level_name: str
    formatter: str
    console_handler: logging.StreamHandler
    file_handlers: List[logging.FileHandler]
    main_project_logger: logging.Logger
    log_file_paths: Dict[int, str]


# TODO this is copied from another project, eliminate duplication later
class SimpleLoggingSetup:

    @staticmethod
    def init_logging(project_name: str,
                     logger_name_prefix: str,
                     debug: bool = False,
                     console_debug: bool = False,
                     format_str: str = None,
                     file_postfix: str = None,
                     execution_mode: ExecutionMode = ExecutionMode.PRODUCTION,
                     modify_pythoncommons_logger_names: bool = True,
                     remove_existing_handlers: bool = True) -> SimpleLoggingSetupConfig:
        specified_file_log_level: int = logging.DEBUG if debug else DEFAULT_LOG_LEVEL
        specified_file_log_level_name: str = logging.getLevelName(specified_file_log_level)
        default_file_log_level_name: str = logging.getLevelName(DEFAULT_LOG_LEVEL)
        console_log_level: int = logging.DEBUG if debug else DEFAULT_LOG_LEVEL

        if not console_debug:
            console_log_level = DEFAULT_LOG_LEVEL

        final_format_str = DEFAULT_FORMAT
        if format_str:
            final_format_str = format_str
        formatter = logging.Formatter(final_format_str)

        # This will init the root logger to the specified level
        logging.basicConfig(format=final_format_str, level=specified_file_log_level)

        log_file_path_for_default_level = SimpleLoggingSetup._determine_log_file_path(default_file_log_level_name,
                                                                                      file_postfix,
                                                                                      execution_mode, project_name)
        log_file_path_for_specified_level = SimpleLoggingSetup._determine_log_file_path(specified_file_log_level_name,
                                                                                        file_postfix,
                                                                                        execution_mode, project_name)
        log_file_paths: Dict[int, str] = {DEFAULT_LOG_LEVEL: log_file_path_for_default_level}
        console_handler = SimpleLoggingSetup._create_console_handler(console_log_level)
        handlers = [
            console_handler,
            SimpleLoggingSetup._create_file_handler(log_file_path_for_default_level, DEFAULT_LOG_LEVEL)
        ]
        # Only add a second file handler if default logging level is different than specified.
        # Example: Default is logging.INFO, specified is logging.DEBUG
        if specified_file_log_level != DEFAULT_LOG_LEVEL:
            SimpleLoggingSetup._create_file_handler(log_file_path_for_specified_level, specified_file_log_level)
            log_file_paths[specified_file_log_level] = log_file_path_for_specified_level

        for h in handlers:
            h.setFormatter(formatter)

        project_main_logger = SimpleLoggingSetup._setup_project_main_logger(logger_name_prefix, handlers)
        SimpleLoggingSetup.setup_existing_loggers(logger_name_prefix, specified_file_log_level, project_main_logger, handlers,
                                                  modify_pythoncommons_logger_names=modify_pythoncommons_logger_names,
                                                  remove_existing_handlers=remove_existing_handlers)
        config = SimpleLoggingSetupConfig(project_name=project_name,
                                          execution_mode=execution_mode,
                                          file_log_level_name=specified_file_log_level_name,
                                          console_log_level_name=logging.getLevelName(console_log_level),
                                          formatter=final_format_str,
                                          console_handler=console_handler,
                                          file_handlers=list(
                                              filter(lambda h: isinstance(h, logging.FileHandler), handlers)),
                                          main_project_logger=project_main_logger,
                                          log_file_paths=log_file_paths)
        return config

    @staticmethod
    def _determine_log_file_path(file_log_level_name, file_postfix, exec_mode, project_name):
        if exec_mode == ExecutionMode.PRODUCTION:
            log_file_path = ProjectUtils.get_default_log_file(project_name, postfix=file_postfix,
                                                              level_name=file_log_level_name)
        elif exec_mode == ExecutionMode.TEST:
            log_file_path = ProjectUtils.get_default_test_log_file(project_name, postfix=file_postfix,
                                                                   level_name=file_log_level_name)
        else:
            raise ValueError(f"Unknown execution mode: {exec_mode}")
        # else:
        #     final_log_dir = os.path.join(os.path.curdir, 'logs')
        #     final_log_file_path = SimpleLoggingSetup.get_default_log_file_path(file_log_level_name, final_log_dir,
        #                                                                        project_name)
        return log_file_path

    @staticmethod
    def get_default_log_file_path(level_str, log_dir, project_name):
        FileUtils.ensure_dir_created(log_dir)
        # Example file name: <project>-info-2020_03_12_01_19_48
        timestamp = _get_timestamp_as_str()
        logfilename = project_name
        if level_str:
            logfilename += "-" + level_str
        logfilename += "-" + timestamp + ".log"
        log_file = os.path.join(log_dir, logfilename)
        return log_file

    @staticmethod
    def _create_console_handler(level):
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(level)
        return ch

    @staticmethod
    def _create_file_handler(log_file_path, level: int):
        fh = TimedRotatingFileHandler(log_file_path, when='midnight')
        fh.suffix = '%Y_%m_%d.log'
        fh.setLevel(level)
        return fh

    @staticmethod
    def _setup_project_main_logger(logger_name_prefix, handlers):
        logger = logging.getLogger(logger_name_prefix)
        logger.propagate = False
        SimpleLoggingSetup._set_level_and_add_handlers(logger, handlers, logging.DEBUG)
        return logger

    @staticmethod
    def setup_existing_loggers(logger_name_prefix: str,
                               level: int,
                               project_main_logger: logging.Logger,
                               handlers: List[logging.Handler],
                               modify_pythoncommons_logger_names: bool = True,
                               remove_existing_handlers: bool = True):
        level_name: str = logging.getLevelName(level)
        logger_names, loggers = SimpleLoggingSetup.get_all_loggers_from_loggerdict(project_main_logger)
        project_specific_loggers = SimpleLoggingSetup.get_project_specific_loggers(loggers, logger_name_prefix)
        if not project_specific_loggers:
            print("Cannot find any project specific loggers with project name '%s', found loggers: %s", logger_name_prefix, logger_names)
        else:
            project_main_logger.info("Setting logging level to '%s' on the following project-specific loggers: %s.", level_name,
                        logger_names)
            SimpleLoggingSetup._set_level_and_add_handlers_on_loggers(project_main_logger, project_specific_loggers, handlers, level, logger_names,
                                                                      remove_existing_handlers=remove_existing_handlers)

        if modify_pythoncommons_logger_names:
            pythoncommons_loggers = SimpleLoggingSetup.get_pythoncommons_loggers(loggers)
            SimpleLoggingSetup._set_level_and_add_handlers_on_loggers(project_main_logger, pythoncommons_loggers, handlers, level, logger_names)

    @staticmethod
    def get_all_loggers_from_loggerdict(logger=None):
        loggers: List[logging.Logger] = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        logger_names: List[str] = list(map(lambda x: x.name, loggers))
        if logger:
            logger.info("Discovered loggers: %s", logger_names)
        return logger_names, loggers

    @staticmethod
    def get_project_specific_loggers(loggers, logger_name_prefix):
        project_specific_loggers: List[logging.Logger] = list(
            filter(lambda x: x.name.startswith(logger_name_prefix + "."), loggers))
        return project_specific_loggers

    @staticmethod
    def get_pythoncommons_loggers(loggers):
        pythoncommons_loggers = list(filter(lambda x: x.name.startswith(PYTHONCOMMONS_PROJECT_NAME + "."), loggers))
        return pythoncommons_loggers

    @staticmethod
    def _set_level_and_add_handlers_on_loggers(project_main_logger: logging.Logger,
                                               loggers: List[logging.Logger],
                                               handlers: List[logging.Handler],
                                               level: int,
                                               logger_names: List[str],
                                               remove_existing_handlers: bool = True):
        level_name = logging.getLevelName(level)
        for logger in loggers:
            SimpleLoggingSetup._set_level_and_add_handlers(logger, handlers, level, remove_existing_handlers=remove_existing_handlers)
        project_main_logger.info("Set level to '%s' on these discovered loggers: %s", level_name, logger_names)

    @staticmethod
    def _set_level_and_add_handlers(logger: logging.Logger,
                                    handlers: List[logging.Handler],
                                    level: int,
                                    remove_existing_handlers: bool = True):
        if remove_existing_handlers:
            existing_handlers = logger.handlers
            logger.debug("Removing existing handlers from logger: %s, handlers: %s", logger, existing_handlers)
            for h in existing_handlers:
                logger.removeHandler(h)

        logger.debug("Setting log level to '%s' on logger '%s'", logging.getLevelName(level), logger)
        logger.setLevel(level)
        for h in handlers:
            logger.debug("Adding handler '%s' to logger '%s'", h, logger)
            logger.addHandler(h)

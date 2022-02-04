import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
import logging.config
from typing import List, Dict, Callable

from _pytest.logging import _LiveLoggingStreamHandler
from _pytest.terminal import TerminalReporter
from pythoncommons.constants import PROJECT_NAME as PYTHONCOMMONS_PROJECT_NAME, ExecutionMode
from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils
from pythoncommons.project_utils import ProjectUtils
from pythoncommons.test_utils import PyTestUtils

DEFAULT_CONSOLE_STREAM = sys.stdout
DEFAULT_LOG_YAML_FILENAME = "logging_default.yaml"
DEFAULT_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


def _get_timestamp_as_str():
    return DateUtils.now_formatted("%Y_%m_%d_%H_%M_%S")


def get_project_logger(project_name, module_name, postfix=None):
    if postfix:
        if postfix.startswith("."):
            postfix = postfix[1:]
        return logging.getLogger("{}.{}.{}".format(project_name, module_name, postfix))
    return logging.getLogger("{}.{}".format(project_name, module_name))


def get_root_logger():
    return logging.getLogger("")


class HandlerType(Enum):
    FILE = "file"
    CONSOLE = "console"


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


@dataclass
class SimpleLoggingSetupInputConfig:
    project_name: str
    logger_name_prefix: str
    debug: bool = False
    console_debug: bool = False
    format_str: str = None
    file_postfix: str = None
    execution_mode: ExecutionMode = ExecutionMode.PRODUCTION
    modify_pythoncommons_logger_names: bool = True
    remove_existing_handlers: bool = True
    disable_propagation: bool = True
    enable_logging_setup_debug_details: bool = False

    # Dynamic fields
    specified_file_log_level: int or None = None
    handlers: List[logging.Handler] = field(default_factory=list)
    project_main_logger: logging.Logger or None = None


# TODO this is copied from another project, eliminate duplication later
class SimpleLoggingSetup:
    _ALL_LOG_FILES = []

    @staticmethod
    def init_logger(
        project_name: str,
        logger_name_prefix: str,
        execution_mode: ExecutionMode,
        console_debug=False,
        postfix: str = None,
        repos=None,
        verbose_git_log=False,
        format_str=None,
        sanity_check_number_of_handlers=True,
        enable_logging_setup_debug_details: bool = False,
    ) -> SimpleLoggingSetupConfig:
        if not project_name:
            raise ValueError("Project name must be specified!")
        if not logger_name_prefix:
            raise ValueError("Logger name prefix must be specified!")

        final_format_str = DEFAULT_FORMAT
        if format_str:
            final_format_str = format_str
        logging_config: SimpleLoggingSetupConfig = SimpleLoggingSetup.init_logging(
            project_name=project_name,
            logger_name_prefix=logger_name_prefix,
            debug=True,
            console_debug=console_debug,
            format_str=final_format_str,
            file_postfix=postfix,
            execution_mode=execution_mode,
            sanity_check_number_of_handlers=sanity_check_number_of_handlers,
            enable_logging_setup_debug_details=enable_logging_setup_debug_details,
        )
        SimpleLoggingSetup._setup_gitpython_log(repos, verbose_git_log)
        return logging_config

    @staticmethod
    def _setup_gitpython_log(repos, verbose_git_log):
        # https://gitpython.readthedocs.io/en/stable/tutorial.html#git-command-debugging-and-customization
        # THIS WON'T WORK BECAUSE GITPYTHON MODULE IS LOADED BEFORE THIS CALL
        # os.environ["GIT_PYTHON_TRACE"] = "1"
        # https://github.com/gitpython-developers/GitPython/issues/222#issuecomment-68597780
        logging.getLogger().warning("Cannot enable GIT_PYTHON_TRACE because repos list is empty!")
        if repos:
            for repo in repos:
                val = "full" if verbose_git_log else "1"
                type(repo.git).GIT_PYTHON_TRACE = val

    @staticmethod
    def init_logging(
        project_name: str,
        logger_name_prefix: str,
        debug: bool = False,
        console_debug: bool = False,
        format_str: str = None,
        file_postfix: str = None,
        execution_mode: ExecutionMode = ExecutionMode.PRODUCTION,
        modify_pythoncommons_logger_names: bool = True,
        remove_existing_handlers: bool = True,
        sanity_check_number_of_handlers: bool = True,
        disable_propagation: bool = True,
        enable_logging_setup_debug_details: bool = False,
    ) -> SimpleLoggingSetupConfig:
        conf = SimpleLoggingSetupInputConfig(
            project_name,
            logger_name_prefix,
            debug,
            console_debug,
            format_str,
            file_postfix,
            execution_mode,
            modify_pythoncommons_logger_names,
            remove_existing_handlers,
            disable_propagation,
            enable_logging_setup_debug_details,
        )
        conf.specified_file_log_level = logging.DEBUG if debug else DEFAULT_LOG_LEVEL
        specified_file_log_level_name: str = logging.getLevelName(conf.specified_file_log_level)
        default_file_log_level_name: str = logging.getLevelName(DEFAULT_LOG_LEVEL)
        console_log_level: int = logging.DEBUG if debug else DEFAULT_LOG_LEVEL

        if not console_debug:
            console_log_level = DEFAULT_LOG_LEVEL

        final_format_str, formatter = SimpleLoggingSetup._determine_formatter(format_str)

        # This will init the root logger to the specified level
        logging.basicConfig(format=final_format_str, level=conf.specified_file_log_level)

        log_file_path_for_default_level = SimpleLoggingSetup._determine_log_file_path(
            default_file_log_level_name, file_postfix, execution_mode, project_name
        )
        log_file_path_for_specified_level = SimpleLoggingSetup._determine_log_file_path(
            specified_file_log_level_name, file_postfix, execution_mode, project_name
        )
        console_handler, conf.handlers, log_file_paths = SimpleLoggingSetup._determine_handlers(
            console_log_level,
            log_file_path_for_default_level,
            log_file_path_for_specified_level,
            conf.specified_file_log_level,
            formatter,
        )
        # Add fields to input config
        project_main_logger = SimpleLoggingSetup._setup_project_main_logger(conf)
        loggers: List[logging.Logger] = SimpleLoggingSetup.setup_existing_loggers(conf)

        logger_to_handler_count_dict = {logger.name: len(logger.handlers) for logger in loggers}
        project_main_logger.debug("Number of handlers on existing loggers: %s", logger_to_handler_count_dict)
        if sanity_check_number_of_handlers:
            SimpleLoggingSetup._sanity_check_number_of_handlers(conf, loggers)

        if enable_logging_setup_debug_details:
            logger = project_main_logger
            project_main_logger.info(
                "Resetting log level on logger: %s, as initial logging setup has been completed.", logger
            )
            SimpleLoggingSetup._set_level_on_logger(conf.specified_file_log_level, logger, logger)

        config = SimpleLoggingSetupConfig(
            project_name=project_name,
            execution_mode=execution_mode,
            file_log_level_name=specified_file_log_level_name,
            console_log_level_name=logging.getLevelName(console_log_level),
            formatter=final_format_str,
            console_handler=console_handler,
            file_handlers=list(filter(lambda h: isinstance(h, logging.FileHandler), conf.handlers)),
            main_project_logger=project_main_logger,
            log_file_paths=log_file_paths,
        )
        return config

    @staticmethod
    def _determine_handlers(
        console_log_level,
        log_file_path_for_default_level,
        log_file_path_for_specified_level,
        specified_file_log_level,
        formatter,
    ):
        log_file_paths: Dict[int, str] = {DEFAULT_LOG_LEVEL: log_file_path_for_default_level}
        file_handler = SimpleLoggingSetup._create_file_handler(log_file_path_for_default_level, DEFAULT_LOG_LEVEL)
        console_handler = None
        if PyTestUtils.is_pytest_execution():
            # IMPORTANT!
            # PyTest has its own handlers so a console handler wouldn't log anything.
            # Keep all handlers of PyTest and don't use the simple StreamHandler for the stdout stream.
            # An example list of these handlers:
            # 0 = {_LiveLoggingStreamHandler} <_LiveLoggingStreamHandler (DEBUG)>
            # 1 = {_FileHandler} <_FileHandler /<path>/pytest-logs.txt (DEBUG)>
            # 2 = {LogCaptureHandler} <LogCaptureHandler (DEBUG)>
            # 3 = {LogCaptureHandler} <LogCaptureHandler (DEBUG)>
            # More info here:
            # 1. https://stackoverflow.com/a/51633600/1106893
            # 2. https://docs.pytest.org/en/latest/how-to/logging.html#live-logs
            root_logger_handlers = logging.getLogger().handlers
            for rh in root_logger_handlers:
                if isinstance(rh, _LiveLoggingStreamHandler) and isinstance(rh.stream, TerminalReporter):
                    console_handler = rh
            if not console_handler:
                raise ValueError("Console handler not found among PyTest's handlers: {}".format(root_logger_handlers))
            handlers = [*root_logger_handlers, file_handler]
        else:
            console_handler = SimpleLoggingSetup._create_console_handler(console_log_level)
            handlers = [
                console_handler,
                file_handler,
            ]

        # Only add a second file handler if default logging level is different from specified.
        # Example: Default is logging.INFO, specified is logging.DEBUG
        if specified_file_log_level != DEFAULT_LOG_LEVEL:
            handler = SimpleLoggingSetup._create_file_handler(
                log_file_path_for_specified_level, specified_file_log_level
            )
            handlers.append(handler)
            log_file_paths[specified_file_log_level] = log_file_path_for_specified_level
        SimpleLoggingSetup._ALL_LOG_FILES.extend(log_file_paths.values())

        for h in handlers:
            h.setFormatter(formatter)
        return console_handler, handlers, log_file_paths

    @staticmethod
    def _determine_formatter(format_str):
        final_format_str = DEFAULT_FORMAT
        if format_str:
            final_format_str = format_str
        formatter = logging.Formatter(final_format_str)
        return final_format_str, formatter

    @staticmethod
    def _sanity_check_number_of_handlers(conf, loggers):
        wrong_number_of_handlers: Dict[str, List[logging.Handler]] = {}
        expected_no_of_handlers = len(conf.handlers)
        for logger in loggers:
            logger_name = logger.name
            if logger_name.startswith(PYTHONCOMMONS_PROJECT_NAME) or logger_name.startswith(conf.logger_name_prefix):
                if len(logger.handlers) != expected_no_of_handlers:
                    wrong_number_of_handlers[logger_name] = logger.handlers
        if len(wrong_number_of_handlers) > 0:
            raise ValueError(
                "Unexpected number of handlers on loggers. "
                f"Expected: {expected_no_of_handlers}, "
                f"Expected handlers: {conf.handlers}, "
                f"These loggers are having wrong number of handlers: {wrong_number_of_handlers}"
            )

    @staticmethod
    def _determine_log_file_path(file_log_level_name, file_postfix, exec_mode, project_name):
        if exec_mode == ExecutionMode.PRODUCTION:
            log_file_path = ProjectUtils.get_default_log_file(
                project_name, postfix=file_postfix, level_name=file_log_level_name
            )
        elif exec_mode == ExecutionMode.TEST:
            log_file_path = ProjectUtils.get_default_test_log_file(
                project_name, postfix=file_postfix, level_name=file_log_level_name
            )
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
        ch = logging.StreamHandler(stream=DEFAULT_CONSOLE_STREAM)
        ch.setLevel(level)
        return ch

    @staticmethod
    def _create_file_handler(log_file_path, level: int):
        fh = TimedRotatingFileHandler(log_file_path, when="midnight")
        fh.suffix = "%Y_%m_%d.log"
        fh.setLevel(level)
        return fh

    @staticmethod
    def _setup_project_main_logger(conf: SimpleLoggingSetupInputConfig):
        logger = logging.getLogger(conf.logger_name_prefix)
        logger.propagate = False
        SimpleLoggingSetup._set_level_and_add_handlers(conf, logger)
        return logger

    @staticmethod
    def setup_existing_loggers(conf: SimpleLoggingSetupInputConfig):
        level = conf.specified_file_log_level
        level_name: str = logging.getLevelName(level)
        logger_names, loggers = SimpleLoggingSetup.get_all_loggers_from_loggerdict(conf.project_main_logger)
        project_specific_loggers = SimpleLoggingSetup.get_project_specific_loggers(
            loggers, conf.logger_name_prefix, append_dot=True
        )

        if not project_specific_loggers:
            print(
                "Cannot find any project specific loggers with project name '%s', found loggers: %s",
                conf.logger_name_prefix,
                logger_names,
            )
        else:
            conf.project_main_logger.debug(
                "Setting logging level to '%s' on the following project-specific loggers: %s.", level_name, logger_names
            )
        SimpleLoggingSetup._set_level_and_add_handlers_on_loggers(conf, project_specific_loggers, logger_names)

        # Add handlers for non-project specific loggers as well (Git, GoogleApiWrapper, etc.)
        except_prefixes = [conf.logger_name_prefix]
        if not conf.modify_pythoncommons_logger_names:
            except_prefixes.append(PYTHONCOMMONS_PROJECT_NAME)
        non_project_specific_loggers = SimpleLoggingSetup.get_loggers(loggers, except_prefixes)
        SimpleLoggingSetup._set_level_and_add_handlers_on_loggers(conf, non_project_specific_loggers, logger_names)
        return loggers

    @staticmethod
    def get_all_loggers_from_loggerdict(logger=None):
        loggers: List[logging.Logger] = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        logger_names: List[str] = list(map(lambda x: x.name, loggers))
        if logger:
            logger.debug("Discovered loggers: %s", logger_names)
        return logger_names, loggers

    @staticmethod
    def get_project_specific_loggers(loggers, logger_name_prefix, append_dot=False):
        if append_dot:
            logger_name_prefix = logger_name_prefix + "."
        loggers: List[logging.Logger] = list(filter(lambda x: x.name.startswith(logger_name_prefix), loggers))
        return loggers

    @staticmethod
    def get_loggers(loggers, except_prefixes: List[str], append_dots=False):
        if not except_prefixes:
            return loggers
        if append_dots:
            except_prefixes = list(map(lambda e: e + "." if e[-1] != "." else e, except_prefixes))

        filtered_loggers = []
        for logger in loggers:
            for prefix in except_prefixes:
                if not logger.name.startswith(prefix):
                    filtered_loggers.append(logger)
        return filtered_loggers

    @staticmethod
    def get_pythoncommons_loggers(loggers):
        pythoncommons_loggers = list(filter(lambda x: x.name.startswith(PYTHONCOMMONS_PROJECT_NAME + "."), loggers))
        return pythoncommons_loggers

    @staticmethod
    def _set_level_and_add_handlers_on_loggers(
        conf: SimpleLoggingSetupInputConfig, loggers: List[logging.Logger], logger_names: List[str], recursive=True
    ):
        level = conf.specified_file_log_level
        level_name = logging.getLevelName(level)
        for logger in loggers:
            SimpleLoggingSetup._set_level_and_add_handlers(conf, logger, recursive=recursive)
            if conf.disable_propagation and logger.propagate:
                conf.project_main_logger.debug("Disabling propagate on logger: %s", logger.name)
                logger.propagate = False
        conf.project_main_logger.info("Set level to '%s' on these discovered loggers: %s", level_name, logger_names)

    @staticmethod
    def _set_level_and_add_handlers(conf: SimpleLoggingSetupInputConfig, logger: logging.Logger, recursive=True):
        level = conf.specified_file_log_level
        existing_handlers = logger.handlers
        # has_console_handler = len(list(filter(lambda h: SimpleLoggingSetup._is_console_handler(h), existing_handlers)))
        # has_file_handler = len(list(filter(lambda h: SimpleLoggingSetup._is_file_handler(h), existing_handlers)))
        is_project_main_logger = SimpleLoggingSetup._is_project_main_logger(conf, logger)
        main_logger = conf.project_main_logger
        if is_project_main_logger:
            conf.project_main_logger = logger
            main_logger = conf.project_main_logger
            if not conf.enable_logging_setup_debug_details:
                main_logger.info("Disabling debug logs of initial LoggingSetup. Logger: %s", main_logger)
                main_logger.setLevel(DEFAULT_LOG_LEVEL)

        # If we are in TEST mode and the handler is a FileHandler, don't replace it
        callback = (
            lambda handler: conf.execution_mode == ExecutionMode.TEST
            and not SimpleLoggingSetup._is_file_handler(handler)
        )

        if conf.remove_existing_handlers:
            main_logger.debug("Removing existing handlers from logger: %s, handlers: %s", logger, existing_handlers)

            # Handle project main logger specially
            if is_project_main_logger:
                if PyTestUtils.is_pytest_execution():
                    # Simply remove & add all handlers
                    SimpleLoggingSetup._remove_handlers_from_logger(main_logger, logger, type=None)
                    SimpleLoggingSetup._add_handlers_to_logger(main_logger, logger, conf.handlers)
                else:
                    SimpleLoggingSetup._remove_handlers_from_logger(main_logger, logger, type=HandlerType.CONSOLE)
                    SimpleLoggingSetup._add_handlers_to_logger(
                        main_logger, logger, conf.handlers, type=HandlerType.CONSOLE
                    )
                    SimpleLoggingSetup._remove_handlers_from_logger(main_logger, logger, type=HandlerType.FILE)
                    SimpleLoggingSetup._add_handlers_to_logger(
                        main_logger, logger, conf.handlers, type=HandlerType.FILE
                    )
                return
            else:
                SimpleLoggingSetup._remove_handlers_from_logger(main_logger, logger, callback=callback)

        if not is_project_main_logger or conf.enable_logging_setup_debug_details:
            SimpleLoggingSetup._set_level_on_logger(level, logger, main_logger)
        kwargs = {}
        if conf.remove_existing_handlers and len(logger.handlers) != 0:
            # If we selectively removed handlers with the callback,
            # we also want to selectively add handlers with the same callback
            kwargs["callback"] = callback

        SimpleLoggingSetup._add_handlers_to_logger(main_logger, logger, conf.handlers, **kwargs)
        if logger.parent:
            SimpleLoggingSetup._set_level_and_add_handlers(conf, logger.parent, recursive=recursive)

    @staticmethod
    def _set_level_on_logger(level, logger, project_main_logger):
        project_main_logger.debug("Setting log level to '%s' on logger '%s'", logging.getLevelName(level), logger)
        logger.setLevel(level)

    @staticmethod
    def _set_level_on_handler(level, handler, project_main_logger=None):
        project_main_logger.debug("Setting log level to '%s' on handler '%s'", logging.getLevelName(level), handler)
        handler.setLevel(level)

    @staticmethod
    def _add_handlers_to_logger(
        project_main_logger, logger, handlers, type: HandlerType = None, callback: Callable = None
    ):
        filtered_handlers = SimpleLoggingSetup._filter_handlers_by_type(handlers, type)
        for handler in filtered_handlers:
            if (callback and callback(handler)) or not callback:
                project_main_logger.debug("Adding handler '%s' to logger '%s'", handler, logger)
                logger.addHandler(handler)

    @staticmethod
    def _remove_handlers_from_logger(project_main_logger, logger, type: HandlerType = None, callback: Callable = None):
        existing_handlers = logger.handlers
        filtered_handlers = SimpleLoggingSetup._filter_handlers_by_type(existing_handlers, type)
        for handler in filtered_handlers:
            if (callback and callback(handler)) or not callback:
                project_main_logger.debug("Removing handler '%s' from logger '%s'", handler, logger)
                logger.removeHandler(handler)

    @staticmethod
    def _same_loggers(l1, l2):
        return l1.name == l2.name

    @staticmethod
    def _is_project_main_logger(conf, logger):
        return logger.name == conf.logger_name_prefix

    @staticmethod
    def _is_console_handler(handler):
        return isinstance(handler, logging.StreamHandler)

    @staticmethod
    def _is_file_handler(handler):
        return isinstance(handler, logging.FileHandler)

    @staticmethod
    def _filter_handlers_by_type(handlers, type: HandlerType = None):
        if not type:
            return handlers
        if type == HandlerType.FILE:
            return list(filter(lambda h: isinstance(h, logging.FileHandler), handlers))
        elif type == HandlerType.CONSOLE:
            return list(
                filter(lambda h: isinstance(h, logging.StreamHandler) and h.stream == DEFAULT_CONSOLE_STREAM, handlers)
            )

    @staticmethod
    def create_command_logger(name: str):
        cmd_logger = logging.getLogger(name)
        cmd_log_handler = logging.StreamHandler(stream=sys.stdout)
        cmd_logger.propagate = False
        cmd_logger.addHandler(cmd_log_handler)
        cmd_log_handler.setFormatter(logging.Formatter("%(message)s"))
        return cmd_logger

    @classmethod
    def get_all_log_files(cls):
        return cls._ALL_LOG_FILES

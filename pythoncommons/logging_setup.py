import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
import logging.config
from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils

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


# TODO this is copied from another project, eliminate duplication later
class SimpleLoggingSetup:

    @staticmethod
    def init_logging(project_name, debug=False, console_debug=False):
        file_log_level = logging.DEBUG if debug else logging.INFO
        console_log_level = logging.DEBUG if debug else logging.INFO
        if not console_debug:
            console_log_level = logging.INFO

        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(format_str)
        logging.basicConfig(format=format_str, level=file_log_level)

        log_dir = os.path.join(os.path.curdir, 'logs')
        handlers = [
            SimpleLoggingSetup._create_console_handler(console_log_level),
            SimpleLoggingSetup._create_file_handler(project_name, log_dir, logging.INFO, level_str="info"),
            SimpleLoggingSetup._create_file_handler(project_name, log_dir, logging.DEBUG, level_str="debug")
        ]

        for h in handlers:
            h.setFormatter(formatter)

        logger = SimpleLoggingSetup._setup_project_main_logger(project_name, handlers)
        SimpleLoggingSetup._set_level_for_existing_loggers(project_name, file_log_level, logger)

    @staticmethod
    def _create_console_handler(level):
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(level)
        return ch

    @staticmethod
    def _create_file_handler(project_name, log_dir, level, level_str=None):
        FileUtils.ensure_dir_created(log_dir)

        # Example file name: <project>-info-2020_03_12_01_19_48
        timestamp = _get_timestamp_as_str()
        logfilename = project_name
        if level_str:
            logfilename += "-" + level_str
        logfilename += "-" + timestamp + ".log"

        log_file = os.path.join(log_dir, logfilename)
        fh = TimedRotatingFileHandler(log_file, when='midnight')
        fh.suffix = '%Y_%m_%d.log'
        fh.setLevel(level)
        return fh

    @staticmethod
    def _setup_project_main_logger(project_name, handlers):
        logger = logging.getLogger(project_name)
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        for h in handlers:
            logger.addHandler(h)
        return logger

    @staticmethod
    def _set_level_for_existing_loggers(project_name, level, logger):
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        logger_names = list(map(lambda x: x.name, loggers))
        logger.info("Discovered loggers: %s", logger_names)
        project_specific_loggers = list(filter(lambda x: x.name.startswith(project_name + "."), loggers))
        logger.info("Setting logging level to '%s' on the following project-specific loggers: %s.", level, logger_names)
        for logger in project_specific_loggers:
            logger.setLevel(level)

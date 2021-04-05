import logging
import os
from os.path import expanduser
import inspect

from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)
PROJECTS_BASEDIR_NAME = "snemeth-dev-projects"
REPOS_DIR = FileUtils.join_path(expanduser("~"), "development", "my-repos")
PROJECTS_BASEDIR = FileUtils.join_path(expanduser("~"), PROJECTS_BASEDIR_NAME)
LOGS_DIR_NAME = "logs"
TEST_OUTPUT_DIR_NAME = "test"
TEST_LOG_FILE_POSTFIX = "TEST"


class ProjectUtils:
    PROJECT_BASEDIR_DICT = {}
    CHILD_DIR_DICT = {}
    CHILD_DIR_TEST_DICT = {}

    @classmethod
    def get_output_basedir(cls, basedir_name: str, ensure_created=True):
        if not basedir_name:
            raise ValueError("Basedir name should be specified!")

        file_of_caller = cls.verify_caller_filename_valid()
        project_name = cls._parse_project_from_caller_filename(file_of_caller)
        proj_basedir = FileUtils.join_path(PROJECTS_BASEDIR, basedir_name)
        if project_name in cls.PROJECT_BASEDIR_DICT:
            old_basedir = cls.PROJECT_BASEDIR_DICT[project_name]
            if old_basedir != proj_basedir:
                raise ValueError("Project is already registered with a different output basedir. Details: \n"
                                 f"Old basedir name: {old_basedir.split(os.sep)[-1]}\n"
                                 f"Project basedir's old full path: {old_basedir}\n"
                                 f"New basedir name would be: {basedir_name}\n"
                                 f"Project basedir's new full path would be: {proj_basedir}\n")
        cls.PROJECT_BASEDIR_DICT[project_name] = proj_basedir

        if ensure_created:
            FileUtils.ensure_dir_created(proj_basedir)
        return proj_basedir

    @classmethod
    def get_test_output_basedir(cls, basedir_name: str):
        file_of_caller = cls.verify_caller_filename_valid()
        project_name = cls._parse_project_from_caller_filename(file_of_caller)
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            # Creating project dir for the first time
            proj_basedir = cls.get_output_basedir(basedir_name)
        else:
            proj_basedir = cls.PROJECT_BASEDIR_DICT[project_name]

        return FileUtils.join_path(proj_basedir, TEST_OUTPUT_DIR_NAME)

    @classmethod
    def get_output_child_dir(cls, dir_name: str, ensure_created=True):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        project_name = cls._validate_project_for_child_dir_creation()

        if project_name in cls.CHILD_DIR_DICT and dir_name in cls.CHILD_DIR_DICT[project_name]:
            stored_dir = cls.CHILD_DIR_DICT[project_name][dir_name]
            LOG.debug(f"Found already stored child dir for project '{project_name}': {stored_dir}")
            return stored_dir

        proj_basedir = cls.PROJECT_BASEDIR_DICT[project_name]
        new_child_dir = FileUtils.join_path(proj_basedir, dir_name)
        if project_name not in cls.CHILD_DIR_DICT:
            cls.CHILD_DIR_DICT[project_name] = {}
        cls.CHILD_DIR_DICT[dir_name] = new_child_dir

        if ensure_created:
            FileUtils.ensure_dir_created(new_child_dir)
        return new_child_dir

    @classmethod
    def get_test_output_child_dir(cls, dir_name: str, ensure_created=True):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        project_name = cls._validate_project_for_child_dir_creation()

        if project_name in cls.CHILD_DIR_TEST_DICT and dir_name in cls.CHILD_DIR_TEST_DICT[project_name]:
            stored_dir = cls.CHILD_DIR_TEST_DICT[project_name][dir_name]
            LOG.debug(f"Found already stored child test dir for project '{project_name}': {stored_dir}")
            return stored_dir

        proj_basedir = cls.PROJECT_BASEDIR_DICT[project_name]
        new_child_dir = FileUtils.join_path(proj_basedir, TEST_OUTPUT_DIR_NAME, dir_name)
        if project_name not in cls.CHILD_DIR_TEST_DICT:
            cls.CHILD_DIR_TEST_DICT[project_name] = {}
        cls.CHILD_DIR_TEST_DICT[dir_name] = new_child_dir

        if ensure_created:
            FileUtils.ensure_dir_created(new_child_dir)
        return new_child_dir

    @classmethod
    def _validate_project_for_child_dir_creation(cls):
        file_of_caller = cls.verify_caller_filename_valid()
        project_name = cls._parse_project_from_caller_filename(file_of_caller)
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            raise ValueError(f"Project '{project_name}' is unknown. "
                             f"Known projects are: {list(cls.PROJECT_BASEDIR_DICT.keys())}\n"
                             f"Please call {ProjectUtils.__name__}.{ProjectUtils.get_output_basedir.__name__} "
                             f"first in order to set the basedir for the project!")
        return project_name

    @classmethod
    def get_logs_dir(cls):
        return cls.get_output_child_dir(LOGS_DIR_NAME)

    @classmethod
    def get_default_log_file(cls, project_name: str, postfix: str = None):
        if not postfix:
            postfix += "-"

        filename = f"{project_name}-{postfix}{DateUtils.get_current_datetime()}"
        log_dir = cls.get_logs_dir()
        return FileUtils.join_path(log_dir, filename)

    @classmethod
    def get_test_logs_dir(cls):
        return cls.get_test_output_child_dir(LOGS_DIR_NAME)

    @classmethod
    def get_default_test_log_file(cls, project_name: str, postfix: str = None):
        if not postfix:
            postfix = ""
        filename = f"{project_name}-{TEST_LOG_FILE_POSTFIX}-{postfix}-{DateUtils.get_current_datetime()}"
        log_dir = cls.get_test_logs_dir()
        return FileUtils.join_path(log_dir, filename)

    @classmethod
    def verify_caller_filename_valid(cls):
        file_of_caller = inspect.stack()[1].filename
        LOG.debug("Filename of caller: " + file_of_caller)
        if REPOS_DIR not in file_of_caller:
            raise ValueError(
                f"Unexpected project repos directory. The repos '{REPOS_DIR}' is not in caller file path: '{file_of_caller}'")
        return file_of_caller

    @classmethod
    def _parse_project_from_caller_filename(cls, file_of_caller):
        import os
        # Cut repos dir path from the beginning
        file_of_caller = file_of_caller[len(REPOS_DIR):]

        # Cut leading slashes
        if file_of_caller.startswith(os.sep):
            file_of_caller = file_of_caller[1:]

        # We should return the first dir name of the path
        return file_of_caller.split(os.sep)[0]

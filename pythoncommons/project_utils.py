import logging
import os
import sys
from os.path import expanduser
import inspect

from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)
PROJECTS_BASEDIR_NAME = "snemeth-dev-projects"
PROJECTS_BASEDIR = FileUtils.join_path(expanduser("~"), PROJECTS_BASEDIR_NAME)
LOGS_DIR_NAME = "logs"
TEST_OUTPUT_DIR_NAME = "test"
TEST_LOG_FILE_POSTFIX = "TEST"


def determine_project_and_parent_dir(project_name_and_file, stack):
    for path in sys.path:
        if project_name_and_file.startswith(path):
            parts = project_name_and_file.split(path)

            # Cut leading slashes
            if parts[1].startswith(os.sep):
                project_name_and_file = parts[1][1:]
                LOG.info(f"Determined path: {parts[0]}, filename: {project_name_and_file}")
            return path, project_name_and_file

    stack_str = "\n".join([str(f.frame) for f in stack])
    sys_path_str = "\n".join(sys.path)
    raise ValueError(
        f"Unexpected project execution directory. \n"
        f"Filename of caller: '{project_name_and_file}'\n"
        f"Printing diagnostic info including call stack + sys.path...\n"
        f"\nCall stack: \n{stack_str}\n"
        f"\nsys.path: \n{sys_path_str}")


class ProjectUtils:
    PROJECT_BASEDIR_DICT = {}
    CHILD_DIR_DICT = {}
    CHILD_DIR_TEST_DICT = {}

    @classmethod
    def get_output_basedir(cls, basedir_name: str, ensure_created=True):
        if not basedir_name:
            raise ValueError("Basedir name should be specified!")

        project_name = cls.verify_caller_filename_valid()
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
        project_name = cls.verify_caller_filename_valid()
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
            FileUtils.ensure_dir_created(stored_dir)
            return stored_dir

        proj_basedir = cls.PROJECT_BASEDIR_DICT[project_name]
        new_child_dir = FileUtils.join_path(proj_basedir, dir_name)
        if project_name not in cls.CHILD_DIR_DICT:
            cls.CHILD_DIR_DICT[project_name] = {}
        cls.CHILD_DIR_DICT[project_name][dir_name] = new_child_dir

        if ensure_created:
            FileUtils.ensure_dir_created(new_child_dir)
        return new_child_dir

    @classmethod
    def get_test_output_child_dir(cls, dir_name: str, ensure_created=True, special_parent_dir=None):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        project_name = cls._validate_project_for_child_dir_creation()

        if project_name in cls.CHILD_DIR_TEST_DICT and dir_name in cls.CHILD_DIR_TEST_DICT[project_name]:
            stored_dir = cls.CHILD_DIR_TEST_DICT[project_name][dir_name]
            LOG.debug(f"Found already stored child test dir for project '{project_name}': {stored_dir}")
            FileUtils.ensure_dir_created(stored_dir)
            return stored_dir

        if special_parent_dir:
            if not FileUtils.does_path_exist(special_parent_dir):
                raise ValueError(f"Specified parent dir does not exist: {special_parent_dir}")
            LOG.debug(f"Parent dir of new child directory will be: {special_parent_dir}")
            parent_dir = special_parent_dir
            new_child_dir = FileUtils.join_path(parent_dir, dir_name)
        else:
            # Default parent dir: Basedir of project
            # New child dir: basedir/test/<new child dir name>
            parent_dir = cls.PROJECT_BASEDIR_DICT[project_name]
            new_child_dir = FileUtils.join_path(parent_dir, TEST_OUTPUT_DIR_NAME, dir_name)
        if project_name not in cls.CHILD_DIR_TEST_DICT:
            cls.CHILD_DIR_TEST_DICT[project_name] = {}
        cls.CHILD_DIR_TEST_DICT[project_name][dir_name] = new_child_dir

        if ensure_created:
            FileUtils.ensure_dir_created(new_child_dir)
        return new_child_dir

    @classmethod
    def _validate_project_for_child_dir_creation(cls):
        project_name = cls.verify_caller_filename_valid()
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
        if postfix:
            postfix += "-"
        else:
            postfix = ""

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
        stack = inspect.stack()
        stack_frame = cls._find_first_non_pythoncommons_stackframe(stack)
        file_of_caller = stack_frame.filename
        LOG.debug("Filename of caller: " + file_of_caller)
        return determine_project_and_parent_dir(file_of_caller, stack)

    @classmethod
    def _find_first_non_pythoncommons_stackframe(cls, stack):
        idx = 1
        while idx < len(stack):
            fname = stack[idx].filename
            if "pythoncommons" not in fname:
                break
            idx += 1
        if idx == len(stack):
            # Walked up the stack and haven't found any frame that is not pythoncommons
            stack_str = "\n".join([str(f.frame) for f in stack])
            raise ValueError("Walked up the stack but haven't found any frame that does not belong to python-commons. \n"
                             "Printing the stack: \n"
                             f"{stack_str}")
        return stack[idx]

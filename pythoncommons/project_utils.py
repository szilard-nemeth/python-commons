import logging
import os
import sys
from enum import Enum
from os.path import expanduser
import inspect

from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)
PROJECTS_BASEDIR_NAME = "snemeth-dev-projects"
PROJECTS_BASEDIR = FileUtils.join_path(expanduser("~"), PROJECTS_BASEDIR_NAME)
REPOS_DIR = FileUtils.join_path(expanduser("~"), "development", "my-repos")
LOGS_DIR_NAME = "logs"
TEST_OUTPUT_DIR_NAME = "test"
TEST_LOG_FILE_POSTFIX = "TEST"


class ProjectRootDeterminationStrategy(Enum):
    COMMON_FILE = 0
    SYS_PATH = 1


class ProjectUtils:
    PROJECT_BASEDIR_DICT = {}
    CHILD_DIR_DICT = {}
    CHILD_DIR_TEST_DICT = {}
    FILES_TO_PROJECT = {}

    @classmethod
    def determine_project_and_parent_dir(cls, file_of_caller, stack, strategy=ProjectRootDeterminationStrategy.COMMON_FILE):
        received_args = locals()
        received_args['stack'] = ProjectUtils.get_stack_human_readable(stack)
        LOG.debug(f"Determining project name. Received args: {received_args}. \n"
                  f"{cls._get_known_projects_str()}\n")

        if file_of_caller in cls.FILES_TO_PROJECT:
            project = cls.FILES_TO_PROJECT[file_of_caller]
            LOG.debug(f"Found cached project name '{project}', file was already a caller: {file_of_caller}")
            return project

        def _determine_project_by_repos_dir(file_of_caller):
            filename = file_of_caller[len(REPOS_DIR):]
            # We should return the first dir name of the path
            # Cut leading slashes, if any as split would return empty string for 0th component
            if filename.startswith(os.sep):
                filename = filename[1:]
            project = filename.split(os.sep)[0]
            LOG.info(f"Determined path: {REPOS_DIR}, project: {project}")
            return REPOS_DIR, project

        def _determine_project_by_common_files(file_of_caller):
            LOG.debug("Execution environment is not local, "
                      "trying to determine project name with common files strategy. "
                      f"Current sys.path: \n{ProjectUtils.get_sys_path_human_readable()}"
                      f"Current caller file: {file_of_caller}")
            project_root_path = FileUtils.find_repo_root_dir_auto(file_of_caller)
            LOG.debug(f"Found project root: {project_root_path}")
            comps = FileUtils.get_path_components(project_root_path)
            project = comps[-1]
            path = comps[0:-1]
            LOG.info(f"Determined path: {path}, project: {project}")
            return path, project

        def _determine_project_by_sys_path(file_of_caller):
            LOG.debug("Execution environment is not local, "
                      "trying to determine project name with sys.path strategy. "
                      f"Current sys.path: \n{ProjectUtils.get_sys_path_human_readable()}")
            for path in sys.path:
                if file_of_caller.startswith(path):
                    LOG.debug(f"Found parent path of caller file: {path}")
                    parts = file_of_caller.split(path)
                    LOG.debug(f"Parts of path after split: {parts}")
                    # Cut leading slashes
                    if parts[1].startswith(os.sep):
                        project = parts[1][1:]
                    else:
                        project = parts[1]
                    if os.sep in project:
                        project = os.path.split(project)[0]
                    LOG.info(f"Determined path: {path}, project: {project}")
                    return path, project

        def _store_and_return(cls, file_of_caller, path, project):
            cls.FILES_TO_PROJECT[file_of_caller] = project
            return path, project

        if REPOS_DIR in file_of_caller:
            return _store_and_return(cls, file_of_caller, *_determine_project_by_repos_dir(file_of_caller))
        if strategy == ProjectRootDeterminationStrategy.COMMON_FILE:
            return _store_and_return(cls, file_of_caller, *_determine_project_by_common_files(file_of_caller))
        elif strategy == ProjectRootDeterminationStrategy.SYS_PATH:
            return _store_and_return(cls, file_of_caller, *_determine_project_by_sys_path(file_of_caller))

        raise ValueError(
            f"Unexpected project execution directory. \n"
            f"Filename of caller: '{file_of_caller}'\n"
            f"Printing diagnostic info including call stack + sys.path...\n"
            f"\nCall stack: \n{ProjectUtils.get_stack_human_readable(stack)}\n"
            f"\nsys.path: \n{ProjectUtils.get_sys_path_human_readable()}")

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
    def save_to_test_file(cls, dir_name: str, filename: str, file_contents: str):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        if not filename:
            raise ValueError("Filename should be specified!")

        project_name = cls._validate_project_for_child_dir_creation()
        cls.validate_test_child_dir(dir_name, project_name)
        dir_path = cls.CHILD_DIR_TEST_DICT[project_name][dir_name]
        FileUtils.save_to_file(
            FileUtils.join_path(dir_path, filename), file_contents)

    @classmethod
    def validate_test_child_dir(cls, dir_name, project_name):
        if dir_name not in cls.CHILD_DIR_TEST_DICT[project_name]:
            raise ValueError(f"Unknown test child dir with name '{dir_name}' for project '{project_name}'.")

    @classmethod
    def remove_test_files_and_recreate_dir(cls, dir_name: str, clazz):
        project_name = cls._validate_project_for_child_dir_creation()
        cls.validate_test_child_dir(dir_name, project_name)
        dir_path = cls.CHILD_DIR_TEST_DICT[project_name][dir_name]

        LOG.info(f"Removing dir: {dir_path}")
        FileUtils.remove_files(dir_path, ".*")
        LOG.info(f"Recreating dir: {dir_path}")
        new_dir = FileUtils.ensure_dir_created(dir_path)
        LOG.info("Basedir of %s is: %s", clazz.__name__, new_dir)
        return new_dir

    @classmethod
    def _validate_project_for_child_dir_creation(cls):
        project_name = cls.verify_caller_filename_valid()
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            raise ValueError(f"Project '{project_name}' is unknown. "
                             f"{cls._get_known_projects_str()}\n"
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
        path, project = cls.determine_project_and_parent_dir(file_of_caller, stack)
        return project

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
            raise ValueError("Walked up the stack but haven't found any frame that does not belong to python-commons. \n"
                             "Printing the stack: \n"
                             f"{ProjectUtils.get_stack_human_readable(stack)}")
        return stack[idx]

    @classmethod
    def get_stack_human_readable(cls, stack):
        return "\n".join([str(f.frame) for f in stack])

    @staticmethod
    def get_sys_path_human_readable():
        return "\n".join(sys.path)

    @classmethod
    def _get_known_projects_str(cls):
        return f"Known projects are: {list(cls.PROJECT_BASEDIR_DICT.keys())}"

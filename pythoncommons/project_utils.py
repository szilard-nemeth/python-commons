import logging
import os
import platform
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
    test_execution: bool = False

    @classmethod
    def determine_project_and_parent_dir(cls, file_of_caller, stack, strategy=ProjectRootDeterminationStrategy.COMMON_FILE):
        if not strategy:
            strategy = ProjectRootDeterminationStrategy.COMMON_FILE
        received_args = locals().copy()
        received_args['stack'] = ProjectUtils.get_stack_human_readable(stack)
        LOG.debug(f"Determining project name. Received args: {received_args}. \n"
                  f"{cls._get_known_projects_str()}\n")

        if file_of_caller in cls.FILES_TO_PROJECT:
            project = cls.FILES_TO_PROJECT[file_of_caller]
            LOG.debug(f"Found cached project name '{project}', file was already a caller: {file_of_caller}")
            return file_of_caller, project

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
            def _special_startswith(path, file_of_caller, is_mac):
                # Had to make an OS-based distinction here...
                # On MacOS, if the file is executed from /var or /tmp, the stackframe will contain the normal path.
                # However, even if the normal path is added to sys.path from a testcase,
                # it will be prepended with /private.
                # More on /private can be found here: https://apple.stackexchange.com/a/227869

                # Example scenario:
                # path: '/private/var/folders/nn/mkv5bwbd2fg8v8ztz5swpq980000gn/T/tmpp3k75qk2/python'
                # file_of_caller: '/var/folders/nn/mkv5bwbd2fg8v8ztz5swpq980000gn/T/tmpp3k75qk2/python/hello_world.py'
                if is_mac and path.startswith(os.sep + "private"):
                    # WARNING: Cannot use os.path.join here as it removes /private from the path string :(
                    extended_file_of_caller = os.sep + "private" + file_of_caller
                    if extended_file_of_caller.startswith(path):
                        LOG.info(f"Matched with special startswith. "
                                 f"Original file of caller: {file_of_caller}"
                                 f"Extended file of caller: {extended_file_of_caller}"
                                 f"Path: {path}")
                        return True, extended_file_of_caller
                return False, file_of_caller

            LOG.debug("Execution environment is not local, "
                      "trying to determine project name with sys.path strategy. "
                      f"Current sys.path: \n{ProjectUtils.get_sys_path_human_readable()}")

            is_mac = platform.system() == "Darwin"
            for path in sys.path:
                match = file_of_caller.startswith(path)
                if not match:
                    match, new_file_of_caller = _special_startswith(path, file_of_caller, is_mac)
                    if match:
                        file_of_caller = new_file_of_caller
                if match:
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
            raise ValueError(f"Cannot determine project. File of caller: {file_of_caller}\n"
                             f"Call stack: \n{ProjectUtils.get_stack_human_readable(stack)}")

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
    def get_output_basedir(cls, basedir_name: str,
                           ensure_created=True,
                           allow_python_commons_as_project=False,
                           project_root_determination_strategy=None):
        if not basedir_name:
            raise ValueError("Basedir name should be specified!")

        project_name = cls.verify_caller_filename_valid(
            allow_python_commons_as_project=allow_python_commons_as_project,
            project_root_determination_strategy=project_root_determination_strategy)
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
    def get_test_output_basedir(cls, basedir_name: str,
                                allow_python_commons_as_project=False,
                                project_root_determination_strategy=None):
        """

        :param basedir_name:
        :param allow_python_commons_as_project: This is useful and a must for test executions of ProjectUtils (e.g. JiraUtilsTests)
        as stackframes calling pythoncommons are only the methods of the unittest framework.
        :return:
        """
        cls.test_execution = True
        project_name = cls.verify_caller_filename_valid(
            allow_python_commons_as_project=allow_python_commons_as_project,
            project_root_determination_strategy=project_root_determination_strategy)
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            # Creating project dir for the first time
            proj_basedir = cls.get_output_basedir(basedir_name,
                                                  allow_python_commons_as_project=allow_python_commons_as_project,
                                                  project_root_determination_strategy=project_root_determination_strategy)
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
    def get_session_dir_under_child_dir(cls, child_dir_name: str):
        # If this method called from production code but we are exeucting it from test code
        if cls.test_execution:
            return cls._get_session_dir_under_child_dir(child_dir_name, test=True)
        return cls._get_session_dir_under_child_dir(child_dir_name)

    @classmethod
    def get_test_session_dir_under_child_dir(cls, child_dir_name: str):
        return cls._get_session_dir_under_child_dir(child_dir_name, test=True)

    @classmethod
    def _get_session_dir_under_child_dir(cls, child_dir_name, test: bool = False):
        child_dir_type: str = "child dir" if not test else "test child dir"
        dir_dict = cls.CHILD_DIR_DICT if not test else cls.CHILD_DIR_TEST_DICT

        if not child_dir_name:
            raise ValueError(f"Project {child_dir_type} name should be specified!")

        project_name = cls._validate_project_for_child_dir_creation()
        if project_name in dir_dict and child_dir_name in dir_dict[project_name]:
            stored_dir = dir_dict[project_name][child_dir_name]
            LOG.debug(f"Found already stored {child_dir_type} for project '{project_name}': {stored_dir}")

            session_dir = FileUtils.join_path(stored_dir, f"session-{DateUtils.now_formatted('%Y%m%d_%H%M%S')}")
            FileUtils.ensure_dir_created(session_dir)
            return session_dir
        else:
            raise ValueError(f"Cannot find stored {child_dir_type} for project. "
                             f"Project: {project_name}, "
                             f"Child dir: {child_dir_name}, "
                             f"All stored {child_dir_type}s: {dir_dict}")

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
    def verify_caller_filename_valid(cls, allow_python_commons_as_project=False,
                                     project_root_determination_strategy=None):
        stack = inspect.stack()
        stack_frame, idx = cls._find_first_non_pythoncommons_stackframe(stack)
        file_of_caller = stack_frame.filename
        LOG.debug("Filename of caller: " + file_of_caller)
        if "unittest" in file_of_caller.split(os.sep):
            message = f"Detected caller as 'unittest'. Current stack frame: {stack_frame}\n" \
                     f"Stack: {ProjectUtils.get_stack_human_readable(stack)}"
            if allow_python_commons_as_project:
                LOG.warning(message)
                # Get the previous frame which should belong to pythoncommons
                python_commons_frame = stack[idx - 1]
                file_of_caller = python_commons_frame.filename
            else:
                message += "\n'allow_python_commons_as_project' is set to False. " \
                               "Please set 'allow_python_commons_as_project' to True " \
                               "to the ProjectUtils method that initiated the call."
                raise ValueError(message)
        path, project = cls.determine_project_and_parent_dir(file_of_caller, stack, strategy=project_root_determination_strategy)
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
        return stack[idx], idx

    @classmethod
    def get_stack_human_readable(cls, stack):
        return "\n".join([str(f.frame) for f in stack])

    @staticmethod
    def get_sys_path_human_readable():
        return "\n".join(sys.path)

    @classmethod
    def _get_known_projects_str(cls):
        return f"Known projects are: {list(cls.PROJECT_BASEDIR_DICT.keys())}"

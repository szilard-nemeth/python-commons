import logging
import os
import platform
import sys
from abc import ABC, abstractmethod
from enum import Enum
from os.path import expanduser
import inspect
from typing import Dict, List

from pythoncommons.constants import PROJECT_NAME
from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import FileUtils, FindResultType
from pythoncommons.os_utils import OsUtils
from pythoncommons.string_utils import StringUtils

LOG = logging.getLogger(__name__)


class ProjectUtilsEnvVar(Enum):
    OVERRIDE_USER_HOME_DIR = "OVERRIDE_USER_HOME_DIR"
    PROJECT_DETERMINATION_STRATEGY = "PYTHONCOMMONS_PROJECTUTILS_PROJECT_DETERMINATION_STRATEGY"


def determine_project_basedir():
    user_home = expanduser("~")
    override_user_home = OsUtils.get_env_value(ProjectUtilsEnvVar.OVERRIDE_USER_HOME_DIR.value)
    if override_user_home:
        LOG.info("Overriding user home dir with: %s", override_user_home)
        user_home = override_user_home
    return FileUtils.join_path(user_home, PROJECTS_BASEDIR_NAME)


MAC_PRIVATE_DIR = "private"
PROJECTS_BASEDIR_NAME = "snemeth-dev-projects"
PROJECTS_BASEDIR = determine_project_basedir()
REPOS_DIR = FileUtils.join_path(expanduser("~"), "development", "my-repos")
LOGS_DIR_NAME = "logs"
TEST_OUTPUT_DIR_NAME = "test"
TEST_LOG_FILE_POSTFIX = "TEST"
SITE_PACKAGES_DIRNAME = "site-packages"


class ProjectRootDeterminationStrategy(Enum):
    COMMON_FILE = "common_file"
    SYS_PATH = "sys_path"
    REPOSITORY_DIR = "repository_dir"


def get_sys_path_human_readable():
    return "\n".join(sys.path)


def get_stack_human_readable(stack):
    return "\n".join([str(f.frame) for f in stack])


class SimpleProjectUtils:
    @classmethod
    def get_project_dir(
        cls,
        basedir: str,
        parent_dir: str,
        dir_to_find: str,
        find_result_type: FindResultType,
        exclude_dirs: List[str] = None,
    ):
        found_dirs = FileUtils.find_files(
            basedir,
            find_type=find_result_type,
            regex=dir_to_find,
            parent_dir=parent_dir,
            exclude_dirs=exclude_dirs,
            single_level=False,
            full_path_result=True,
        )
        if len(found_dirs) != 1:
            raise ValueError(
                f"Expected to find 1 dir with name {dir_to_find} "
                f"and parent dir '{parent_dir}'. "
                f"Actual results: {found_dirs}"
            )
        return found_dirs[0]

    @classmethod
    def get_project_file(
        cls,
        basedir: str,
        file_to_find: str,
        find_result_type: FindResultType,
    ):
        found_files = FileUtils.find_files(
            basedir,
            find_type=find_result_type,
            regex=file_to_find,
            single_level=False,
            full_path_result=True,
        )
        if len(found_files) != 1:
            raise ValueError(f"Expected to find 1 file with name {file_to_find}." f"Actual results: {found_files}")
        return found_files[0]


class StrategyBase(ABC):
    @abstractmethod
    def determine_path(self, caller_file, stack, project_name_hint=None):
        pass

    def find_common_paths(self, path, file_of_caller):
        # Remove potential multiple slashes to check against the same path, see: https://stackoverflow.com/a/64459248/1106893
        file_of_caller = os.path.abspath(file_of_caller)
        found_match: bool = file_of_caller.startswith(path)
        if found_match:
            return path, file_of_caller

        found_match, new_file_of_caller = self.mac_specific_path_startswith(path, file_of_caller)
        LOG.debug("File of caller: '%s', path: '%s', found match: %s", file_of_caller, path, found_match)
        if found_match:
            return path, new_file_of_caller

        return None, file_of_caller

    @staticmethod
    def mac_specific_path_startswith(path, file_of_caller):
        # Remove potential multiple slashes to check against the same path, see: https://stackoverflow.com/a/64459248/1106893
        file_of_caller = os.path.abspath(file_of_caller)

        # Had to make an OS-based distinction here...
        # On MacOS, if the file is executed from /var or /tmp, the stackframe will contain the normal path.
        # However, even if the normal path is added to sys.path from a testcase,
        # it will be prepended with /private.
        # More on /private can be found here: https://apple.stackexchange.com/a/227869

        # Example scenario:
        # path: '/private/var/folders/nn/mkv5bwbd2fg8v8ztz5swpq980000gn/T/tmpp3k75qk2/python'
        # file_of_caller: '/var/folders/nn/mkv5bwbd2fg8v8ztz5swpq980000gn/T/tmpp3k75qk2/python/hello_world.py'
        is_mac = platform.system() == "Darwin"
        LOG.debug("Trying to match file '%s' with path '%s' with Mac-specific startswith.", file_of_caller, path)
        if is_mac and StringUtils.is_path_starting_with_dirname(path, MAC_PRIVATE_DIR):
            # WARNING: Cannot use os.path.join, neither StringUtils.prepend_path here as it removes /private from the path string :(
            # extended_file_of_caller = StringUtils.prepend_path(file_of_caller, MAC_PRIVATE_DIR)
            extended_file_of_caller = os.sep + MAC_PRIVATE_DIR + file_of_caller
            LOG.debug(
                f"Original file of caller: {file_of_caller}"
                f"\nExtended file of caller: {extended_file_of_caller}"
                f"\nPath: {path}"
            )
            if extended_file_of_caller.startswith(path):
                return True, extended_file_of_caller
        return False, file_of_caller

    LOG.debug(
        "Execution environment is not local, "
        "trying to determine project name with sys.path strategy. "
        f"Current sys.path: \n{get_sys_path_human_readable()}"
    )


class CommonPathStrategy(StrategyBase):
    def determine_path(self, file_of_caller, stack, project_name_hint=None):
        LOG.debug(
            "Execution environment is not local, "
            "trying to determine project name with common files strategy. "
            f"Current sys.path: \n{get_sys_path_human_readable()}"
            f"Current caller file: {file_of_caller}"
        )
        project_root_path, visited_paths = FileUtils.find_repo_root_dir_auto(file_of_caller, raise_error=False)
        if project_root_path == os.sep:
            orig_path = os.path.realpath(file_of_caller)
            err_message = (
                f"Failed to find project root directory starting from path '{orig_path}'. "
                f"Visited: {visited_paths}\n"
                f"Strategy: {type(self).__name__}\n"
                f"Caller file: {file_of_caller}"
            )
            if project_name_hint:
                LOG.error(err_message + " Returning project name from hint: " + project_name_hint)
                return file_of_caller, project_name_hint
            else:
                raise ValueError(err_message)

        LOG.debug(f"Found project root: {project_root_path}")
        comps = FileUtils.get_path_components(project_root_path)
        project = comps[-1]
        path = comps[0:-1]
        LOG.info(f"Determined path: {path}, project: {project}")
        return path, project


class RepositoryDirStrategy(StrategyBase):
    def determine_path(self, file_of_caller, stack, project_name_hint=None):
        LOG.debug(
            "Trying to determine project name with repository dir strategy. "
            f"Current sys.path: \n{get_sys_path_human_readable()}"
        )
        filename = file_of_caller[len(REPOS_DIR) :]
        # We should return the first dir name of the path
        # Cut leading slashes, if any as split would return empty string for 0th component
        filename = StringUtils.strip_leading_os_sep(filename)
        project = StringUtils.get_first_dir_of_path(filename)
        LOG.info(f"Determined path: {REPOS_DIR}, project: {project}")
        return REPOS_DIR, project


class SysPathStrategy(StrategyBase):
    def determine_path(self, file_of_caller, stack, project_name_hint=None):
        for path in sys.path:
            LOG.debug("Checking path: '%s' against file_of_caller: '%s'", path, file_of_caller)
            if ProjectUtils.FORCE_SITE_PACKAGES_IN_PATH_NAME and SITE_PACKAGES_DIRNAME not in path:
                LOG.debug("Skipping path: '%s', as '%s' not found in the path", path, SITE_PACKAGES_DIRNAME)
                continue
            matched_base_path, file_of_caller = self.find_common_paths(path, file_of_caller)
            if not matched_base_path:
                continue

            LOG.debug("Found Base path: %s for file of caller: %s", matched_base_path, file_of_caller)
            matched_base_path = StringUtils.strip_trailing_os_sep(matched_base_path)
            if ProjectUtils.FORCE_SITE_PACKAGES_IN_PATH_NAME and not matched_base_path.endswith(SITE_PACKAGES_DIRNAME):
                LOG.debug(
                    "Matched base path does not end with '%s'. Dropping path components after it.",
                    SITE_PACKAGES_DIRNAME,
                )
                # Need to cut the last dir from the path, so we find the site-packages root
                # Example: /<somepath>/venv/lib/python3.8/site-packages/test_project
                matched_base_path = StringUtils.remove_last_dir_from_path(matched_base_path)
                LOG.debug("Final base path: %s", matched_base_path)

            parts = file_of_caller.split(matched_base_path)
            LOG.debug(f"Parts of path after split: {parts}")

            # Example #1: ['', '/test_project.py'] --> Need to get item with index 1
            # Cut leading slashes
            proj_name = parts[1]
            proj_name = StringUtils.strip_leading_os_sep(proj_name)

            # Example #2: ['', '/testproject/commands/testcommand/dummy_test_command.py']
            if StringUtils.is_path_multi_component(proj_name):
                LOG.debug(
                    "Found multiple dirs in project name: %s. " "Assuming first dir is the name of the project.",
                    proj_name,
                )
                proj_name = StringUtils.get_first_dir_of_path_if_multi_component(proj_name)
            LOG.info(f"Determined path: {matched_base_path}, project: {proj_name}")
            return matched_base_path, proj_name

        err_message = (
            f"Cannot determine project! "
            f"File of caller: {file_of_caller}\n"
            f"Call stack: \n{get_stack_human_readable(stack)}"
            f"Strategy: {type(self).__name__}"
        )
        if project_name_hint:
            LOG.error(err_message + " Returning project name from hint: " + project_name_hint)
            return file_of_caller, project_name_hint
        else:
            raise ValueError(err_message)


class ProjectUtils:
    PROJECT_BASEDIR_DICT = {}
    CHILD_DIR_DICT = {}
    CHILD_DIR_TEST_DICT = {}
    FILES_TO_PROJECT = {}
    FORBIDDEN_DIR_NAMES = ["unittest", "pytest", "_pytest"]
    test_execution: bool = False
    project_root_determine_strategy_set_manually: bool = False
    default_project_determine_strategy = ProjectRootDeterminationStrategy.COMMON_FILE
    project_root_determine_strategy = default_project_determine_strategy
    FORCE_SITE_PACKAGES_IN_PATH_NAME = True
    STRATEGIES: Dict[ProjectRootDeterminationStrategy, StrategyBase] = {
        ProjectRootDeterminationStrategy.COMMON_FILE: CommonPathStrategy(),
        ProjectRootDeterminationStrategy.SYS_PATH: SysPathStrategy(),
        ProjectRootDeterminationStrategy.REPOSITORY_DIR: RepositoryDirStrategy(),
    }

    @classmethod
    def reset_root_determine_strategy_to_default(cls):
        cls.project_root_determine_strategy_set_manually = False
        cls.project_root_determine_strategy = cls.default_project_determine_strategy

    @classmethod
    def set_root_determine_strategy(cls, strategy: ProjectRootDeterminationStrategy, allow_overwrite=True):
        old_strategy = cls.project_root_determine_strategy
        LOG.info("Discovered project root determine strategy: %s", old_strategy)
        if not cls.project_root_determine_strategy_set_manually or allow_overwrite:
            LOG.info(
                "Overwriting project root determine strategy! Old value: %s, New value: %s", old_strategy, strategy
            )
            cls.project_root_determine_strategy = strategy
            cls.project_root_determine_strategy_set_manually = True

    @classmethod
    def determine_project_and_parent_dir(cls, file_of_caller, stack, project_name_hint=None):
        received_args = locals().copy()
        received_args["stack"] = get_stack_human_readable(stack)
        LOG.debug(
            f"Determining project name with strategy '{cls.project_root_determine_strategy}'. "
            f"Received args: {received_args}. \n"
            f"{cls._get_known_projects_str()}\n"
        )

        if file_of_caller in cls.FILES_TO_PROJECT:
            project = cls.FILES_TO_PROJECT[file_of_caller]
            LOG.debug(f"Found cached project name '{project}', file was already a caller: {file_of_caller}")
            return file_of_caller, project

        strategy: StrategyBase = cls._determine_strategy(file_of_caller)
        path, project = strategy.determine_path(file_of_caller, stack, project_name_hint=project_name_hint)
        cls.FILES_TO_PROJECT[file_of_caller] = project
        return path, project

        # TODO Can this happen?
        # raise ValueError(
        #     f"Unexpected project execution directory. \n"
        #     f"Filename of caller: '{file_of_caller}'\n"
        #     f"Printing diagnostic info including call stack + sys.path...\n"
        #     f"\nCall stack: \n{get_stack_human_readable(stack)}\n"
        #     f"\nsys.path: \n{get_sys_path_human_readable()}")

    @classmethod
    def _determine_strategy(cls, file_of_caller) -> StrategyBase:
        strategy_env_var = OsUtils.get_env_value(ProjectUtilsEnvVar.PROJECT_DETERMINATION_STRATEGY.value)
        if strategy_env_var:
            strat = ProjectRootDeterminationStrategy[strategy_env_var.upper()]
            LOG.info("Using strategy '%s' based on env var", strat)
            return cls.STRATEGIES[strat]
        strategy: StrategyBase = cls.STRATEGIES[cls.project_root_determine_strategy]
        if (
            REPOS_DIR in file_of_caller
            and cls.project_root_determine_strategy == cls.default_project_determine_strategy
        ):
            strategy = cls.STRATEGIES[ProjectRootDeterminationStrategy.REPOSITORY_DIR]
        return strategy

    @classmethod
    def get_output_basedir(
        cls,
        basedir_name: str,
        ensure_created=True,
        allow_python_commons_as_project=False,
        basedir=PROJECTS_BASEDIR,
        project_name_hint=None,
    ):
        if not basedir_name:
            raise ValueError("Basedir name should be specified!")

        project_name = cls.verify_caller_filename_valid(
            allow_python_commons_as_project=allow_python_commons_as_project, project_name_hint=project_name_hint
        )
        proj_basedir = FileUtils.join_path(basedir, basedir_name)
        if project_name in cls.PROJECT_BASEDIR_DICT:
            old_basedir = cls.PROJECT_BASEDIR_DICT[project_name]
            if old_basedir != proj_basedir:
                raise ValueError(
                    "Project is already registered with a different output basedir. Details: \n"
                    f"Old basedir name: {StringUtils.get_last_dir_of_path(old_basedir)}\n"
                    f"Project basedir's old full path: {old_basedir}\n"
                    f"New basedir name would be: {basedir_name}\n"
                    f"Project basedir's new full path would be: {proj_basedir}\n"
                )
        cls.PROJECT_BASEDIR_DICT[project_name] = proj_basedir

        if ensure_created:
            FileUtils.ensure_dir_created(proj_basedir)
        return proj_basedir

    @classmethod
    def get_test_output_basedir(cls, basedir_name: str, allow_python_commons_as_project=False):
        """

        :param basedir_name:
        :param allow_python_commons_as_project: This is useful and a must for test executions of ProjectUtils (e.g. JiraUtilsTests)
        as stackframes calling pythoncommons are only the methods of the unittest framework.
        :return:
        """
        cls.test_execution = True
        project_name = cls.verify_caller_filename_valid(allow_python_commons_as_project=allow_python_commons_as_project)
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            # Creating project dir for the first time
            proj_basedir = cls.get_output_basedir(
                basedir_name, allow_python_commons_as_project=allow_python_commons_as_project
            )
        else:
            proj_basedir = cls.PROJECT_BASEDIR_DICT[project_name]

        return FileUtils.join_path(proj_basedir, TEST_OUTPUT_DIR_NAME)

    @classmethod
    def get_output_child_dir(cls, dir_name: str, ensure_created=True, project_name_hint=None):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        project_name = cls._validate_project_for_child_dir_creation(project_name_hint=project_name_hint)

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
    def get_test_output_child_dir(
        cls, dir_name: str, ensure_created=True, special_parent_dir=None, project_name_hint=None
    ):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        project_name = cls._validate_project_for_child_dir_creation(project_name_hint=project_name_hint)

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
            raise ValueError(
                f"Cannot find stored {child_dir_type} for project. "
                f"Project: {project_name}, "
                f"Child dir: {child_dir_name}, "
                f"All stored {child_dir_type}s: {dir_dict}"
            )

    @classmethod
    def save_to_test_file(cls, dir_name: str, filename: str, file_contents: str):
        if not dir_name:
            raise ValueError("Dir name should be specified!")
        if not filename:
            raise ValueError("Filename should be specified!")

        project_name = cls._validate_project_for_child_dir_creation()
        cls.validate_test_child_dir(dir_name, project_name)
        dir_path = cls.CHILD_DIR_TEST_DICT[project_name][dir_name]
        FileUtils.save_to_file(FileUtils.join_path(dir_path, filename), file_contents)

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
    def _validate_project_for_child_dir_creation(cls, project_name_hint=None):
        project_name = cls.verify_caller_filename_valid(project_name_hint=project_name_hint)
        if project_name not in cls.PROJECT_BASEDIR_DICT:
            raise ValueError(
                f"Project '{project_name}' is unknown. "
                f"{cls._get_known_projects_str()}\n"
                f"Please call {ProjectUtils.__name__}.{ProjectUtils.get_output_basedir.__name__} "
                f"first in order to set the basedir for the project!"
            )
        return project_name

    @classmethod
    def get_default_log_file(cls, project_name: str, postfix: str = None, level_name: str = None):
        return cls._get_log_filename_internal(project_name, postfix, level_name=level_name, prod=True)

    @classmethod
    def get_default_test_log_file(cls, project_name: str, postfix: str = None, level_name: str = None):
        return cls._get_log_filename_internal(project_name, postfix, level_name=level_name, prod=False)

    @classmethod
    def _get_log_filename_internal(
        cls, project_name: str, postfix: str = None, level_name: str = None, prod: bool = True
    ):
        if postfix:
            postfix = "-" + postfix
        else:
            postfix = ""
        if not prod:
            postfix += "-" + TEST_LOG_FILE_POSTFIX

        if level_name:
            level_name = "-" + level_name
        else:
            level_name = ""

        filename = f"{project_name}{postfix}{level_name}-{DateUtils.get_current_datetime()}"
        log_dir = (
            cls.get_logs_dir(project_name_hint=project_name)
            if prod
            else cls.get_test_logs_dir(project_name_hint=project_name)
        )
        return FileUtils.join_path(log_dir, filename)

    @classmethod
    def get_logs_dir(cls, project_name_hint=None):
        return cls.get_output_child_dir(LOGS_DIR_NAME, project_name_hint=project_name_hint)

    @classmethod
    def get_test_logs_dir(cls, project_name_hint=None):
        return cls.get_test_output_child_dir(LOGS_DIR_NAME, project_name_hint=project_name_hint)

    @classmethod
    def verify_caller_filename_valid(cls, allow_python_commons_as_project=False, project_name_hint=None):
        stack = inspect.stack()
        stack_frame, idx = cls._find_first_non_pythoncommons_stackframe(stack)
        file_of_caller = stack_frame.filename
        LOG.debug("Filename of caller: " + file_of_caller)
        if StringUtils.is_any_of_dir_names_in_path(file_of_caller, cls.FORBIDDEN_DIR_NAMES):
            message = (
                f"Detected caller as 'unittest'. Current stack frame: {stack_frame}\n"
                f"Stack: {get_stack_human_readable(stack)}"
            )
            if allow_python_commons_as_project:
                LOG.warning(message)
                # Get the previous frame which should belong to pythoncommons
                python_commons_frame = stack[idx - 1]
                file_of_caller = python_commons_frame.filename
            else:
                message += (
                    "\n'allow_python_commons_as_project' is set to False. "
                    "Please set 'allow_python_commons_as_project' to True "
                    "to the ProjectUtils method that initiated the call."
                )
                raise ValueError(message)
        path, project = cls.determine_project_and_parent_dir(file_of_caller, stack, project_name_hint=project_name_hint)
        return project

    @classmethod
    def _find_first_non_pythoncommons_stackframe(cls, stack):
        idx = 1
        while idx < len(stack):
            LOG.debug("Inspecting stack frame: %s", stack[idx])
            fname = stack[idx].filename
            if PROJECT_NAME not in fname:
                break
            idx += 1
        if idx == len(stack):
            # Walked up the stack and haven't found any frame that is not pythoncommons
            raise ValueError(
                "Walked up the stack but haven't found any frame that does not belong to python-commons. \n"
                "Printing the stack: \n"
                f"{get_stack_human_readable(stack)}"
            )
        return stack[idx], idx

    @classmethod
    def _get_known_projects_str(cls):
        return f"Known projects are: {list(cls.PROJECT_BASEDIR_DICT.keys())}"

    @classmethod
    def get_all_project_basedirs(cls):
        return cls.PROJECT_BASEDIR_DICT.values()

    @classmethod
    def get_project_basedirs_dict(cls):
        return cls.PROJECT_BASEDIR_DICT

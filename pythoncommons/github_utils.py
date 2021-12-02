import logging
from enum import Enum

from pythoncommons.os_utils import OsUtils

LOG = logging.getLogger(__name__)


class GithubActionsEnvVar(Enum):
    CI_EXECUTION = "CI"
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    GITHUB_WORKSPACE = "GITHUB_WORKSPACE"


class GitHubUtils:
    @staticmethod
    def is_github_ci_execution() -> bool:
        is_github_ci_exec = OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_ACTIONS.value)
        if is_github_ci_exec:
            LOG.debug("Identified Github Actions CI execution")
            return True
        return False

    @staticmethod
    def get_workspace_path() -> str:
        github_ws_path = OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_WORKSPACE.value)
        if github_ws_path:
            LOG.debug("Identified Github Actions CI workspace path: %s", github_ws_path)
        return github_ws_path

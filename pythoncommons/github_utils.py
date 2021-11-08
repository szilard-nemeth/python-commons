from enum import Enum

from pythoncommons.os_utils import OsUtils


class GithubActionsEnvVar(Enum):
    CI_EXECUTION = "CI"
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    GITHUB_WORKSPACE = "GITHUB_WORKSPACE"

class GitHubUtils:
    @staticmethod
    def is_github_ci_execution() -> bool:
        return True if OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_ACTIONS.value) else False

    @staticmethod
    def get_workspace_path() -> str:
        return OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_WORKSPACE.value)
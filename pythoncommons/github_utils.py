import logging
from enum import Enum

import requests

from pythoncommons.os_utils import OsUtils

LOG = logging.getLogger(__name__)
GITHUB_PULLS_API = "https://api.github.com/repos/apache/hadoop/pulls/$PR_ID"


class GithubPRMergeStatus(Enum):
    MERGEABLE = "Mergeable"
    NOT_MERGEABLE = "Not mergeable"
    UNKNOWN = "Unknown"


class GithubActionsEnvVar(Enum):
    CI_EXECUTION = "CI"
    GITHUB_ACTIONS = "GITHUB_ACTIONS"
    GITHUB_WORKSPACE = "GITHUB_WORKSPACE"


class GitHubUtils:
    @staticmethod
    def is_github_ci_execution() -> bool:
        is_github_ci_exec = OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_ACTIONS.value)
        if is_github_ci_exec:
            LOG.debug("Detected Github Actions CI execution")
            return True
        return False

    @staticmethod
    def get_workspace_path() -> str:
        github_ws_path = OsUtils.get_env_value(GithubActionsEnvVar.GITHUB_WORKSPACE.value)
        if github_ws_path:
            LOG.debug("Detected Github Actions CI workspace path: %s", github_ws_path)
        return github_ws_path

    @staticmethod
    def is_pull_request_mergeable(pr_id: int):
        pr_json = requests.get(GitHubUtils.get_pull_request_url(pr_id)).json()
        if "mergeable" in pr_json:
            if pr_json["mergeable"]:
                return GithubPRMergeStatus.MERGEABLE
            else:
                return GithubPRMergeStatus.NOT_MERGEABLE
        return GithubPRMergeStatus.UNKNOWN

    @staticmethod
    def get_pull_request_url(pr_id: int):
        return GITHUB_PULLS_API.replace("$PR_ID", str(pr_id))

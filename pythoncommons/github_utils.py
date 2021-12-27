import logging
from enum import Enum

import requests

from pythoncommons.os_utils import OsUtils

LOG = logging.getLogger(__name__)
GITHUB_PULLS_API = "https://api.github.com/repos/apache/hadoop/pulls/$PR_ID"
GITHUB_PULLS_LIST_API = "https://api.github.com/repos/apache/hadoop/pulls"


class GithubPRMergeStatus(Enum):
    MERGEABLE = "Mergeable"
    NOT_MERGEABLE = "Not mergeable"
    UNKNOWN = "Unknown"
    PR_NOT_FOUND = "Pull request not found"


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
    def is_pull_request_of_jira_mergeable(jira_id: str) -> GithubPRMergeStatus:
        found_pr = GitHubUtils.find_pull_request(jira_id)
        if not found_pr:
            return GithubPRMergeStatus.PR_NOT_FOUND
        return GitHubUtils.is_pull_request_mergeable(int(found_pr["number"]))

    @staticmethod
    def is_pull_request_mergeable(pr_id: int) -> GithubPRMergeStatus:
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

    @classmethod
    def find_pull_request(cls, jira_id):
        prs = requests.get(GITHUB_PULLS_LIST_API).json()
        pr_by_title = {pr["title"]: pr for pr in prs}

        found_pr = None
        for title, pr_dict in pr_by_title.items():
            if title.startswith(jira_id):
                found_pr = pr_dict
                # TODO Handle multiple PRs, e.g. https://issues.apache.org/jira/browse/YARN-11014
                break
        return found_pr

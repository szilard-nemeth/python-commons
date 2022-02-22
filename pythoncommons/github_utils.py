import logging
from enum import Enum

import requests

from pythoncommons.os_utils import OsUtils

LOG = logging.getLogger(__name__)
GITHUB_PULLS_API = "https://api.github.com/repos/apache/hadoop/pulls/$PR_ID"
GITHUB_PULLS_LIST_API = "https://api.github.com/repos/apache/hadoop/pulls"
GITHUB_PULLS_LIST_API_QUERY_PAGE = "page"
GITHUB_PULLS_LIST_API_QUERY_PER_PAGE = "per_page"


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
        """
        With GitHub's pulls API, we can't get the number of PR results or the number of pages.
        However, we can get the PRs by specifying the page=<number> query parameter.
        We should query the PRs as long as the current page gave some meaningful result.
        If the resulted PR list is empty, we can stop the itaration.
        See:
        https://docs.github.com/en/rest/reference/pulls
        https://stackoverflow.com/a/38699904/1106893
        :param jira_id:
        :return:
        """
        all_pr_by_title = cls.find_all_pull_requests()
        found_pr = None
        for title, pr_dict in all_pr_by_title.items():
            if title.startswith(jira_id):
                found_pr = pr_dict
                # TODO Handle multiple PRs, e.g. https://issues.apache.org/jira/browse/YARN-11014
                break
        return found_pr

    @classmethod
    def find_all_pull_requests(cls):
        all_prs_by_title = {}
        page_number = 1
        while True:
            page_param = f"{GITHUB_PULLS_LIST_API_QUERY_PAGE}={page_number}"
            url = f"{GITHUB_PULLS_LIST_API}?{GITHUB_PULLS_LIST_API_QUERY_PER_PAGE}=100&{page_param}"
            LOG.info("Querying Pull requests from URL: %s", url)
            prs = requests.get(url).json()
            pr_by_title = {pr["title"]: pr for pr in prs}
            if pr_by_title:
                LOG.info(
                    "Found %d open PRs for URL: %s. All PRs found so far: %d",
                    len(pr_by_title),
                    url,
                    len(all_prs_by_title),
                )
            else:
                break
            all_prs_by_title.update(pr_by_title)
            page_number += 1
        LOG.info("Found %d open PRs for base URL: %s", len(all_prs_by_title), GITHUB_PULLS_LIST_API)
        LOG.debug("Found open PRs for base URL '%s', details: %s", GITHUB_PULLS_LIST_API, all_prs_by_title)
        return all_prs_by_title

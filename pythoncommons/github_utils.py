import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List

import requests

from pythoncommons.os_utils import OsUtils

LOG = logging.getLogger(__name__)
GITHUB_PULLS_API_TEMPLATE = "https://api.github.com/repos/$owner$/$repo$/pulls/$PR_ID"
GITHUB_PULLS_LIST_API_TEMPLATE = "https://api.github.com/repos/$owner$/$repo$/pulls"
GITHUB_PULLS_LIST_API_QUERY_PAGE = "page"
GITHUB_PULLS_LIST_API_QUERY_PER_PAGE = "per_page"


class GitHubListPRsField(Enum):
    MERGEABLE = "mergeable"
    BASE = "base"
    HEAD = "head"
    NUMBER = "number"


class GitHubPRSrcDestField(Enum):
    REF = "ref"


@dataclass(frozen=True, eq=True)
class GitHubRepoIdentifier:
    owner: str
    repo: str

    def as_list_api(self):
        replacers = [("$owner$", self.owner), ("$repo$", self.repo)]
        return self._multi_replace(GITHUB_PULLS_LIST_API_TEMPLATE, replacers)

    def as_pulls_api(self):
        replacers = [("$owner$", self.owner), ("$repo$", self.repo)]
        return self._multi_replace(GITHUB_PULLS_API_TEMPLATE, replacers)

    @staticmethod
    def _multi_replace(base_str, replacers):
        res = base_str
        for replacer in replacers:
            res = res.replace(replacer[0], replacer[1])
        return res


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
    ALL_PRS_BY_REPO_ID_CACHE: Dict[GitHubRepoIdentifier, Dict[Any, Any]] = {}

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
    def is_pull_request_of_jira_mergeable(
        gh_repo_id: GitHubRepoIdentifier, jira_id: str, branches: List[str], use_cache=True
    ) -> Dict[str, GithubPRMergeStatus]:
        found_prs = GitHubUtils.find_pull_requests(gh_repo_id, jira_id, use_cache=use_cache)
        if not found_prs:
            return {br: GithubPRMergeStatus.PR_NOT_FOUND for br in branches}

        d = {}
        branches_set = set(branches)
        for pr in found_prs:
            pr_id = int(pr[GitHubListPRsField.NUMBER.value])
            target_branch_of_pr = pr[GitHubListPRsField.BASE.value][GitHubPRSrcDestField.REF.value]
            mergeable = GitHubUtils._is_pull_request_mergeable(gh_repo_id, pr_id)
            d[target_branch_of_pr] = mergeable
            branches_set.remove(target_branch_of_pr)

        # Loop through remaining branches and add PR_NOT_FOUND
        for br in branches_set:
            d[br] = GithubPRMergeStatus.PR_NOT_FOUND
        return d

    @staticmethod
    def _is_pull_request_mergeable(gh_repo_id: GitHubRepoIdentifier, pr_id: int) -> GithubPRMergeStatus:
        pr_url = GitHubUtils._get_pull_request_url(gh_repo_id, pr_id)
        pr_json = requests.get(pr_url).json()
        if GitHubListPRsField.MERGEABLE.value in pr_json:
            if pr_json[GitHubListPRsField.MERGEABLE.value]:
                return GithubPRMergeStatus.MERGEABLE
            else:
                return GithubPRMergeStatus.NOT_MERGEABLE
        return GithubPRMergeStatus.UNKNOWN

    @staticmethod
    def _get_pull_request_url(gh_repo_id: GitHubRepoIdentifier, pr_id: int):
        return gh_repo_id.as_pulls_api().replace("$PR_ID", str(pr_id))

    @classmethod
    def find_pull_requests(cls, gh_repo_id: GitHubRepoIdentifier, jira_id: str, use_cache=True) -> List[Any]:
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
        # TODO This does not find PRs that are closed / merged
        all_pr_by_title = cls._find_all_pull_requests(gh_repo_id, use_cache=use_cache)
        return cls.find_in_all_pull_requests(all_pr_by_title, jira_id)

    @classmethod
    def find_in_all_pull_requests(cls, all_prs_by_title, jira_id) -> List[Any]:
        found_prs = []
        for title, pr_dict in all_prs_by_title.items():
            if title.startswith(jira_id):
                found_prs.append(pr_dict)
        return found_prs

    @classmethod
    def _find_all_pull_requests(cls, gh_repo_id: GitHubRepoIdentifier, use_cache=True):
        if use_cache and gh_repo_id in cls.ALL_PRS_BY_REPO_ID_CACHE:
            return cls.ALL_PRS_BY_REPO_ID_CACHE[gh_repo_id]

        all_prs_by_title = {}
        page_number = 1
        while True:
            page_param = f"{GITHUB_PULLS_LIST_API_QUERY_PAGE}={page_number}"
            url = f"{gh_repo_id.as_list_api()}?{GITHUB_PULLS_LIST_API_QUERY_PER_PAGE}=100&{page_param}"
            LOG.info("Querying Pull requests from URL: %s", url)
            resp = requests.get(url)
            if resp.status_code != 200:
                resp_json = resp.json()
                message = resp_json["message"]
                raise ValueError("HTTP error during querying {}. Message: {}".format(url, message))
            prs = resp.json()
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
        LOG.info("Found %d open PRs for base URL: %s", len(all_prs_by_title), gh_repo_id.as_list_api())
        LOG.debug("Found open PRs for base URL '%s', details: %s", gh_repo_id.as_list_api(), all_prs_by_title)
        if use_cache:
            cls.ALL_PRS_BY_REPO_ID_CACHE[gh_repo_id] = all_prs_by_title
        return all_prs_by_title

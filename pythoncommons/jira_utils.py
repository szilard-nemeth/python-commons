import logging

import requests
from bs4 import BeautifulSoup
from pythoncommons.file_utils import FileUtils
from pythoncommons.string_utils import StringUtils

LOG = logging.getLogger(__name__)


class JiraUtils:
    @staticmethod
    def download_jira_html(jira_server, jira_id, to_file):
        resp = requests.get(jira_server + jira_id)
        resp.raise_for_status()
        FileUtils.save_to_file(to_file, resp.text)
        return resp.text

    @staticmethod
    def parse_subjiras_from_umbrella_html(html_doc, to_file, filter_ids):
        soup = BeautifulSoup(html_doc, "html.parser")
        issue_keys = []
        for link in soup.find_all("a", attrs={"class": "issue-link"}):
            issue_keys.append(link.attrs["data-issue-key"])

        if filter_ids:
            LOG.info("Filtering ids from result list: %s", filter_ids)
            issue_keys = [issue for issue in issue_keys if issue not in filter_ids]

        # Filter dupes
        issue_keys = list(set(issue_keys))
        FileUtils.save_to_file(to_file, StringUtils.list_to_multiline_string(issue_keys))
        return issue_keys

    @staticmethod
    def parse_subjiras_and_jira_titles_from_umbrella_html(html_doc, to_file, filter_ids):
        soup = BeautifulSoup(html_doc, "html.parser")
        result_dict = {}
        for link in soup.find_all("a", attrs={"class": "issue-link"}):
            jira_id = link.attrs["data-issue-key"]
            jira_title = link.contents[0]
            result_dict[jira_id] = jira_title

        if filter_ids:
            LOG.info("Filtering ids from result list: %s", filter_ids)
            result_dict = {jira_id: title for jira_id, title in result_dict.items() if jira_id not in filter_ids}

        FileUtils.save_to_file(to_file, StringUtils.dict_to_multiline_string(result_dict))
        return result_dict

import logging
import os
import time

import requests
from jira import JIRA, JIRAError, Issue
from jira.resources import Attachment

from pythoncommons.string_utils import StringUtils

LOG = logging.getLogger(__name__)


class JiraFetchMode:
    GSHEET = "GSHEET"
    ISSUES_CMDLINE = "ISSUES_CMDLINE"


class PatchOwner:
    def __init__(self, name, display_name):
        self.name = name
        self.display_name = display_name

    def __repr__(self):
        return repr((self.name, self.display_name))

    def __str__(self):
        # TODO understand unicode conversion issue in more details
        # return self.__class__.__name__ + \
        #        " { name: " + self.name + \
        #        ", display_name: " + str(self.display_name) + " }"
        # UnicodeEncodeError: 'ascii' codec can't encode character u'\xe1' in position 7: ordinal not in range(128)
        return (
            self.__class__.__name__
            + " { name: "
            + self.name
            + ", display_name: "
            + StringUtils.replace_special_chars(self.display_name)
            + " }"
        )


class PatchOverallStatus:
    def __init__(self, status):
        self.status = status

    def __repr__(self):
        return repr(self.status)

    def __str__(self):
        return self.__class__.__name__ + " { status: " + self.status + "}"


class JiraPatch:
    def __init__(self, issue_id, owner, patch_file):
        self.issue_id = issue_id
        # TODO owner and owner_short are currently not queried anywhere except __str__
        self.owner = owner
        self.owner_short = owner.name
        self.owner_display_name = owner.display_name
        self.filename = patch_file
        self.overall_status = PatchOverallStatus("N/A")
        self.file_path = None

    def set_patch_file_path(self, file_path):
        self.file_path = file_path

    def set_overall_status(self, overall_status):
        self.overall_status = overall_status

    def __repr__(self):
        return repr((self.issue_id, self.owner, self.filename))

    def __str__(self):
        return (
            self.__class__.__name__
            + " { issue_id: "
            + self.issue_id
            + ", owner: "
            + str(self.owner)
            + ", filename: "
            + str(self.filename)
            + " }"
        )

    def __hash__(self):
        return hash((self.issue_id, self.owner, self.filename))

    def __eq__(self, other):
        if isinstance(other, JiraPatch):
            return self.issue_id == other.issue_id and self.owner == other.owner and self.filename == other.filename
        return False


class JiraWrapper:
    def __init__(self, jira_url: str, default_branch: str, patches_root):
        options = {"server": jira_url}
        self.jira: JIRA = JIRA(options=options, timeout=20, max_retries=10)
        self.jira_url: str = jira_url
        self.default_branch: str = default_branch
        self.patches_root: str = patches_root

    def download_patch_file(self, patch: JiraPatch):
        LOG.debug("Querying jira issue %s", patch.issue_id)
        issue: Issue = self.jira.issue(patch.issue_id)

        found: bool = False
        for attachment in issue.fields.attachment:  # type: Attachment
            if patch.filename == attachment.filename:
                patch_file_path: str = os.path.join(self.patches_root, patch.issue_id, patch.filename)

                issue_dir: str = os.path.dirname(patch_file_path)
                if not os.path.exists(issue_dir):
                    os.makedirs(issue_dir)

                LOG.debug("Downloading patch from issue %s to file %s", patch.issue_id, patch_file_path)
                attachment_data = self.download_attachment_with_retries(attachment)

                # TODO let JiraPatch object create the path
                patch.set_patch_file_path(patch_file_path)
                with open(patch_file_path, "w") as file:
                    file.write(attachment_data)
                found = True
                break

        if not found:
            raise ValueError(
                "Cannot find attachment with name '{name}' for issue {issue}".format(
                    name=patch.filename, issue=patch.issue_id
                )
            )

    def get_jira_issue(self, issue_id: str):
        retries = 1
        try:
            if retries > 5:
                raise Exception("Jira could not be accessed 5 times, consecutively! Stopping execution.")
            return self.jira.issue(issue_id)
        except JIRAError:
            LOG.exception("JIRAError caught! Retrying to access jira!")
            retries += 1

    def download_attachment_with_retries(self, attachment: Attachment):
        tried = 0
        max_retries = 5
        while max_retries != tried:
            try:
                tried += 1
                return attachment.get()
            except requests.exceptions.Timeout:
                LOG.error("Read timed out while communicating with %s, sleeping for 5 seconds...", self.jira_url)
                time.sleep(5)

    def list_attachments(self, issue_id: str):
        issue = self.jira.issue(issue_id)

        for attachment in issue.fields.attachment:
            print("Name: '{filename}', size: {size}".format(filename=attachment.filename, size=attachment.size))
            # to read content use `get` method:
            # print("Content: '{}'".format(attachment.get()))

    def get_status(self, issue_id: str):
        issue = self.jira.issue(issue_id)
        status = issue.fields.status
        LOG.debug("Status of issue %s: %s", issue_id, status)
        return status.name

    def is_status_resolved(self, issue_id: str):
        status = self.get_status(issue_id)
        if status == "Resolved":
            LOG.debug("Status of jira is 'Resolved': %s", issue_id)
            return True
        return False

    @staticmethod
    def determine_patch_owner(jira_issue: Issue):
        if jira_issue.fields.assignee:
            owner_name = jira_issue.fields.assignee.name
            owner_display_name = jira_issue.fields.assignee.displayName
        else:
            owner_name = "unassigned"
            owner_display_name = "unassigned"
        return PatchOwner(owner_name, owner_display_name)

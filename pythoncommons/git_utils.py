import logging

LOG = logging.getLogger(__name__)


class GitUtils:
    def __init__(self):
        pass

    @classmethod
    def convert_remote_branch_name_to_local(cls, remote_branch):
        stripped_rbranch = remote_branch.lstrip()
        # Strip off leading "<remote>/" part, if any
        split_parts = stripped_rbranch.rsplit("/", 1)

        if len(split_parts) == 2:
            l_branch = split_parts[1]
        else:
            # Branch is already in local format
            l_branch = split_parts

        return l_branch

    @classmethod
    def get_number_of_conflicts_from_str(cls, str):
        conflicts = str.count("patch failed: ")
        LOG.debug("Number of conflicts: %s", conflicts)
        return conflicts

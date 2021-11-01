import logging
import os
import sys

from pythoncommons.project_utils import ProjectUtils

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


class FakeBranchComparator:
    def __init__(self):
        output_child_dir = ProjectUtils.get_output_child_dir("branch-comparator")
        session_dir = ProjectUtils.get_session_dir_under_child_dir(os.path.basename(output_child_dir))
        LOG.info("Session dir: " + session_dir)

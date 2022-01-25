import logging
import os
import site
import sys

from pythoncommons.project_utils import ProjectUtils, ProjectRootDeterminationStrategy
from testproject.commands.testcommand.dummy_test_command import FakeBranchComparator

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger("project_utils")
LOG.setLevel(logging.DEBUG)


def main():
    LOG = logging.getLogger(__name__)
    ProjectUtils.project_root_determine_strategy = ProjectRootDeterminationStrategy.SYS_PATH
    output_basedir = ProjectUtils.get_output_basedir("testproject")
    output_child_dir = ProjectUtils.get_output_child_dir("branch-comparator")
    logfilename = ProjectUtils.get_default_log_file("test-log")

    LOG.info("Output basedir: " + output_basedir)
    LOG.info("Output child dir: " + output_child_dir)
    LOG.info("logfilename: " + logfilename)

    python_global_site = site.getsitepackages()[0]
    python_user_site = site.USER_SITE
    LOG.info("sys.path: %s", sys.path)
    LOG.info("Global site: " + python_global_site)
    LOG.info("User site: " + python_user_site)

    LOG.info("Creating FakeBranchComparator...")
    FakeBranchComparator()
    ProjectUtils.reset_root_determine_strategy_to_default()


if __name__ == "__main__":
    main()

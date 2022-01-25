import logging
import sys

from pythoncommons.project_utils import ProjectUtils, ProjectRootDeterminationStrategy

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger("project_utils")
LOG.setLevel(logging.DEBUG)


def main():
    LOG = logging.getLogger(__name__)
    LOG.info("hello world")

    LOG.info("sys.path: %s", sys.path)
    ProjectUtils.project_root_determine_strategy = ProjectRootDeterminationStrategy.SYS_PATH
    ProjectUtils.FORCE_SITE_PACKAGES_IN_PATH_NAME = False
    basedir = ProjectUtils.get_output_basedir("test")
    logfilename = ProjectUtils.get_default_log_file("test")
    LOG.info("basedir: " + basedir)
    LOG.info("logfilename: " + logfilename)

    ProjectUtils.reset_root_determine_strategy_to_default()


if __name__ == "__main__":
    main()

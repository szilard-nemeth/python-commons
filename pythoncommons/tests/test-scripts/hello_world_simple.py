import logging
import sys

from pythoncommons.project_utils import ProjectUtils, ProjectRootDeterminationStrategy

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, force=True)
LOG = logging.getLogger("project_utils")
LOG.setLevel(logging.DEBUG)

LOG = logging.getLogger(__name__)
LOG.info("hello world")

LOG.info("sys.path: %s", sys.path)
ProjectUtils.project_root_determine_strategy = ProjectRootDeterminationStrategy.SYS_PATH
basedir = ProjectUtils.get_output_basedir('test')
logfilename = ProjectUtils.get_default_log_file('test')
LOG.info("basedir: " + basedir)
LOG.info("logfilename: " + logfilename)

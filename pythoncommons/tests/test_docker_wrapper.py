import unittest

from pythoncommons.docker_wrapper import DockerTestSetup, DockerInitException
import logging

LOG = logging.getLogger(__name__)


class TestDocker(unittest.TestCase):
    def test_init_docker_test_setup(self):
        dts = DockerTestSetup("busybox", fail_fast_if_docker_unavailable=False)
        try:
            container, cmd_outputs = dts.run_container(
                ["ls -la /"], capture_progress=True, print_progress=False, progress=None
            )
        except DockerInitException as e:
            # Catch DockerInitException if Docker is not running
            LOG.exception("Docker init exception. ", exc_info=e)

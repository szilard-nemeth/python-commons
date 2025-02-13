import unittest

from pythoncommons.docker_wrapper import DockerTestSetup, DockerInitException
import logging

LOG = logging.getLogger(__name__)


class TestDocker(unittest.TestCase):
    def test_init_docker_test_setup(self):
        dts = DockerTestSetup("busybox", fail_fast_if_docker_unavailable=False)
        try:
            _ = dts.run_container(["ls -la /"], capture_progress=True, print_progress=False, progress=None)
        except DockerInitException as e:
            # Catch DockerInitException if Docker is not running
            LOG.exception("Docker init exception. ", exc_info=e)

    def test_command_fails_default_behavior(self):
        dts = DockerTestSetup("busybox", fail_fast_if_docker_unavailable=False)
        self.assertRaises(
            ValueError,
            lambda: dts.run_container(["badcommand"], capture_progress=True, print_progress=False, progress=None),
        )

    def test_command_does_not_fail_with_fail_on_error_false(self):
        dts = DockerTestSetup("busybox", fail_fast_if_docker_unavailable=False)
        results = dts.run_container(
            ["badcommand"], capture_progress=True, print_progress=False, progress=None, fail_on_error=False
        )
        results.container.remove(force=True)
        LOG.info("Command outputs: %s", results.command_outputs())

    def test_with_multiple_commands(self):
        dts = DockerTestSetup("busybox", fail_fast_if_docker_unavailable=False)
        results = dts.run_container(
            ["badcommand", "ls -la /", "ls /"],
            capture_progress=True,
            print_progress=False,
            progress=None,
            fail_on_error=False,
        )
        results.container.remove(force=True)
        LOG.info("Command outputs: %s", results.command_outputs())

        self.assertIsNotNone(results.get_result("badcommand"))
        self.assertTrue(results.get_result("badcommand").exit_code != 0)

        self.assertIsNotNone(results.get_result("ls -la /"))
        self.assertEqual(results.get_result("ls -la /").exit_code, 0)

        self.assertIsNotNone(results.get_result("ls /"))
        self.assertEqual(results.get_result("ls /").exit_code, 0)

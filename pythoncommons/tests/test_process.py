import io
import logging
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from copy import copy
from datetime import datetime
from typing import List

from pythoncommons.file_utils import FileUtils
from pythoncommons.logging_setup import SimpleLoggingSetup
from pythoncommons.process import CommandRunner, SubprocessCommandRunner
from pythoncommons.tests.test_project_utils import TEST_SCRIPTS_DIR

REPO_ROOT_DIRNAME = "python-commons"
PYTHONCOMMONS_MODULE_NAME = "pythoncommons"
SCRIPT_WITH_ARGS_SH = "script_with_args.sh"
SCRIPT_THAT_FAILS_SH = "script_that_fails.sh"
UTILS_SH = "utils.sh"
SLEEPING_LOOP_SH = "sleeping_loop.sh"
import logging
LOG = logging.getLogger(__name__)


class ProcessTests(unittest.TestCase):
    """
    IMPORTANT !
    Specify this as additional CLI arguments if running from PyCharm:
    -s  --capture=no --log-cli-level=10

    Source: https://stackoverflow.com/a/71913594/1106893
    """

    def _get_test_name(self):
        return os.environ.get('PYTEST_CURRENT_TEST').split(':')[-1].split(' ')[0]

    def get_test_dir(self, parent):
        date_str = datetime.today().strftime('%Y%m%d_%H%M%S')
        dir = os.path.join(parent, f"{self._get_test_name()}-{date_str}")
        os.mkdir(dir)
        return dir

    @staticmethod
    def find_script(name: str):
        basedir = FileUtils.find_repo_root_dir(__file__, PYTHONCOMMONS_MODULE_NAME, raise_error=True)
        return FileUtils.join_path(basedir, "test-scripts", name)

    @staticmethod
    def find_input_file(name: str):
        basedir = FileUtils.find_repo_root_dir(__file__, PYTHONCOMMONS_MODULE_NAME, raise_error=True)
        return FileUtils.join_path(basedir, "test-input-files", name)

    def test_subprocessrunner_run_and_follow_stdout_stderr_does_not_hang(self):
        script = self.find_script(SLEEPING_LOOP_SH)
        basedir = FileUtils.get_parent_dir_name(script)
        cmd = f"cd {basedir};{script}"
        cmd = f"bash -c \"{cmd}\""
        CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
        CMD_LOG.setLevel(logging.DEBUG)
        SubprocessCommandRunner.run_and_follow_stdout_stderr(
                        cmd, stdout_logger=CMD_LOG, exit_on_nonzero_exitcode=True
                    )
        # TODO verify if all printed to stdout / stderr

    def test_subprocessrunner_run_and_follow_stdout_stderr_defaults(self):
        script = self.find_script(SLEEPING_LOOP_SH)
        basedir = FileUtils.get_parent_dir_name(script)
        cmd = f"cd {basedir};{script}"
        cmd = f"bash -c \"{cmd}\""
        SubprocessCommandRunner.run_and_follow_stdout_stderr(cmd)
        # TODO verify if all printed to stdout / stderr

    def test_subprocessrunner_run_no_output(self):
        script = self.find_script(SLEEPING_LOOP_SH)
        parent_dir = FileUtils.get_parent_dir_name(script)
        cmd = f"{script}"
        cmd = f"bash -c \"{cmd}\""

        command_result = SubprocessCommandRunner.run(cmd,
                                                     working_dir=parent_dir,
                                                     log_command_result=False,
                                                     fail_on_error=True,
                                                     fail_message="Failed to run script")
        # TODO verify empty stdout / stderr

    def test_commandrunner_execute_script_with_args(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            test_dir = self.get_test_dir(tmpdirname)
            output_file = FileUtils.join_path(test_dir, "testfile")
            script_path = ProcessTests.find_script(SCRIPT_WITH_ARGS_SH)
            script_parent_dir = FileUtils.get_parent_dir_name(script_path)
            script_name = os.path.basename(script_path)

            args = f"arg1 arg2 arg3"

            cli_cmd, cli_output = CommandRunner.execute_script(
                script_name, args=args, working_dir=script_parent_dir, output_file=output_file, use_tee=True
            )
            file_contents = FileUtils.read_file(output_file)
            self.assertEqual('arg: arg1\narg: arg2\narg: arg3\n', file_contents)
            self.assertEqual('arg: arg1\narg: arg2\narg: arg3', cli_output)

    def test_commandrunner_run_cli_command_with_args(self):
        script_path = ProcessTests.find_script(SCRIPT_WITH_ARGS_SH)

        args = f"arg1 arg2 arg3"
        cmd = f"{script_path} {args}"
        cmd, cli_output = CommandRunner.run_cli_command(
            cmd, fail_on_empty_output=False, print_command=False, fail_on_error=False
        )

        self.assertEqual('arg: arg1\narg: arg2\narg: arg3', cli_output)


    def test_commnadrunner_egrep_with_cli(self):
        with tempfile.TemporaryDirectory() as tmpdirname:
            test_dir = self.get_test_dir(tmpdirname)
            output_file = FileUtils.join_path(test_dir, "testfile")

            git_log_file = self.find_input_file("hadoop-git-repo-log.txt")
            git_log: str = FileUtils.read_file(git_log_file)
            git_log: List[str] = git_log.splitlines()

            cli_command, output = CommandRunner.egrep_with_cli(
                git_log,
                file=output_file,
                grep_for="backport",
                escape_single_quotes=False,
                escape_double_quotes=True,
                fail_on_empty_output=False,
                fail_on_error=True,
            )
            commit_messages = set()
            for l in output.splitlines():
                tmp = l.split("(")[0]
                tmp = tmp.replace("*", "")
                tmp = tmp.replace("|", "")
                tmp = tmp.strip()
                commit_messages.add(tmp)
            self.assertIn("a90c7221436c - HADOOP-18724. [FOLLOW-UP] cherrypick changes from branch-3.3 backport", commit_messages)
            self.assertIn("9676774e233f - HDFS-9273. Moving to 2.6.3 CHANGES section to reflect the backport.",
                          commit_messages)
            self.assertIn("c753617a48bf - Move HADOOP-11361, HADOOP-12348 and HADOOP-12482 from 2.8.0 to 2.7.3 in CHANGES.txt for backporting.",
                          commit_messages)
            self.assertIn("f3e5bc67661e - CHANGES.txt: Moving YARN-1884, YARN-3171, YARN-3740, YARN-3248, YARN-3544 to 2.6.1 given the backport.",
                          commit_messages)
            self.assertIn("fbbb7ff1ed11 - Updating all CHANGES.txt files to move entires from future releases into 2.6.1 section given the large number of backports to 2.6.1.",
                          commit_messages)
            self.assertIn("8770c82acc94 - MAPREDUCE-6286. Amend commit to CHANGES.txt for backport into 2.7.0.",
                          commit_messages)
            self.assertIn("7981908929a0 - backported HADOOP-10125 to branch2, update CHANGES.txt",
                          commit_messages)
            self.assertIn("b8f1cf31926d - HDFS-4817. Moving changelog to Release 2.2.0 section to reflect the backport.",
                          commit_messages)
            self.assertIn("2245fcc8c5c4 - Move HDFS-347 and related JIRAs to 2.0.5 section of CHANGES.txt after backport",
                          commit_messages)
            self.assertIn("0b9a1f908a57 - Moving MAPREDUCE-4678's changes line to 0.23 section to prepare for backport.",
                          commit_messages)
            self.assertIn("ebcc708d78ef - Move HADOOP-9004 to 2.0.3 section after backport",
                          commit_messages)
            self.assertIn("d6c50b4a67f6 - Move QJM-related backports into 2.0.3 release section in CHANGES.txt after backport to branch-2",
                          commit_messages)
            self.assertIn("c9ed8342f527 - Move HDFS-2330 and HDFS-3190 to branch-2 section, since they have been backported from trunk.",
                          commit_messages)
            self.assertIn("32431d25aed9 - HADOOP-7469 backporting to 0.23; moving in CHANGES.TXT",
                          commit_messages)
            LOG.info(commit_messages)

    def test_subprocessrunner_run_script_fails(self):
        script_path = ProcessTests.find_script(SCRIPT_THAT_FAILS_SH)
        with self.assertRaises(ValueError):
            SubprocessCommandRunner.run(script_path, fail_on_error=True, fail_message="Failed to run script")

    def test_command_runner_run_sync_stdout_and_stderr_specified(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, _out=sys.stdout, _err=sys.stderr)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(cmd_stdout), 0)
            self.assertEqual(len(cmd_stderr), 0)
            self.assertTrue(len(stdout.getvalue().splitlines()) > 1)
            self.assertTrue(len(stderr.getvalue().splitlines()) > 50)

    def test_command_runner_run_sync_stdout_callback_and_stderr_callback(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd,
                                                                    add_stdout_callback=True,
                                                                    add_stderr_callback=True,
                                                                    _out=None, _err=None)
            self.assertEqual(exit_code, 0)
            self.assertTrue(len(cmd_stdout) > 50)
            self.assertTrue(len(cmd_stderr) > 50)
            self._assert_empty_stdout(stdout, cmd)
            self.assertEqual(len(stderr.getvalue()), 0)

    def test_command_runner_run_sync_stdout_callback_and_stderr_callback_log_both(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd,
                                                                    add_stdout_callback=True,
                                                                    add_stderr_callback=True,
                                                                    _out=None, _err=None,
                                                                    log_stdout_to_logger=True,
                                                                    log_stderr_to_logger=True)
            self.assertEqual(exit_code, 0)
            self.assertTrue(len(cmd_stdout) > 50)
            self.assertTrue(len(cmd_stderr) > 50)
            # stdout holds all logs, stderr is empty as logger logs all records to console (stdout)
            self.assertTrue(len(stdout.getvalue().splitlines()) > 1)
            self.assertEqual(len(stderr.getvalue()), 0)

    def test_command_runner_run_sync_stdout_callback_stderr_specified(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, add_stdout_callback=True, _out=None, _err=sys.stderr)
            self.assertEqual(exit_code, 0)
            self.assertTrue(len(cmd_stdout) > 50)
            self.assertEqual(len(cmd_stderr), 0)
            self._assert_empty_stdout(stdout, cmd)
            self.assertTrue(len(stderr.getvalue()) > 1000)

    def test_command_runner_run_sync_stdrr_callback_stdout_specified(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, add_stderr_callback=True, _out=sys.stdout)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(cmd_stdout), 0)
            self.assertTrue(len(cmd_stderr) > 50)
            self.assertTrue(len(stdout.getvalue()) > 50)
            self.assertEqual(len(stderr.getvalue()), 0)

    def test_command_runner_run_sync_stdout_stderr_both_unspecified(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, _out=None, _err=None)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(cmd_stdout), 0)
            self.assertEqual(len(cmd_stderr), 0)
            self._assert_empty_stdout(stdout, cmd)
            self.assertEqual(len(stderr.getvalue()), 0)

    def test_command_runner_run_sync_stdout_stderr_both_unspecified_without_capturing(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, _out=None, _err=None)
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(cmd_stdout), 0)
            self.assertEqual(len(cmd_stderr), 0)
            self._assert_empty_stdout(stdout, cmd)
            self.assertEqual(len(stderr.getvalue()), 0)

    def _assert_empty_stdout(self, stdout, cmd):
        orig_lines = stdout.getvalue().splitlines()
        LOG.info("**Lines from stdout: %s", orig_lines)

        lines = copy(orig_lines)
        lines.remove(f"Running command: {cmd}")
        remaining_lines = copy(lines)
        # Remove empty line
        for line in lines:
            if line == "":
                remaining_lines.remove(line)
        self.assertEqual(len(remaining_lines), 0)

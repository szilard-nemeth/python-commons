import io
import operator
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from io import StringIO
from numbers import Number
from typing import List, Tuple, Callable

from pythoncommons.constants import ExecutionMode
from pythoncommons.file_utils import FileUtils
from pythoncommons.logging_setup import SimpleLoggingSetup
from pythoncommons.logging_utils import LoggingUtils
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

def as_stringio(lines: str) -> StringIO:
    return StringIO(lines)

Operator = Callable[[Number, Number], bool]
DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES = 60

class ProcessTests(unittest.TestCase):
    """
    IMPORTANT !
    Specify this as additional CLI arguments if running from PyCharm:
    -s  --capture=no --log-cli-level=10

    Source: https://stackoverflow.com/a/71913594/1106893
    """

    @classmethod
    def setUpClass(cls):
        log_files = LoggingUtils.project_setup(execution_mode=ExecutionMode.TEST)

        def audit(event, args):
            if event == 'subprocess.Popen':
                LOG.debug(f'[AUDIT subprocess.Popen]: {event} with args={args}')
        sys.addaudithook(audit)

    @staticmethod
    def _get_test_name():
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


    def _assert_stdout_stderr(self, cmd,
                              stdout_assert: Tuple[StringIO, Operator, int],
                              stderr_assert: Tuple[StringIO, Operator, int]):
        def get_filtered_contents(stdout_orig):
            res = []
            for line in stdout_orig:
                # Filter logger lines from stdout
                if "***" not in line:
                    res.append(line)
            return res

        def get_truth(a: Number, relate: operator, b: Number):
            return relate(a, b)

        def get_ops_str(o):
            ops = {operator.gt: '>',
                   operator.lt: '<',
                   operator.ge: '>=',
                   operator.le: '<=',
                   operator.eq: '=='
            }
            return ops[o]

        stdout = stdout_assert[0]
        stdout_op = stdout_assert[1]
        stdout_num = stdout_assert[2]

        stderr = stderr_assert[0]
        stderr_op = stderr_assert[1]
        stderr_num = stderr_assert[2]

        self.assertIsInstance(stdout, StringIO)
        self.assertIsInstance(stderr, StringIO)

        stdout_contents = get_filtered_contents(stdout.getvalue().splitlines())
        stderr_contents = get_filtered_contents(stderr.getvalue().splitlines())
        LOG.debug("***command: %s", cmd)
        LOG.debug("***stdout: %s", stdout_contents)
        LOG.debug("***stdout # of lines: %d", len(stdout_contents))
        LOG.debug("***stderr: %s", stderr_contents)
        LOG.debug("***stderr # of lines: %d", len(stderr_contents))

        self.assertTrue(get_truth(len(stdout_contents), stdout_op, stdout_num), f"False statement: {len(stdout_contents)} {get_ops_str(stdout_op)} {stdout_num}")
        self.assertTrue(get_truth(len(stderr_contents), stderr_op, stderr_num), f"False statement: {len(stderr_contents)} {get_ops_str(stderr_op)} {stderr_num}")

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
            self.assertEqual('arg: arg1\narg: arg2\narg: arg3', cli_output)
            self.assertEqual('arg: arg1\narg: arg2\narg: arg3\n', file_contents)


    def test_commandrunner_run_cli_command_with_args(self):
        script_path = ProcessTests.find_script(SCRIPT_WITH_ARGS_SH)

        args = f"arg1 arg2 arg3"
        cmd = f"{script_path} {args}"
        cmd, cli_output = CommandRunner.run_cli_command(
            cmd, fail_on_empty_output=False, print_command=False, fail_on_error=False
        )

        self.assertEqual('arg: arg1\narg: arg2\narg: arg3', cli_output)

    def test_commandrunner_egrep_with_cli(self):
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

            # cmd_stdout expected to be empty as add_stdout_callback=False for cmd_runner.run_sync
            # cmd_stderr expected to be empty as add_stderr_callback=False for cmd_runner.run_sync
            # stdout expected to be empty as _out is specified for cmd_runner.run_sync
            # stderr expected to be empty as _err is specified for cmd_runner.run_sync
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 0),
                                       (as_stringio(cmd_stderr), operator.eq, 0))
            self._assert_stdout_stderr(cmd, (stdout, operator.eq, 1),
                                       (stderr, operator.gt, DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES))

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
                                                                    _out=None,
                                                                    _err=None)
            self.assertEqual(exit_code, 0)

            # cmd_stdout expected to contain one printed line as add_stdout_callback=True
            # cmd_stderr expected to contain all lines logged to stderr as add_stderr_callback=True
            # stdout expected to contain no line as _out is not specified for cmd_runner.run_sync
            # stderr expected to contain no line as _err is not specified for cmd_runner.run_sync
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 1),
                                       (as_stringio(cmd_stderr), operator.gt, DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES))
            self._assert_stdout_stderr(cmd, (stdout, operator.eq, 0),
                                       (stderr, operator.eq, 0))

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
                                                                    _out=None,
                                                                    _err=None,
                                                                    log_stdout_to_logger=True,
                                                                    log_stderr_to_logger=True)
            self.assertEqual(exit_code, 0)

            # cmd_stdout should contain a single line as add_stdout_callback=True
            # cmd_stderr expected to contain all lines as add_stderr_callback=True
            # stderr should be empty as _err=None
            # stdout should be empty as _out=None but as log_stdout_to_logger=True and log_stderr_to_logger=True,
            #   all lines that are logged to either stdout or stderr will be processed by the logger that prints to console (stdout)
            #   so we expect 2 * DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES lines on stdout.
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 1),
                                       (as_stringio(cmd_stderr), operator.gt, DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES))
            self._assert_stdout_stderr(cmd, (stdout, operator.gt, 2 * DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES),
                                       (stderr, operator.eq, 0))

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

            # cmd_stdout should contain a single line as add_stdout_callback=True
            # cmd_stderr expected to contain no line as add_stderr_callback=False
            # stdout should be empty as _out=None
            # stderr expected to contain all lines logged to stderr as _err is specified
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 1),
                                       (as_stringio(cmd_stderr), operator.eq, 0))
            self._assert_stdout_stderr(cmd,
                                       (stdout, operator.eq, 0),
                                       (stderr, operator.gt, DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES))

    def test_command_runner_run_sync_stderr_callback_stdout_specified(self):
        with (tempfile.TemporaryDirectory() as tmpdirname,
              redirect_stdout(io.StringIO()) as stdout,
              redirect_stderr(io.StringIO()) as stderr):
            test_dir = self.get_test_dir(tmpdirname)
            CMD_LOG = SimpleLoggingSetup.create_command_logger(__name__)
            cmd_runner = CommandRunner(CMD_LOG)

            cmd = f". {TEST_SCRIPTS_DIR}/download.sh; download-random-jars {test_dir}"
            exit_code, cmd_stdout, cmd_stderr = cmd_runner.run_sync(cmd, add_stderr_callback=True, _out=sys.stdout)
            self.assertEqual(exit_code, 0)

            # cmd_stdout expected to be empty as there is no callback
            # cmd_stderr expected to contain all lines logged to stderr as add_stderr_callback=True
            # stdout should contain one line as sys.stdout is redirected to stdout
            # stderr expected to contain no line as _err is not specified for cmd_runner.run_sync
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 0),
                                       (as_stringio(cmd_stderr), operator.gt, DOWNLOAD_RANDOM_JARS_SCRIPT_MIN_OUTPUT_LINES))
            self._assert_stdout_stderr(cmd, (stdout, operator.eq, 1),
                                       (stderr, operator.eq, 0))

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

            # cmd_stdout expected to contain no line as add_stdout_callback=False
            # cmd_stderr expected to contain no line as add_stderr_callback=False
            # stdout expected to contain no line as _out is not specified for cmd_runner.run_sync
            # stderr expected to contain no line as _err is not specified for cmd_runner.run_sync
            self._assert_stdout_stderr(cmd,
                                       (as_stringio(cmd_stdout), operator.eq, 0),
                                       (as_stringio(cmd_stderr), operator.eq, 0))
            self._assert_stdout_stderr(cmd, (stdout, operator.eq, 0),
                                       (stderr, operator.eq, 0))

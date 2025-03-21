import io
from dataclasses import dataclass
from typing import Callable, Any, List, Optional
from subprocess import Popen
import sh
import logging
import os
import pty
import select
import shlex
import subprocess
import sys
import termios
import time
import tty
from pythoncommons.file_utils import FileUtils
from pythoncommons.string_utils import auto_str, StringUtils


class CommandOutput:
    def __init__(self, logger, single_result, log_stdout_to_logger, log_stderr_to_logger):
        self._logger = logger
        self._log_stdout = log_stdout_to_logger
        self._log_stderr = log_stderr_to_logger
        self._stdout = []
        self._stderr = []
        self._single_result = single_result

    def append_stdout(self, line):
        self._stdout.append(line)
        if self._log_stdout:
            self._logger.info(line)

    def append_stderr(self, line):
        self._stderr.append(line)
        if self._log_stderr:
            self._logger.info(line)

    def get_stdout(self):
        return " ".join(self._stdout)

    def get_stderr(self):
        return " ".join(self._stderr)

    def get_sanitized_stdout(self):
        return self._get_sanitized_output(self._stdout)

    def get_sanitized_stderr(self):
        output = self._get_sanitized_output(self._stderr)
        return output

    def _get_sanitized_output(self, stream):
        output = [line.rstrip() for line in stream]
        if len(output) == 1 and self._single_result:
            output = output[0]
            return output
        return "\n".join(output)


# TODO consolidate methods
class CommandRunner:
    def __init__(self, log):
        self.LOG = log

    def run_sync(
        self,
        cmd: str,
        fail_on_error: bool = False,
        single_result=True,
        _out: str = None,
        _err: str = None,
        _tee: bool = False,
        _err_to_out: bool = False,
        add_stdout_callback: bool = False,
        add_stderr_callback: bool = False,
        log_stdout_to_logger: bool = False,
        log_stderr_to_logger: bool = False,
    ):
        if add_stdout_callback and _out:
            raise ValueError(
                "Invalid input parameters! Cannot specify '_out' and 'add_stdout_callback' at the same time!"
            )
        if add_stderr_callback and _err:
            raise ValueError(
                "Invalid input parameters! Cannot specify '_err' and 'add_stderr_callback' at the same time!"
            )

        def _prepare_kwargs(_err, _out, _tee):
            # _out and _err should be always added as explicit None values also matter
            # e.g. if _out=None, err=None is specified, we want to override sh's default parameters with explicit disabling stdout and stderr
            kwargs = {"_out": _out, "_err": _err}
            if add_stdout_callback:
                kwargs["_out"] = stdout_callback
            if add_stderr_callback:
                kwargs["_err"] = stderr_callback
            if _tee:
                kwargs["_tee"] = True
            if _err_to_out:
                kwargs["_err_to_out"] = True
            return kwargs

        def stdout_callback(line: str):
            """
            Documentation for kwargs '_out':
            https://sh.readthedocs.io/en/latest/sections/redirection.html#function-callback
            https://sh.readthedocs.io/en/latest/sections/asynchronous_execution.html#callbacks
            :param self:
            :param line:
            :return:
            """
            cmd_output.append_stdout(line)

        cmd_output = CommandOutput(self.LOG, single_result, log_stdout_to_logger, log_stderr_to_logger)

        def stderr_callback(line: str):
            cmd_output.append_stderr(line)

        exit_code = None
        try:
            kwargs = _prepare_kwargs(_err, _out, _tee)
            process = sh.bash("-c", cmd, **kwargs)
            process.wait()
            exit_code = process.exit_code
        except sh.ErrorReturnCode as e:
            if fail_on_error:
                raise e
            return e.exit_code, e.stdout, e.stderr
        except Exception as e:
            self.LOG.error("Error while executing command {}:\n {}".format(cmd, str(e)))

        # self.LOG.info(cmd_output.get_stdout())
        # Remove trailing newlines from each line
        stdout = cmd_output.get_sanitized_stdout()
        stderr = cmd_output.get_sanitized_stderr()

        return exit_code, stdout, stderr

    def run_async(
        self, cmd: str, stdout_callback: Callable[[str], str] = None, stderr_callback: Callable[[str], str] = None
    ) -> Popen:
        self.LOG.info("Running command async: {}".format(cmd))

        _stdout_callback = stdout_callback
        _stderr_callback = stderr_callback

        if stdout_callback is None:
            _stdout_callback = print
        if stderr_callback is None:
            _stderr_callback = print

        process = sh.bash("-c", cmd, _out=_stdout_callback, _err=_stderr_callback, _bg=True)

        self.LOG.info("\n")

        return process

    def run_interactive(self, cmd: str) -> int:
        return subprocess.call(cmd, shell=True)

    @staticmethod
    def run(command, shell=False, shlex_split=True):
        if shlex_split:
            args = shlex.split(command)
        else:
            args = command
        proc = subprocess.run(
            args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell
        )
        args2 = str(proc.args)
        return RegularCommandResult(command, args2, proc.stdout, proc.stderr, proc.returncode)

    @staticmethod
    def egrep_with_cli(
        git_log_result: List[str],
        file: str,
        grep_for: str,
        escape_single_quotes=True,
        escape_double_quotes=True,
        fail_on_empty_output=True,
        fail_on_error=True,
    ):
        FileUtils.save_to_file(file, StringUtils.list_to_multiline_string(git_log_result))
        if escape_single_quotes or escape_double_quotes:
            grep_for = StringUtils.escape_str(
                grep_for, escape_single_quotes=escape_single_quotes, escape_double_quotes=escape_double_quotes
            )
        cli_command = f'cat {file} | egrep "{grep_for}"'
        return CommandRunner.run_cli_command(
            cli_command, fail_on_empty_output=fail_on_empty_output, fail_on_error=fail_on_error
        )

    @staticmethod
    def execute_script(script: str, args: str, working_dir: str = None, output_file: str = None, use_tee=False):
        cli_command = ""
        if working_dir:
            # TODO Figure out why this wouldn't work only with GitHub actions:
            #  cli_command += f"cd {working_dir};{script}"
            #  without using ./<script-name> it DOES NOT WORK AND FAILS!
            # Related audit log with fixed run:
            # 2025-02-07 04:14:55,599 - DEBUG - pythoncommons.tests.test_process - [AUDIT subprocess.Popen]:
            # subprocess.Popen with args=('/bin/sh', ['/bin/sh', '-c', 'cd /home/runner/work/python-commons/python-commons/pythoncommons/test-scripts;./script_with_args.sh arg1 arg2 arg3 | tee /tmp/tmpt_msgge2/test_commandrunner_execute_script_with_args-20250207_041455/testfile'], None, None)
            # FAILED RUN
            #
            #
            # =================================== FAILURES ===================================
            # ___________ ProcessTests.test_commandrunner_execute_script_with_args ___________
            #
            # self = <pythoncommons.tests.test_process.ProcessTests testMethod=test_commandrunner_execute_script_with_args>
            #
            #     def test_commandrunner_execute_script_with_args(self):
            #         with tempfile.TemporaryDirectory() as tmpdirname:
            #             test_dir = self.get_test_dir(tmpdirname)
            #             output_file = FileUtils.join_path(test_dir, "testfile")
            #             script_path = ProcessTests.find_script(SCRIPT_WITH_ARGS_SH)
            #             script_parent_dir = FileUtils.get_parent_dir_name(script_path)
            #             script_name = os.path.basename(script_path)
            #
            #             args = f"arg1 arg2 arg3"
            #
            #             cli_cmd, cli_output = CommandRunner.execute_script(
            #                 script_name, args=args, working_dir=script_parent_dir, output_file=output_file, use_tee=True
            #             )
            #             file_contents = FileUtils.read_file(output_file)
            # >           self.assertEqual('arg: arg1\narg: arg2\narg: arg3', cli_output)
            # E           AssertionError: 'arg: arg1\narg: arg2\narg: arg3' != '/bin/sh: 1: script_with_args.sh: not found'
            # E           + /bin/sh: 1: script_with_args.sh: not found- arg: arg1
            # E           - arg: arg2
            # E           - arg: arg3
            #
            # pythoncommons/tests/test_process.py:166: AssertionError
            # ------------------------------ Captured log call -------------------------------
            # 2025-02-07 03:58:37,821 - INFO - pythoncommons.process - Running CLI command: cd /home/runner/work/python-commons/python-commons/pythoncommons/test-scripts;script_with_args.sh arg1 arg2 arg3 | tee /tmp/tmpmw81baze/test_commandrunner_execute_script_with_args-20250207_035837/testfile
            # 2025-02-07 03:58:37,822 - DEBUG - pythoncommons.tests.test_process - [AUDIT subprocess.Popen]: subprocess.Popen with args=('/bin/sh', ['/bin/sh', '-c', 'cd /home/runner/work/python-commons/python-commons/pythoncommons/test-scripts;script_with_args.sh arg1 arg2 arg3 | tee /tmp/tmpmw81baze/test_commandrunner_execute_script_with_args-20250207_035837/testfile'], None, None)
            cli_command += f"cd {working_dir};./{script}"
        else:
            cli_command += script
        if args:
            cli_command += " " + args
        if output_file:
            if use_tee:
                cli_command += f" | tee {output_file}"
            else:
                cli_command += f" > {output_file}"
        return CommandRunner.run_cli_command(cli_command)

    @staticmethod
    def run_cli_command(cli_command, fail_on_empty_output=True, print_command=True, fail_on_error=True):
        if print_command:
            LOG.info("Running CLI command: %s", cli_command)
        output = CommandRunner._getoutput(cli_command, raise_on_error=fail_on_error)
        if fail_on_empty_output and not output:
            # TODO Faulty format string: Search for all kinds of '%s' occurrences with ValueError
            raise ValueError("Command failed: %s", cli_command)
        return cli_command, output

    @staticmethod
    def _getoutput(command, raise_on_error=True):
        statusoutput = subprocess.getstatusoutput(command)
        if raise_on_error and statusoutput[0] != 0:
            raise ValueError(f"Command failed with exit code {statusoutput[0]}. Command was: {command}")
        return statusoutput[1]


LOG = logging.getLogger(__name__)
CONSOLE = logging.getLogger("console")


@dataclass
class RegularCommandResult:
    cli_cmd: str
    args: List[Any]
    stdout: str
    stderr: str
    exit_code: int


class SubprocessCommandRunner:
    @classmethod
    def run(
        cls,
        command,
        working_dir=None,
        log_stdout=False,
        log_stderr=False,
        log_command_result=False,
        fail_on_error=False,
        fail_message="",
        wait_after=0,
        wait_message="",
    ):
        if working_dir:
            FileUtils.change_cwd(working_dir)

        args = shlex.split(command)
        proc = subprocess.run(args, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        args2 = str(proc.args)

        if working_dir:
            FileUtils.reset_cwd()
        command_result = RegularCommandResult(command, args2, proc.stdout, proc.stderr, proc.returncode)

        if log_command_result:
            LOG.info("Command result: %s", command_result)
        if log_stdout:
            LOG.info("Stdout:\n %s", command_result.stdout)
        if log_stderr:
            LOG.info("Stderr:\n %s", command_result.stderr)

        if fail_on_error and command_result.exit_code != 0:
            if fail_message:
                LOG.error(fail_message)
            raise ValueError("Execution failed! Command was: {}".format(command))

        if wait_after > 0:
            LOG.info("Waiting for %d seconds %s", wait_message)
            time.sleep(wait_after)

    @classmethod
    def run_and_follow_stdout_stderr(
        cls,
        cmd,
        log_file=FileUtils.get_temp_file_name(),
        stdout_logger: Optional[logging.Logger] = None,
        exit_on_nonzero_exitcode=False,
    ):
        # TODO stderr is not logged at all
        if not stdout_logger:
            stdout_logger = LOG
        args = shlex.split(cmd)
        LOG.info(f"Running command: {cmd}")
        LOG.info(f"Command args: {args}")
        LOG.info(f"Config: Logging stderr to stdout, and stdout to logger. The logger is: {stdout_logger}")
        LOG.info(f"Config: Also logging to file: {log_file}")

        with open(log_file, "w") as f:
            # Redirect stderr to stdout
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            LOG.info(f"Returned process from subprocess.Popen: {process}")
            stdout_wrapper = io.TextIOWrapper(process.stdout, encoding="utf-8")
            for line in stdout_wrapper:
                line = line.strip()
                stdout_logger.info(line)
                f.write(line + os.linesep)
            stdout_wrapper.close()
            while process.poll() is None:
                LOG.info("Waiting for process to terminate...")
                time.sleep(2)
            LOG.info(f"Exit code of command '{cmd}' was: {process.returncode}")

            if exit_on_nonzero_exitcode and process.returncode != 0:
                LOG.error(f"Non-zero exit code was received while running command: {cmd}. Please check logs above.")
                sys.exit(process.returncode)
            return process


# TODO Warning: untested
class InteractiveCommandRunner:
    # https://intellij-support.jetbrains.com/hc/en-us/community/posts/360003383619-Pycharm-2019-termios-error-25-Inappropriate-ioctl-for-device-
    # In PyCharm, in Run configurations, this must be enabled: Emulate terminal in output console
    def run(self, command):
        if not command:
            raise ValueError("Command was empty or None!")

        LOG.info("Executing Command: " + str(command))
        CONSOLE.info("Command: " + str(command))
        # command = 'docker run -it --rm centos /bin/bash'.split()

        # save original tty setting then set it to raw mode
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        # open pseudo-terminal to interact with subprocess
        master_fd, slave_fd = pty.openpty()

        # use os.setsid() make it run in a new process group, or bash job control will not be enabled

        p = subprocess.Popen(
            command,
            preexec_fn=os.setsid,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            universal_newlines=True,
            shell=True,
        )

        while p.poll() is None:
            r, w, e = select.select([sys.stdin, master_fd], [], [])
            if sys.stdin in r:
                d = os.read(sys.stdin.fileno(), 10240)
                os.write(master_fd, d)
            elif master_fd in r:
                o = os.read(master_fd, 10240)
                if o:
                    os.write(sys.stdout.fileno(), o)

        # restore tty settings back
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

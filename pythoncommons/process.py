import io
from typing import Callable
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
from pythoncommons.string_utils import auto_str


class CommandRunner:
    
    def __init__(self, log):
        self.LOG = log
    
    def run_sync(self, cmd: str, fail_on_error: bool = False, single_result=True,
                 _out: str = None, _err: str = None, _tee: bool = False):
        def _prepare_kwargs(_err, _out, _tee):
            kwargs = {}
            if _out:
                kwargs['_out'] = _out
            if _err:
                kwargs['_err'] = _err
            if _tee:
                kwargs['_tee'] = True
            return kwargs

        self.LOG.info("Running command: {}".format(cmd))
        output = []
        exit_code = None
        try:
            kwargs = _prepare_kwargs(_err, _out, _tee)
            if "_out" not in kwargs:
                # TODO There were problems passing this lambda from _prepare_kwargs
                process = sh.bash("-c", cmd, **kwargs, _out=lambda line: output.append(line))
            else:
                process = sh.bash("-c", cmd, **kwargs)
            process.wait()
            exit_code = process.exit_code
        except sh.ErrorReturnCode as e:
            if fail_on_error:
                raise e
            return e.stdout, e.exit_code
        except Exception as e:
            self.LOG.error("Error while executing command {}:\n {}".format(cmd, str(e)))

        self.LOG.info(" ".join(output))
        # Remove trailing newlines from each line
        output = [line.rstrip() for line in output]
        if len(output) == 1 and single_result:
            output = output[0]

        return output, exit_code

    def run_async(self, cmd: str,
                  stdout_callback: Callable[[str], str] = None,
                  stderr_callback: Callable[[str], str] = None) -> Popen:
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


LOG = logging.getLogger(__name__)
CONSOLE = logging.getLogger("console")


@auto_str
# TODO convert this to dataclass
class RegularCommandResult:
    def __init__(self, cli_cmd, args, stdout, stderr, exit_code):
        self.cli_cmd = cli_cmd
        self.args = args
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class SubprocessCommandRunner:
    @classmethod
    def run(cls,
            command,
            working_dir=None,
            log_stdout=False,
            log_stderr=False,
            log_command_result=False,
            fail_on_error=False,
            fail_message="",
            wait_after=0,
            wait_message=""):
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
    def run_and_follow_stdout_stderr(cls, cmd, log_file='test.log',
                                     stdout_logger=None,
                                     exit_on_nonzero_exitcode=False):
        if not stdout_logger:
            stdout_logger = LOG
        args = shlex.split(cmd)
        LOG.info(f"Running command: {cmd}")
        LOG.info(f"Command args: {args}")

        with open(log_file, 'w') as f:
            # Redirect stderr to stdout
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            LOG.info(f"Returned process: {process}")
            for line in io.TextIOWrapper(process.stdout, encoding="utf-8"):
                line = line.strip()
                stdout_logger.info(line)
                f.write(line + os.linesep)
            while process.poll() is None:
                LOG.info("Waiting for process to terminate...")
                time.sleep(2)
            LOG.info(f"Exit code of command '{cmd}' was: {process.returncode}")

            if exit_on_nonzero_exitcode and process.returncode != 0:
                LOG.error(f"Error while running command: {cmd}. Please check logs above.")
                sys.exit(process.returncode)
            return process


#TODO Warning: untested
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

        p = subprocess.Popen(command,
                             preexec_fn=os.setsid,
                             stdin=slave_fd,
                             stdout=slave_fd,
                             stderr=slave_fd,
                             universal_newlines=True, shell=True)

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
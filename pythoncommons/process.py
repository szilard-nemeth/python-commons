
from typing import Callable
import subprocess
from subprocess import Popen
import sh


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

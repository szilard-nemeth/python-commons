import logging
import os
import re
import time
from enum import Enum
from typing import List, Tuple, Dict

import docker
from docker import APIClient
import json

from docker.errors import ImageNotFound

from pythoncommons.file_utils import FileUtils
from pythoncommons.process import SubprocessCommandRunner
from pythoncommons.string_utils import auto_str
from rich.progress import Progress

DEFAULT_DOCKERFILE_NAME = "Dockerfile"

LOG = logging.getLogger(__name__)


class DockerWrapper:
    try:
        client = APIClient(base_url="unix://var/run/docker.sock")
        # TODO Smarter way to detect this?
        # alternative path:
        #  client = APIClient(base_url="unix:///Users/snemeth/.docker/run/docker.sock")
    except Exception:
        LOG.exception(
            "Cannot connect to Docker daemon! "
            "This article might help: https://stackoverflow.com/a/74175227/1106893 "
            "Verify docker contexts with: docker context ls"
        )
        raise

    def __init__(self):
        pass

    @classmethod
    def create_image_from_dir(cls, dockerfile_parent_dir_path, tag=None, build_args=None):
        cls._build_image_internal(dockerfile_parent_dir_path, tag=tag, build_args=build_args)

    @classmethod
    def create_image_from_dockerfile(cls, dockerfile_name, tag=None, build_args=None):
        dockerfile_parent_dir_path = os.path.dirname(dockerfile_name)

        # Example: dockerfile_name = "Dockerfile" --> Path would be empty
        if not dockerfile_parent_dir_path:
            dockerfile_parent_dir_path = os.getcwd()
        dockerfile_name = os.path.basename(dockerfile_name)
        cls._build_image_internal(
            dockerfile_parent_dir_path, dockerfile_name=dockerfile_name, tag=tag, build_args=build_args
        )

    @classmethod
    def _build_image_internal(
            cls, dockerfile_parent_dir_path, dockerfile_name=DEFAULT_DOCKERFILE_NAME, tag=None, build_args=None
    ):
        if not build_args:
            build_args = {}
        LOG.info(
            "Starting to build Docker image from Dockerfile: %s, based on parent dir path: %s",
            dockerfile_name,
            dockerfile_parent_dir_path,
        )
        cls._fix_path_for_macos()
        response = [
            line
            for line in cls.client.build(
                path=dockerfile_parent_dir_path,
                dockerfile=dockerfile_name,
                rm=True,
                tag=tag,
                buildargs=build_args,
                network_mode="host",
            )
        ]
        errors = cls.log_response(response)
        if errors:
            raise ValueError(
                f"Failed to build Docker image from Dockerfile: {dockerfile_name}. " f"Error messages: {errors}"
            )

    @classmethod
    def _fix_path_for_macos(cls):
        # NOTE: To avoid docker.credentials.errors.InitializationError: docker-credential-osxkeychain
        # not installed or not available in PATH.
        # --> Must add /usr/local/bin/ to PATH on macosx platform
        current_path = os.environ["PATH"]
        if "/usr/local/bin" not in current_path:
            os.environ["PATH"] = current_path + ":/usr/local/bin"

    @classmethod
    def run_container(cls, image, volumes, sleep=300):
        client = docker.client.from_env()
        container = client.containers.run(image, "sleep {}".format(sleep), stderr=True, detach=True, volumes=volumes)
        return container

    @classmethod
    def inspect_container(cls, container_id: str):
        return docker.client.inspect_container(container_id)

    @classmethod
    def log_response(cls, response):
        errors = []
        for r in response:
            lines = r.decode().split("\r\n")
            for line in lines:
                if line:
                    line_dict = json.loads(line)
                    log_value = line_dict["stream"] if "stream" in line_dict else None
                    err_detail = line_dict["errorDetail"] if "errorDetail" in line_dict else None
                    if err_detail:
                        err_message = err_detail["message"]
                        errors.append(err_message)
                        LOG.error("[BUILD] %s", err_message)
                    if log_value and "ERROR" in log_value:
                        errors.append(log_value)
                    if log_value and (log_value != "\n"):
                        LOG.info("[BUILD] %s", log_value)
        return errors


class DockerMountMode(Enum):
    READ_WRITE = "rw"
    READ_ONLY = "ro"


@auto_str
class DockerMount:
    def __init__(self, host_dir, container_dir, mode=DockerMountMode.READ_WRITE):
        self.host_dir = host_dir
        self.container_dir = container_dir
        self.mode = mode


class DockerDiagnosticStdoutAssertionMode(Enum):
    EXACT_MATCH = "exact_match"
    SUBSTRING_MATCH = "substring_match"


class DockerDiagnosticPhase(Enum):
    PRE = "pre"
    POST = "post"


@auto_str
class DockerDiagnosticCommand:
    def __init__(
            self,
            mode,
            phase,
            command,
            expected_exit_code=0,
            expected_output=None,
            expected_output_fragments=None,
            strip=False,
    ):
        self.phase = phase
        self.mode = mode
        self.command = command
        self.expected_exit_code = expected_exit_code
        self.expected_output = expected_output
        self.expected_output_fragments = expected_output_fragments
        self.strip = strip

    @classmethod
    def create_exact_match(cls, phase, command, expected_output, expected_exit_code=0, strip=False):
        return cls(
            DockerDiagnosticStdoutAssertionMode.EXACT_MATCH,
            phase,
            command,
            expected_exit_code=expected_exit_code,
            expected_output=expected_output,
            strip=strip,
        )

    @classmethod
    def create_substring_match(cls, phase, command, expected_output_fragments, expected_exit_code=0, strip=False):
        return cls(
            DockerDiagnosticStdoutAssertionMode.SUBSTRING_MATCH,
            phase,
            command,
            expected_exit_code=expected_exit_code,
            expected_output_fragments=expected_output_fragments,
            strip=strip,
        )


class CreatePathMode(Enum):
    FULL_PATH = "FULL_PATH"
    PARENT_PATH = "PARENT_PATH"


class DockerPullProgress:
    def __init__(self, progress: Progress=None):
        self._progress = progress if progress else Progress()
        self._tasks = {} # key: image, value: rich task id
        self._image_to_number = {} # key: image, value: number of image
        self._image_counter = 1
        self._totals = {} # key: image, value: sum of 'total' counter of all layers of the image
        self._layer_data = {}
        self._seen_layers = set()

    def store_layer_data(self, image, layer, current, total):
        if image not in self._layer_data:
            self._layer_data[image] = {}
        if layer not in self._layer_data[image]:
            self._layer_data[image][layer] = {}
        self._layer_data[image][layer] = {'current': current, 'total': total}

    def get_completed_for_image(self, image):
        completed = 0
        for layer, data in self._layer_data[image].items():
            completed += data["current"]
        return completed

    def download_or_pull_description(self, image_name):
        return f'[red]Downloading {self._image_to_number[image_name]}]'

    def extracting_description(self, image_name):
        return f'[green][Extracting {self._image_to_number[image_name]}]'

    def capture_progress(self, image_name, line):
        """
        Message types:
         {'status': 'Downloading', 'progressDetail': {'current': 77701098, 'total': 693170420}, 'progress': '[=====>]   77.7MB/693.2MB', 'id': '7a9e0db762c8'}
         {'status': 'Extracting', 'progressDetail': {'current': 557056, 'total': 705917953}, 'progress': '[>        ]  557.1kB/705.9MB', 'id': '4091cbe1d60a'}
         {'status': 'Pull complete', 'progressDetail': {}, 'id': '6291dc4a3923'}
         {'status': 'Verifying Checksum', 'progressDetail': {}, 'id': '27cce364b293'}
         {'status': 'Download complete', 'progressDetail': {}, 'id': '4091cbe1d60a'}
         # {'status': 'Digest: sha256:2c24487226d01d3400f4e2ac050e2e8b1f23b0faad8c7030d37101be6571d175'}
        :param image_name:
        :param line:
        :return:
        """
        if "id" not in line:
            return

        if not image_name in self._image_to_number:
            self._image_to_number[image_name] = self._image_counter
            self._totals[image_name] = 0
            self._image_counter += 1

        layer = line["id"]
        status = line['status']
        if status in ("Downloading", "Pulling"):
            description = self.download_or_pull_description(image_name)
        elif status == "Extracting":
            description = self.extracting_description(image_name)
        else:
            # skip other statuses
            return

        total = line['progressDetail']['total']
        current = line['progressDetail']['current']
        self.store_layer_data(image_name, layer, current, total)
        if layer not in self._seen_layers:
            self._seen_layers.add(layer)
            self._totals[image_name] += total

        if image_name not in self._tasks.keys():
            self._tasks[image_name] = self._progress.add_task(description, total=self._totals[image_name], completed=self.get_completed_for_image(image_name))
        else:
            self._progress.update(self._tasks[image_name], total=self._totals[image_name], completed=self.get_completed_for_image(image_name))

    def rich_progress(self):
        return self._progress



class DockerTestSetup:
    def __init__(self, image_name, create_image=False, dockerfile_parent_dir_path=None, dockerfile=None, logger=None):
        self.image_name = image_name
        if create_image:
            if dockerfile_parent_dir_path:
                self.create_image(dockerfile_parent_dir_path=dockerfile_parent_dir_path)
            elif dockerfile:
                DockerWrapper.create_image_from_dockerfile(dockerfile, tag=self.image_name)

        if logger:
            self.CMD_LOG = logger
        else:
            self.CMD_LOG = LOG

        # Assigned later
        self._reinit()

    def _reinit(self):
        self.pre_diagnostics: List[DockerDiagnosticCommand] = []
        self.post_diagnostics: List[DockerDiagnosticCommand] = []
        self.test_instance = None
        self.mounts: List[DockerMount] = []
        self.container = None

    def cleanup(self):
        self._reinit()

    def create_image(self, dockerfile_parent_dir_path=None):
        if not dockerfile_parent_dir_path:
            dockerfile_parent_dir_path = os.getcwd()
            LOG.warning(
                f"Dockerfile location was not specified. "
                f"Trying to create image from current working directory: {dockerfile_parent_dir_path}"
            )
        DockerWrapper.create_image_from_dir(dockerfile_parent_dir_path, tag=self.image_name)

    def mount_dir(self, host_dir, container_dir, mode=DockerMountMode.READ_WRITE):
        self.mounts.append(DockerMount(host_dir, container_dir, mode=mode))

    def apply_mounts(self, docker_mounts: List[DockerMount]):
        self.mounts.extend(docker_mounts)

    def print_mounts(self):
        LOG.info("Docker mounts: %s", self.mounts)

    def add_diagnostics(self, diags: List[DockerDiagnosticCommand]):
        for diag in diags:
            if diag.phase == DockerDiagnosticPhase.PRE:
                self.pre_diagnostics.append(diag)
            elif diag.phase == DockerDiagnosticPhase.POST:
                self.post_diagnostics.append(diag)

    def run_container(self, commands_to_run: List[str] = None,
                      sleep=300,
                      capture_progress=False,
                      print_progress=False,
                      progress: Progress=None):
        if not commands_to_run:
            commands_to_run = []
        if not capture_progress and progress:
            capture_progress = True

        volumes_dict = self._create_volumes_dict()

        if capture_progress:
            client = docker.client.from_env()
            try:
                container = client.containers.create(image=self.image_name, command="sleep 1", detach=True)
            except ImageNotFound:
                resp = client.api.pull(self.image_name, stream=True, decode=True)
                progress = DockerPullProgress(progress) if progress else DockerPullProgress()
                for line in resp:
                    progress.capture_progress(self.image_name, line)
                    if print_progress:
                        self.CMD_LOG.info(f"[{self.image_name}] {line}")


        LOG.info(f"Starting container from image '{self.image_name}' with volumes: '{volumes_dict}'")
        self.container = DockerWrapper.run_container(image=self.image_name, volumes=volumes_dict, sleep=sleep)

        if self.pre_diagnostics:
            self._run_pre_diagnostic_commands()

        for cmd in commands_to_run:
            self.exec_cmd_in_container(cmd)

        if self.post_diagnostics:
            self._run_post_diagnostic_commands()
        return self.container

    def _create_volumes_dict(self):
        # Convert DockerMount objects to volumes dictionary
        volumes_dict = {}
        for mount in self.mounts:
            volumes_dict[mount.host_dir] = {"bind": mount.container_dir, "mode": mount.mode.value}
        return volumes_dict

    def _run_pre_diagnostic_commands(self):
        self._run_diagnostic_command(DockerDiagnosticPhase.PRE)

    def _run_post_diagnostic_commands(self):
        self._run_diagnostic_command(DockerDiagnosticPhase.POST)

    def _run_diagnostic_command(self, phase):
        diag_command_objs: List[DockerDiagnosticCommand] = (
            self.pre_diagnostics if phase == DockerDiagnosticPhase.PRE else self.post_diagnostics
        )
        LOG.debug("Running diagnostic commands in '%s' phase: %s", phase.value, diag_command_objs)
        for diag in diag_command_objs:
            if diag.mode == DockerDiagnosticStdoutAssertionMode.EXACT_MATCH:
                self.exec_diagnostic_command(diag)
            elif diag.mode == DockerDiagnosticStdoutAssertionMode.SUBSTRING_MATCH:
                self.exec_command_and_grep_in_stdout(diag)

    def exec_diagnostic_command(self, diag: DockerDiagnosticCommand):
        # TODO Seems like stdout is not returned anymore :(
        exit_code, stdout = self.exec_cmd_in_container(diag.command, strip=diag.strip)
        self.test_instance.assertEqual(
            diag.expected_exit_code,
            exit_code,
            msg="Exit code of command is not the expected. " f"Command details: {diag}",
        )
        if diag.strip:
            diag.expected_output = diag.expected_output.strip()
        self.test_instance.assertEqual(
            diag.expected_output, stdout, msg="Stdout of command is not the expected. " f"Command details: {diag}"
        )

    def exec_command_and_grep_in_stdout(self, diag: DockerDiagnosticCommand):
        # TODO Seems like stdout is not returned anymore :(
        exit_code, stdout = self.exec_cmd_in_container(diag.command, strip=diag.strip)
        self.test_instance.assertEqual(
            diag.expected_exit_code,
            exit_code,
            msg="Exit code of command is not the expected." f"Command details: {diag}",
        )

        for fragment in diag.expected_output_fragments:
            self.test_instance.assertTrue(
                fragment in stdout,
                msg="Cannot find expected fragment in stdout. "
                    f"Fragment: {fragment}, stdout: {stdout}, Command details: '{diag}'",
                )

    def generate_dummy_text_files_in_container_dirs(self, dir_and_no_of_files: List[Tuple[str, int]]):
        for dir_files in dir_and_no_of_files:
            self._generate_dummy_text_files_in_container_dir(dir_files[0], dir_files[1])

    def _generate_dummy_text_files_in_container_dir(self, dir_path: str, number_of_files: int):
        self.exec_cmd_in_container("mkdir -p " + dir_path)
        for i in range(number_of_files):
            path = os.path.normpath(dir_path)
            path_segments = path.split(os.sep)
            path_segments = list(filter(None, path_segments))
            file_name = "_".join(path_segments) + "_" + str(i + 1)
            file_path = FileUtils.join_path(dir_path, file_name)
            cmd = f"echo dummy_{str(i + 1)} > {file_path}"
            # Simple redirect did not work: self._exec_cmd_in_container(cmd)
            # See: https://github.com/docker/docker-py/issues/1637
            # Use this as a workaround
            self.exec_cmd_in_container(["sh", "-c", cmd])

    def exec_cmd_in_container(
            self,
            cmd,
            charset="utf-8",
            strip=True,
            fail_on_error=True,
            stdin=False,
            tty=False,
            env: Dict[str, str] = None,
            detach=False,
            callback=None,
            stream=False,
            strict: bool = True,
    ):
        if not env:
            env = {}
        if strict:
            if not stream and callback:
                raise ValueError(
                    "Callback is specified but streaming mode is not enabled! Callback only makes sense if streaming mode is active!"
                )

        # https://stackoverflow.com/questions/29663459/python-app-does-not-print-anything-when-running-detached-in-docker
        env["PYTHONUNBUFFERED"] = "1"
        LOG.info(f"Running command '{cmd}' in container: '{self.container}'")
        exec_handler = DockerWrapper.client.exec_create(self.container.id, cmd, environment=env, stdin=stdin, tty=tty)
        ret = DockerWrapper.client.exec_start(exec_handler, stream=stream, detach=detach)

        # If stream=True, the execution will stay in _get_output_of_cmd until there's data to read from the output.
        # This means that when the loop that reads the output ends, the process is finished.
        # Therefore, handle stream mode separately.
        if not stream:
            self._get_and_verify_exit_code(callback, charset, cmd, exec_handler, fail_on_error, ret, stream, strip)

        if detach:
            exit_code: int = self._get_exit_code(cmd, exec_handler, stream)
            return exit_code, None

        decoded_stdout = self._get_output_of_cmd(cmd, ret, callback, charset, strip, stream)
        exit_code = self._get_and_verify_exit_code(
            callback, charset, cmd, exec_handler, fail_on_error, ret, stream, strip
        )
        return exit_code, decoded_stdout

    def _get_and_verify_exit_code(self, callback, charset, cmd, exec_handler, fail_on_error, ret, stream, strip):
        exit_code: int = self._get_exit_code(cmd, exec_handler, stream)
        if fail_on_error and exit_code != 0:
            _ = self._get_output_of_cmd(cmd, ret, callback, charset, strip, stream)
            raise ValueError(
                f"Command '{cmd}' returned with non-zero exit code: {exit_code}. See logs above for more details."
            )
        return exit_code

    def _get_output_of_cmd(self, cmd, ret, callback, charset, strip, stream):
        LOG.info(f"Listing stdout of cmd: {cmd}...")
        short_cmd = os.path.basename(cmd).rstrip()
        decoded_stdout = None

        if not stream:
            if ret:
                decoded_stdout = ret.decode(charset)
                if strip:
                    decoded_stdout = decoded_stdout.strip()
                self.CMD_LOG.info(f"[{short_cmd}] {decoded_stdout}")
                return decoded_stdout
            else:
                LOG.warning("Output was None")
                return None

        for output in ret:
            try:
                decoded_stdout = output.decode(charset)
                if strip:
                    decoded_stdout = decoded_stdout.strip()
                self.CMD_LOG.info(f"[{short_cmd}] {decoded_stdout}")
                if callback:
                    callback(cmd, decoded_stdout, self)
            except UnicodeDecodeError:
                LOG.error(f"Error while decoding string: {output.decode('cp437')}")
        return decoded_stdout

    @staticmethod
    def _get_exit_code(cmd: str, exec_handler, max_wait_seconds: int = 5):
        """
        client.exec_inspect(exec_handler["Id"]).get("ExitCode") does not immediately returns the exit code.
        Try to wait for it for some time.
        :param exec_handler:
        :return:
        """
        slept_seconds = 0
        while True:
            exit_code: int = DockerWrapper.client.exec_inspect(exec_handler["Id"]).get("ExitCode")
            LOG.debug("Command: '%s', exit code: %s", cmd, exit_code)
            if exit_code is not None:
                return exit_code
            else:
                LOG.debug("Commnand: '%s', exit code is still None. Sleeping 1s...")
                time.sleep(1)
                slept_seconds += 1
            if slept_seconds == max_wait_seconds:
                return None

    def inspect_container(self, container_id: str):
        return DockerWrapper.inspect_container(container_id)

    def docker_cp_from_container(self, container_path, local_target_path):
        command = f"docker cp {self.container.id}:{container_path} {local_target_path}"
        LOG.info(
            "Copying container directory '%s' to local directory '%s' (container id: %s). Command was: %s",
            container_path,
            local_target_path,
            self.container.id,
            command,
        )
        SubprocessCommandRunner.run_and_follow_stdout_stderr(command)

    def docker_cp_to_container(
            self,
            container_target_path,
            local_src_file,
            create_container_path_mode: CreatePathMode = None,
            double_check_with_ls: bool = False,
    ):
        # run mkdir -p if dir not exist
        self.create_directories_in_container(container_target_path, create_container_path_mode)
        command = f"docker cp {local_src_file} {self.container.id}:{container_target_path}"
        LOG.info(
            "Copying local directory '%s' to container directory '%s' (container id: %s). Command was: %s",
            local_src_file,
            container_target_path,
            self.container.id,
            command,
        )
        SubprocessCommandRunner.run_and_follow_stdout_stderr(command)
        if double_check_with_ls:
            self.exec_cmd_in_container(f"ls -la {container_target_path}")

    def create_directories_in_container(self, container_target_path: str, create_container_path_mode: CreatePathMode):
        if not create_container_path_mode:
            LOG.warning("Will not create directories as create_container_path_mode=%s", create_container_path_mode)
            return
        if create_container_path_mode:
            if create_container_path_mode == CreatePathMode.PARENT_PATH:
                path_to_create = FileUtils.basename(container_target_path)
                exit_code, _ = self.exec_cmd_in_container(f"ls {path_to_create}", fail_on_error=False)
            elif create_container_path_mode == CreatePathMode.FULL_PATH:
                path_to_create = container_target_path
                exit_code, _ = self.exec_cmd_in_container(f"ls {path_to_create}", fail_on_error=False)
            else:
                raise ValueError("Unknown create path mode: {}".format(create_container_path_mode))

            if exit_code != 0:
                self.create_dirs_in_container(path_to_create)

    def create_dirs_in_container(self, path_to_create):
        LOG.debug("Creating directories (recursive) '%s' in container '%s'", path_to_create, self.container.id)
        exit_code, _ = self.exec_cmd_in_container(f"mkdir -p {path_to_create}")
        if exit_code != 0:
            raise ValueError(
                "Failed to create directories '{}' in container {}".format(path_to_create, self.container.id)
            )


class DockerFileReplacer:
    vars_to_replace = {}

    # https://stackoverflow.com/a/30777398/1106893
    @classmethod
    def replace_all_vars(cls, input, vars_to_replace, default=None, skip_escaped=False):
        """Expand environment variables of form $var and ${var}.
        If parameter 'skip_escaped' is True, all escaped variable references
        (i.e. preceded by backslashes) are skipped.
        Unknown variables are set to 'default'. If 'default' is None,
        they are left unchanged.
        """
        cls.vars_to_replace = vars_to_replace

        def replace_var(m):
            # m.group(0) -> '${VAR}'
            # m.group(1) -> '{VAR}'
            # m.group(2) -> 'VAR'
            varname = m.group(2) or m.group(1)
            replaced_name = (
                DockerFileReplacer.vars_to_replace[varname] if varname in DockerFileReplacer.vars_to_replace else None
            )
            if not replaced_name:
                if default:
                    replaced_name = default
                else:
                    replaced_name = m.group(0)

            return replaced_name

        pattern = (r"(?<!\\)" if skip_escaped else "") + r"\$(\w+|\{([^}]*)\})"
        result = re.sub(pattern, replace_var, input)
        cls.vars_to_replace = {}

        # TODO print all remainder lines matching pattern -> Unresolved variables (LOG warning)
        # e.g. ${PYTHONPATH}
        return result

    @classmethod
    def add_env_var_declaration(cls, dockerfile_contents, var_name):
        lines = dockerfile_contents.split("\n")
        mod_lines = []
        for line in lines:
            if line.startswith("FROM"):
                mod_lines.append(line)
                mod_lines.append("ARG {var}".format(var=var_name))
                mod_lines.append('RUN echo "{var} = ${var}"'.format(var=var_name))
            else:
                mod_lines.append(line)

        return "\n".join(mod_lines)


class DockerCompose:
    COMPOSE_FILE_TEMPLATE = "docker-compose{profile}.yml"

    @staticmethod
    def up(working_dir, profile="", wait=0):
        if profile:
            profile = "-" + profile
        compose_file = DockerCompose.COMPOSE_FILE_TEMPLATE.format(profile=profile)
        command = "docker-compose -f {cfile} up -d".format(cfile=compose_file)
        SubprocessCommandRunner.run(
            command,
            working_dir=working_dir,
            log_command_result=True,
            fail_on_error=True,
            wait_after=10,
            wait_message="for docker compose command",
        )

    @staticmethod
    def logs(working_dir):
        command = "docker-compose logs"
        SubprocessCommandRunner.run(command, working_dir=working_dir, log_stdout=True)

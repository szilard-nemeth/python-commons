import logging
import os
from enum import Enum
from typing import List, Tuple, Dict

import docker
from docker import APIClient
import json
from pythoncommons.file_utils import FileUtils
from pythoncommons.string_utils import auto_str

MOUNT_MODE_RW = "rw"
LOG = logging.getLogger(__name__)


class DockerWrapper:
    client = APIClient(base_url='unix://var/run/docker.sock')

    def __init__(self):
        pass

    @classmethod
    def create_image_from_dir(cls, dockerfile_dir_path, tag=None, build_args=None):
        dockerfile_path = FileUtils.join_path(dockerfile_dir_path, "Dockerfile")
        cls._build_image_internal(dockerfile_dir_path, dockerfile_path, tag=tag, build_args=build_args)

    @classmethod
    def create_image_from_dockerfile(cls, docker_file, tag=None, build_args=None):
        parent_dir = os.path.dirname(docker_file)
        cls._build_image_internal(parent_dir, docker_file, tag=tag, build_args=build_args)

    @classmethod
    def _build_image_internal(cls, dockerfile_dir_path, dockerfile_path, tag=None, build_args=None):
        if not build_args:
            build_args = {}
        LOG.info(f"Starting to build Docker image from Dockerfile: {dockerfile_path}, based on parent dir path.")
        cls._fix_path_for_macos()
        response = [line for line in cls.client.build(
            path=dockerfile_dir_path, rm=True, tag=tag, buildargs=build_args, network_mode='host')]
        errors = cls.log_response(response)
        if errors:
            raise ValueError(f"Failed to build Docker image from Dockerfile: {dockerfile_path}. "
                             f"Error messages: {errors}")

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
    def log_response(cls, response):
        errors = []
        for r in response:
            lines = r.decode().split('\r\n')
            for line in lines:
                if line:
                    line_dict = json.loads(line)
                    log_value = line_dict['stream'] if 'stream' in line_dict else None
                    err_detail = line_dict['errorDetail'] if 'errorDetail' in line_dict else None
                    if err_detail:
                        err_message = err_detail["message"]
                        errors.append(err_message)
                        LOG.error("[BUILD] %s", err_message)
                    if log_value and "ERROR" in log_value:
                        errors.append(log_value)
                    if log_value and (log_value != '\n'):
                        LOG.info("[BUILD] %s", log_value)
        return errors



class DockerMount:
    def __init__(self, host_dir, container_dir, mode=MOUNT_MODE_RW):
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
    def __init__(self, mode, phase, command, expected_exit_code=0,
                 expected_output=None,
                 expected_output_fragments=None,
                 strip=False):
        self.phase = phase
        self.mode = mode
        self.command = command
        self.expected_exit_code = expected_exit_code
        self.expected_output = expected_output
        self.expected_output_fragments = expected_output_fragments
        self.strip = strip

    @classmethod
    def create_exact_match(cls, phase, command, expected_output, expected_exit_code=0, strip=False):
        return cls(DockerDiagnosticStdoutAssertionMode.EXACT_MATCH, phase, command,
                   expected_exit_code=expected_exit_code,
                   expected_output=expected_output,
                   strip=strip)

    @classmethod
    def create_substring_match(cls, phase, command, expected_output_fragments, expected_exit_code=0, strip=False):
        return cls(DockerDiagnosticStdoutAssertionMode.SUBSTRING_MATCH, phase, command,
                   expected_exit_code=expected_exit_code,
                   expected_output_fragments=expected_output_fragments,
                   strip=strip)


class DockerTestSetup:
    def __init__(self, image_name, create_image=False, dockerfile_location=None, logger=None):
        self.image_name = image_name
        if create_image:
            self.create_image(dockerfile_location=dockerfile_location)

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
        self.mounts = []
        self.container = None

    def cleanup(self):
        self._reinit()

    def create_image(self, dockerfile_location=None):
        if dockerfile_location:
            location = dockerfile_location
        else:
            location = os.getcwd()
            LOG.warning(f"Dockerfile location was not specified. "
                        f"Trying to create image from current working directory: {location}")
        DockerWrapper.create_image_from_dir(location, tag=self.image_name)

    def mount_dir(self, host_dir, container_dir, mode=MOUNT_MODE_RW):
        self.mounts.append(DockerMount(host_dir, container_dir, mode=mode))

    def add_diagnostics(self, diags: List[DockerDiagnosticCommand]):
        for diag in diags:
            if diag.phase == DockerDiagnosticPhase.PRE:
                self.pre_diagnostics.append(diag)
            elif diag.phase == DockerDiagnosticPhase.POST:
                self.post_diagnostics.append(diag)

    def run_container(self, commands_to_run: List[str] = None, sleep=300):
        if not commands_to_run:
            commands_to_run = []

        volumes_dict = self._create_volumes_dict()
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
            volumes_dict[mount.host_dir] = {'bind': mount.container_dir, 'mode': mount.mode}
        return volumes_dict

    def _run_pre_diagnostic_commands(self):
        self._run_diagnostic_command(DockerDiagnosticPhase.PRE)

    def _run_post_diagnostic_commands(self):
        self._run_diagnostic_command(DockerDiagnosticPhase.POST)

    def _run_diagnostic_command(self, phase):
        diag_command_objs: List[DockerDiagnosticCommand] = self.pre_diagnostics \
            if phase == DockerDiagnosticPhase.PRE else \
            self.post_diagnostics
        LOG.debug("Running diagnostic commands in '%s' phase: %s", phase.value, diag_command_objs)
        for diag in diag_command_objs:
            if diag.mode == DockerDiagnosticStdoutAssertionMode.EXACT_MATCH:
                self.exec_diagnostic_command(diag)
            elif diag.mode == DockerDiagnosticStdoutAssertionMode.SUBSTRING_MATCH:
                self.exec_command_and_grep_in_stdout(diag)

    def exec_diagnostic_command(self, diag: DockerDiagnosticCommand):
        exit_code, stdout = self.exec_cmd_in_container(diag.command, strip=diag.strip)
        self.test_instance.assertEqual(diag.expected_exit_code, exit_code,
                                       msg="Exit code of command is not the expected. "
                                           f"Command details: {diag}")
        if diag.strip:
            diag.expected_output = diag.expected_output.strip()
        self.test_instance.assertEqual(diag.expected_output, stdout,
                                       msg="Stdout of command is not the expected. "
                                           f"Command details: {diag}")

    def exec_command_and_grep_in_stdout(self, diag: DockerDiagnosticCommand):
        exit_code, stdout = self.exec_cmd_in_container(diag.command, strip=diag.strip)
        self.test_instance.assertEqual(diag.expected_exit_code, exit_code,
                                       msg="Exit code of command is not the expected."
                                           f"Command details: {diag}")

        for fragment in diag.expected_output_fragments:
            self.test_instance.assertTrue(fragment in stdout,
                                          msg="Cannot find expected fragment in stdout. "
                                              f"Fragment: {fragment}, stdout: {stdout}, Command details: '{diag}'")

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
            self.exec_cmd_in_container(['sh', '-c', cmd])

    def exec_cmd_in_container(self, cmd, charset="utf-8", strip=True, fail_on_error=True,
                               stdin=False,
                               tty=False,
                               env: Dict[str, str] = None,
                               detach=False,
                               callback=None, stream=True):
        if not env:
            env = {}

        # https://stackoverflow.com/questions/29663459/python-app-does-not-print-anything-when-running-detached-in-docker
        env["PYTHONUNBUFFERED"] = "1"
        LOG.info(f"Running command '{cmd}' in container: '{self.container}'")
        exec_handler = DockerWrapper.client.exec_create(self.container.id, cmd, environment=env, stdin=stdin, tty=tty)
        ret = DockerWrapper.client.exec_start(exec_handler, stream=stream, detach=detach)

        if not stream:
            if ret:
                return ret.decode(charset)
            else:
                LOG.warning("Return value was None")
                return None

        if detach:
            return None

        LOG.info(f"Listing stdout of cmd: {cmd}...")
        short_cmd = os.path.basename(cmd).rstrip()
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

        exit_code = DockerWrapper.client.exec_inspect(exec_handler['Id']).get('ExitCode')
        if fail_on_error and exit_code != 0:
            raise ValueError(f"Command '{cmd}' returned with non-zero exit code: {exit_code}. See logs above for more details.")
        return exit_code

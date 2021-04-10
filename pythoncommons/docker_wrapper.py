import logging
import os

import docker
from docker import APIClient
import json

LOG = logging.getLogger(__name__)


class DockerWrapper:
    client = APIClient(base_url='unix://var/run/docker.sock')

    def __init__(self):
        pass

    @classmethod
    def create_image(cls, dockerfile_dir_path, tag=None, build_args=None):
        if not build_args:
            build_args = {}
        dockerfile_path = dockerfile_dir_path + "/Dockerfile"
        LOG.info("Starting to build Docker image from Dockerfile: %s", dockerfile_path)

        # Can't combine path and fileobj together.
        # The only way to replace env vars in Dockerfile is to replace + copy Dockerfile back into repo root
        # to avoid issues with Dockerfile like it cannot find files to add to image from build directory

        # NOTE: To avoid docker.credentials.errors.InitializationError: docker-credential-osxkeychain
        # not installed or not available in PATH.
        # --> Must add /usr/local/bin/ to PATH on macosx platform
        current_path = os.environ["PATH"]
        if "/usr/local/bin" not in current_path:
            os.environ["PATH"] = current_path + ":" + "/usr/local/bin"
        response = [line for line in cls.client.build(path=dockerfile_dir_path, rm=True, tag=tag, buildargs=build_args, network_mode='host')]
        errors = cls.log_response(response)
        if errors:
            raise ValueError("Failed to build Docker image from Dockerfile: {}. Error messages: {}".format(dockerfile_path, errors))

    @classmethod
    def run_container(cls, image, volumes, delay=300):
        client = docker.client.from_env()
        container = client.containers.run(image, "sleep {}".format(delay), stderr=True, detach=True, volumes=volumes)
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

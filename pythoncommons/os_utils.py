import logging
import os
import sys

# TODO rename to SystemUtils?
PASSWORD_PREFIX = "password "
LOG = logging.getLogger(__name__)


class OsUtils:
    @staticmethod
    def get_env_value(env_name, default_value=None, suppress=False):
        if env_name in os.environ:
            env_value = os.environ[env_name]
            if not suppress:
                LOG.debug("Value of env variable '%s': %s", env_name, env_value)
        else:
            env_value = default_value
            if not suppress:
                LOG.debug("Value of env variable '%s' is not defined, using default value of: %s", env_name, env_value)
        return env_value

    @staticmethod
    def determine_full_command():
        return " ".join(sys.argv)

    @staticmethod
    def determine_full_command_filtered(filter_password=False):
        full_command = " ".join(sys.argv)
        if filter_password:
            split_res = full_command.split(PASSWORD_PREFIX)
            if len(split_res) == 1:
                # Password not found, return full command
                return full_command
            # Chop the first word from the 2nd string, that word should be the password.
            return split_res[0] + f"{PASSWORD_PREFIX}****** " + " ".join(split_res[1].split(" ")[1:])
        else:
            return full_command

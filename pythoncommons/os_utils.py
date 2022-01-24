import logging
import os
import sys

# TODO rename to SystemUtils?
from typing import Dict, List

PASSWORD_PREFIX = "password "
LOG = logging.getLogger(__name__)


class OsUtils:
    ENV_UPDATES: Dict[str, str] = {}
    TRACK_UPDATES = False

    @classmethod
    def track_env_updates(cls):
        cls.TRACK_UPDATES = True

    @classmethod
    def stop_tracking_updates(cls, clear_updates_dict=False):
        cls.TRACK_UPDATES = False
        if clear_updates_dict:
            cls.ENV_UPDATES.clear()

    @classmethod
    def get_tracked_updates(cls) -> Dict[str, str]:
        return dict(cls.ENV_UPDATES)

    @classmethod
    def get_env_value(cls, env_name, default_value=None, suppress=False):
        if env_name in os.environ:
            env_value = os.environ[env_name]
            if not suppress:
                LOG.debug("Value of env variable '%s': %s", env_name, env_value)
        else:
            env_value = default_value
            if not suppress:
                LOG.debug("Value of env variable '%s' is not defined, using default value of: %s", env_name, env_value)
        return env_value

    @classmethod
    def set_env_value(cls, env_name, env_value, suppress=False):
        if env_name in os.environ:
            old_value = os.environ[env_name]
            if not suppress:
                LOG.debug(
                    "Setting value of env variable '%s' to : %s. Old value was: %s", env_name, env_value, old_value
                )
        else:
            if isinstance(env_value, bool):
                env_value = str(env_value)
            if not suppress:
                LOG.debug("Setting value of env variable '%s' to : %s", env_name, env_value)
        if cls.TRACK_UPDATES:
            cls.ENV_UPDATES[env_name] = env_value
        os.environ[env_name] = env_value

    @classmethod
    def clear_env_vars(cls, vars: List[str]):
        for var in vars:
            if var in os.environ:
                LOG.debug("Removing env variable '%s'", var)
                del os.environ[var]

    @classmethod
    def is_env_var_true(cls, env_var_name, default_val):
        env_var_value = OsUtils.get_env_value(env_var_name, default_val)
        if env_var_value is None:
            raise ValueError("Env var value should not be None for env var name: '{}'".format(env_var_name))
        return env_var_value == "True" or env_var_value is True

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


class EnvironmentValidator:
    @staticmethod
    def validate_env_vars(env_vars, action=sys.exit, action_params=1, logger=LOG):
        for env_var in env_vars:
            if not os.getenv(env_var):
                logger.error("env var '%s' is not defined! Calling action: '%s(%s)'", env_var, action, action_params)
                action(action_params)

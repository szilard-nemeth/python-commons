import os
import sys

# TODO rename to SystemUtils?
PASSWORD_PREFIX = "password "


class OsUtils:
    @staticmethod
    def get_env_value(env_name, default_value=None):
        if env_name in os.environ:
            return os.environ[env_name]
        else:
            return default_value

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

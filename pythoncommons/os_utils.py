import os


class OsUtils:
    @staticmethod
    def get_env_value(env_name, default_value=None):
        if env_name in os.environ:
            return os.environ[env_name]
        else:
            return default_value
import os


class OsUtils:
    def get_env_value(self, env_name, default_value=None):
        if env_name in os.environ:
            return os.environ[env_name]
        else:
            return default_value
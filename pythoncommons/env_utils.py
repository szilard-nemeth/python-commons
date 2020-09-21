import logging
import os
import sys
LOG = logging.getLogger(__name__)


class EnvironmentValidator:
    @staticmethod
    def validate_env_vars(env_vars, action=sys.exit, action_params=1, logger=LOG):
        for env_var in env_vars:
            if not os.getenv(env_var):
                logger.error("env var '%s' is not defined! Calling action: '%s(%s)'", env_var, action, action_params)
                action(action_params)
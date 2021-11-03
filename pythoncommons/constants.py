from enum import Enum

PROJECT_NAME = "pythoncommons"
REPO_ROOT_DIRNAME = "python-commons"


class ExecutionMode(Enum):
    PRODUCTION = "prod"
    TEST = "test"
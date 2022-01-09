import os
import sys


class PyTestUtils:
    @staticmethod
    def is_pytest_execution():
        if "pytest" in sys.modules and "PYTEST_CURRENT_TEST" in os.environ:
            return True
        return False

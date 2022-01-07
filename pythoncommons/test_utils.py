import sys


class PyTestUtils:
    @staticmethod
    def is_pytest_execution():
        if "pytest" in sys.modules:
            return True
        return False

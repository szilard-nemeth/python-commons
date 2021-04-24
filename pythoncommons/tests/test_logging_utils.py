import unittest
import logging
import sys

from pythoncommons.logging_utils import LoggerFactory, COLLECTION_PLACEHOLDER

TESTLOGGER_INFO = "INFO:testLogger:"
TESTLOGGER_DEBUG = "DEBUG:testLogger:"


def double_coll(coll):
    coll *= 2
    return f"{str(coll)}"


class LoggingUtilsTests(unittest.TestCase):

    def test_many_strings(self):
        # format="%(message)s"
        logging.basicConfig(stream=sys.stdout, level=logging.WARN)

        with self.assertLogs('testLogger', level='INFO') as cm:
            logger = LoggerFactory.get_logger("testLogger")
            logger.setLevel(logging.WARN)
            logger.combined_log("testInfo0", ["a1", "a2"])

            logger.setLevel(logging.INFO)
            logger.combined_log("testInfo1...|", ["a1", "a2"])
            logger.combined_log(f"te {COLLECTION_PLACEHOLDER} stInfo2...", ["a1", "a2", "a3"])

            logger.setLevel(logging.DEBUG)
            logger.combined_log("testDebug1...", ["a1", "a2"])
            logger.combined_log(f"te {COLLECTION_PLACEHOLDER} stDebug2...", ["a1", "a2", "a3"])
            logger.combined_log(f"te {COLLECTION_PLACEHOLDER} stDebug3...", ["a1", "a2", "a3", "a4"], debug_coll_func=double_coll)

            self.assertEqual(cm.output, [self.logger_info_msg("testInfo1...| 2"),
                                         self.logger_info_msg("te 3 stInfo2..."),

                                         self.logger_info_msg("testDebug1... 2"),
                                         self.logger_debug_msg("testDebug1... ['a1', 'a2']"),

                                         self.logger_info_msg("te 3 stDebug2..."),
                                         self.logger_debug_msg("te ['a1', 'a2', 'a3'] stDebug2..."),

                                         self.logger_info_msg("te 4 stDebug3..."),
                                         self.logger_debug_msg("te ['a1', 'a2', 'a3', 'a4', "
                                                                   "'a1', 'a2', 'a3', 'a4'] stDebug3...")
                                         ])

    def logger_info_msg(self, msg):
        return f"{TESTLOGGER_INFO}{msg}"

    def logger_debug_msg(self, msg):
        return f"{TESTLOGGER_DEBUG}{msg}"








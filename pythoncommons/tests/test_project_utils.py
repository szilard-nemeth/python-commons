import contextlib
import logging
import os
import site
import subprocess
import sys
import tempfile
import unittest
import sys
from pythoncommons.file_utils import FileUtils, FindResultType
from pythoncommons.process import SubprocessCommandRunner
from pythoncommons.project_utils import SimpleProjectUtils

LOG = logging.getLogger(__name__)
PROJECT_NAME = "pythoncommons"
REPO_ROOT_DIRNAME = "python-commons"
REPO_ROOT_DIR = FileUtils.find_repo_root_dir(__file__, REPO_ROOT_DIRNAME)


def get_test_scripts_dir():
    return SimpleProjectUtils.get_project_dir(basedir=REPO_ROOT_DIR,
                                              parent_dir="tests",
                                              dir_to_find="test-scripts",
                                              find_result_type=FindResultType.DIRS)


TEST_SCRIPTS_DIR = get_test_scripts_dir()


class ProjectUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, force=True)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        testlogger = logging.getLogger(__name__)
        self.assertTrue(root_logger.handlers, msg="No handlers configured on root logger")

    def test_executing_script_from_uncommon_directory(self):
        with self._copy_script_to_temp_dir("hello_world_simple.py") as tup:
            script_abs_path = tup[1]
            # self.launch_script(script_abs_path)
            proc = self.launch_script(script_abs_path)
            self.assertEqual(0, proc.returncode)

    def test_executing_script_from_global_user_site(self):
        script_abs_path = self._copy_script_to_global_site("test_project", "test_project.py")

        # Second script will be imported from the script above
        self._copy_script_to_global_site("testproject", "test_project.py")
        self._copy_script_to_global_site("testproject", "dummy_test_command.py",
                                         relative_dest_dir=FileUtils.join_path("commands", "testcommand"))
        proc = self.launch_script(script_abs_path)
        self.assertEqual(0, proc.returncode)

    @staticmethod
    def launch_script(script_abs_path):
        cmd = f"python3 {script_abs_path}"
        proc = SubprocessCommandRunner.run_and_follow_stdout_stderr(cmd, stdout_logger=LOG, exit_on_nonzero_exitcode=True)
        return proc

    @contextlib.contextmanager
    def _copy_script_to_temp_dir(self, script_filename: str, dest_filename: str = None):
        if not dest_filename:
            dest_filename = script_filename

        # Can't use /tmp as it's platform dependent.
        # On MacOS, it's mounted as /private/tmp but some Linux systems don't have /private/tmp.
        # Let's use python's built-in temp dir creation methods.
        tmp_dir: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory()
        script_tmp_dir = FileUtils.join_path(tmp_dir.name, "python")
        FileUtils.ensure_dir_created(script_tmp_dir)
        script_abs_path = FileUtils.join_path(script_tmp_dir, dest_filename)
        src_script = FileUtils.join_path(TEST_SCRIPTS_DIR, script_filename)
        FileUtils.copy_file(src_script, script_abs_path)
        yield tmp_dir, script_abs_path

    def _copy_script_to_global_site(self, project_dir: str, script_filename: str, dest_filename: str = None,
                                    relative_dest_dir=None):
        if not dest_filename:
            dest_filename = script_filename
        if not relative_dest_dir:
            relative_dest_dir = ""
        if os.sep in relative_dest_dir:
            relative_dest_dirs = relative_dest_dir.split(os.sep)
        else:
            relative_dest_dirs = [relative_dest_dir]

        python_global_site = site.getsitepackages()[0]
        script_dest_parent_dir = FileUtils.join_path(python_global_site, project_dir)
        FileUtils.ensure_dir_created(script_dest_parent_dir)
        LOG.info("Script parent dir: %s", script_dest_parent_dir)
        dest_file = FileUtils.join_path(script_dest_parent_dir, *relative_dest_dirs, script_filename)
        FileUtils.ensure_file_exists(dest_file, create=True)
        src_file = FileUtils.join_path(TEST_SCRIPTS_DIR, *relative_dest_dirs, dest_filename)
        FileUtils.copy_file(src_file, dest_file)
        return dest_file


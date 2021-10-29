import os
import subprocess
import sys
import tempfile
import unittest
from pythoncommons.file_utils import FileUtils

PROJECT_NAME = "pythoncommons"


class ProjectUtilsTests(unittest.TestCase):
    def test_executing_script_from_uncommon_directory(self):
        # Can't use /tmp as it's platform dependent.
        # On MacOS, it's mounted as /private/tmp but some Linux systems don't have /private/tmp.
        # Let's use python's built-in temp dir creation methods.
        tmp_dir: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory()
        script_dir = FileUtils.ensure_dir_created(FileUtils.join_path(tmp_dir.name, "python"))
        sys.path.append(script_dir)
        script_abs_path = script_dir + os.sep + "hello_world.py"
        contents = "from pythoncommons.project_utils import ProjectUtils,ProjectRootDeterminationStrategy\n" \
                   "ProjectUtils.project_root_determine_strategy = ProjectRootDeterminationStrategy.SYS_PATH" \
                   "print(\"hello world\")\n" \
                   "basedir = ProjectUtils.get_output_basedir('test')\n" \
                   "logfilename = ProjectUtils.get_default_log_file('test')\n"
        FileUtils.save_to_file(script_abs_path, contents)
        os.system(f'python3 {script_abs_path}')
        proc = subprocess.run(["python3", script_abs_path], capture_output=True)
        # print(f"stdout: {proc.stdout}")
        # print(f"stderr: {str(proc.stderr)}")
        print(f"exit code: {proc.returncode}")
        self.assertEqual(0, proc.returncode)


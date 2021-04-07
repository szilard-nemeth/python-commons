import os
import subprocess
import unittest
from pythoncommons.file_utils import FileUtils

PROJECT_NAME = "pythoncommons"


class ProjectUtilsTests(unittest.TestCase):
    def test_executing_script_from_uncommon_directory(self):
        script_dir = FileUtils.ensure_dir_created(FileUtils.join_path(os.sep, "private", "tmp", "python"))
        script_abs_path = script_dir + os.sep + "hello_world.py"
        contents = "from pythoncommons.project_utils import ProjectUtils\n" \
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


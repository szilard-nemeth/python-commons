import os
import shutil
import unittest
from pythoncommons.file_utils import FileUtils


class FileUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.umask(0)
        self.link_container_dir = "/tmp/link_container"
        self.linked_dir = "/tmp/linked_dir"
        self.link_name = "link_name"

    def tearDown(self) -> None:
        if os.path.exists:
            shutil.rmtree(self.link_container_dir)

    def test_create_symlink_path_dir_link_dest_not_exist(self):
        FileUtils.create_symlink_path_dir(self.link_name, self.linked_dir, self.link_container_dir)

    def test_create_symlink_path_dir_link_dest_exist(self):
        os.makedirs(self.link_container_dir, mode=0o777)
        full_path_to_link = FileUtils.join_path(self.link_container_dir, self.link_name)
        FileUtils.create_new_empty_file(full_path_to_link)
        FileUtils.create_symlink_path_dir(self.link_name, self.linked_dir, self.link_container_dir)
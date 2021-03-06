import os
import shutil
import unittest
from pythoncommons.file_utils import FileUtils


class FileUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.link_container_dir = "/tmp/link_container"
        self.linked_dir = "/tmp/linked_dir"
        self.link_name = "link_name"
        if os.path.exists(self.link_container_dir):
            shutil.rmtree(self.link_container_dir)
        os.umask(0)

    def tearDown(self) -> None:
        pass

    def test_create_symlink_path_dir_link_dest_not_exist(self):
        FileUtils.create_symlink_path_dir(self.link_name, self.linked_dir, self.link_container_dir)

    def test_create_symlink_path_dir_link_dest_exist_but_link_does_not_point_to_file(self):
        os.makedirs(self.link_container_dir, mode=0o777)
        full_path_to_link = FileUtils.join_path(self.link_container_dir, self.link_name)
        FileUtils.create_new_empty_file(full_path_to_link)
        FileUtils.create_symlink_path_dir(self.link_name, self.linked_dir, self.link_container_dir)

    def test_create_symlink_path_dir_link_dest_exist_and_link_points_to_file(self):
        os.makedirs(self.link_container_dir, mode=0o777)
        full_path_to_link = FileUtils.join_path(self.link_container_dir, self.link_name)
        FileUtils.create_new_empty_file(full_path_to_link)

        # Remove link, otherwise os.symlink won't work with existing files
        FileUtils.remove_file(full_path_to_link)
        os.symlink(self.linked_dir, full_path_to_link)
        FileUtils.create_symlink_path_dir(self.link_name, self.linked_dir, self.link_container_dir)

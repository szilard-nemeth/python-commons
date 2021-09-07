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

    def test_read_file_into_list(self):
        text_file_path = "/tmp/pythontest/textfile"
        FileUtils.create_new_empty_file(text_file_path)
        FileUtils.write_to_file(text_file_path, "bla\nbla2\nbla3")
        file_lines_list = FileUtils.read_file_to_list(text_file_path)
        self.assertEqual(['bla', 'bla2', 'bla3'], file_lines_list)

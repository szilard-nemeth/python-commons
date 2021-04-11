import logging
import os
from typing import List

from pythoncommons.file_utils import FileUtils
import tempfile
import zipfile
LOG = logging.getLogger(__name__)


class ZipFileUtils:
    @staticmethod
    def create_zip_as_tmp_file(src_files: List[str], filename: str):
        filename, suffix = ZipFileUtils._validate_zip_file_name(filename)
        tmp_file = tempfile.NamedTemporaryFile(prefix=filename, suffix=suffix, delete=False)
        return ZipFileUtils._create_zip_file(src_files, tmp_file)

    @staticmethod
    def create_zip_file(src_files: List[str], filename: str):
        return ZipFileUtils._create_zip_file(src_files, open(filename, mode="wb"))

    @staticmethod
    def extract_zip_file(file: str, path: str):
        # Apparently, ZipFile does not resolve symlinks so let's do it manually
        if os.path.islink(file):
            file = os.path.realpath(file)
        FileUtils.ensure_file_exists(file)
        zip_file = zipfile.ZipFile(file, "r")
        zip_file.extractall(path)

    @staticmethod
    def _validate_zip_file_name(filename):
        if "." in filename:
            filename_and_ext = filename.split(".")
            if len(filename_and_ext) != 2:
                raise ValueError("Invalid filename: " + filename)
            filename = filename_and_ext[0]
            suffix = "." + filename_and_ext[1]
        else:
            filename = filename
            suffix = ".zip"
        return filename, suffix

    @staticmethod
    def _create_zip_file(src_files, file):
        zip_file = zipfile.ZipFile(file, "w")
        LOG.info(f"Creating zip file. Target file: {zip_file.filename}, Input files: {src_files}")
        for src_file in src_files:
            if FileUtils.is_dir(src_file):
                ZipFileUtils._add_dir_to_zip(src_file, zip_file)
            else:
                LOG.debug(f"Adding file '{src_file}' to zip file '${zip_file.filename}'")
                zip_file.write(src_file, FileUtils.basename(src_file))
        zip_file.close()
        file.seek(0)
        return file

    @staticmethod
    def _add_dir_to_zip(src_dir, zip_file):
        # Iterate over all the files in directory
        LOG.debug(f"Adding directory '{src_dir}' to zip file '${zip_file.filename}'")
        for dirpath, dirnames, filenames in os.walk(src_dir):
            LOG.debug(f"dirpath: {dirpath}, dirnames: {dirnames}, filenames: {filenames}")
            for filename in filenames:
                LOG.debug(f"filename: {filename}")
                # create complete filepath of file in directory
                file_path = os.path.join(dirpath, filename)
                # Add file to zip
                LOG.debug(f"Writing to zip. File path: {file_path}, basename: {FileUtils.basename(file_path)}")
                zip_file.write(file_path, FileUtils.basename(file_path))
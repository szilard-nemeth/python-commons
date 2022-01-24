import logging
import os
from contextlib import closing
from io import BufferedWriter
from typing import List
from zlib import Z_DEFAULT_COMPRESSION

from pythoncommons.file_utils import FileUtils, FileFinder
import tempfile
import zipfile

from pythoncommons.string_utils import StringUtils

LOG = logging.getLogger(__name__)


class ZipFileUtils:
    @staticmethod
    def create_zip_file_advanced(
        input_files: List[str], dest_filename: str, ignore_filetypes: List[str] = None, output_dir: str = None
    ):
        if not ignore_filetypes:
            ignore_filetypes = []

        sum_len_all_files: int = 0
        all_ignores_files: int = 0
        if ignore_filetypes:
            (
                all_ignores_files,
                sum_len_all_files,
                input_files,
                tmp_dir,
            ) = ZipFileUtils._determine_input_files_based_on_exclusions(
                all_ignores_files, ignore_filetypes, input_files, sum_len_all_files
            )

        temp_dir_dest: bool = True if not output_dir or output_dir.startswith("/tmp") else False
        if output_dir:
            dest_filepath = FileUtils.join_path(output_dir, dest_filename)
            zip_file: BufferedWriter = ZipFileUtils.create_zip_file(input_files, dest_filepath, compress=True)
        else:
            zip_file: BufferedWriter = ZipFileUtils.create_zip_as_tmp_file(input_files, dest_filename, compress=True)

        zip_file_name = zip_file.name
        no_of_files_in_zip: int = ZipFileUtils.get_number_of_files_in_zip(zip_file_name)
        if ignore_filetypes and (sum_len_all_files - all_ignores_files) != no_of_files_in_zip:
            raise ValueError(
                f"Unexpected number of files in zip. "
                f"All files: {sum_len_all_files}, "
                f"all ignored files: {all_ignores_files}, "
                f"number of files in zip: {no_of_files_in_zip}, "
                f"zip file: {zip_file_name}"
            )

        LOG.info(
            f"Finished writing command data to zip file: {zip_file_name}, "
            f"size: {FileUtils.get_file_size(zip_file_name)}"
        )
        return zip_file_name, temp_dir_dest

    @staticmethod
    def _determine_input_files_based_on_exclusions(
        all_ignores_files, ignore_filetypes, input_files_param, sum_len_all_files
    ):
        input_files = []
        tmp_dir: tempfile.TemporaryDirectory or None = None
        for input_file in input_files_param:
            if FileUtils.is_dir(input_file):
                all_files = FileUtils.find_files(input_file, regex=".*", full_path_result=True)
                sum_len_all_files += len(all_files)
                files_to_ignore = set()
                for ext in ignore_filetypes:
                    new_files_to_ignore = FileUtils.find_files(input_file, extension=ext, full_path_result=True)
                    all_ignores_files += len(new_files_to_ignore)
                    LOG.debug(
                        f"Found {len(new_files_to_ignore)} files to ignore in directory '{input_file}': "
                        f"{StringUtils.list_to_multiline_string(files_to_ignore)}"
                    )
                    files_to_ignore.update(new_files_to_ignore)

                files_to_keep = list(set(all_files).difference(files_to_ignore))
                tmp_dir: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory()
                tmp_dir_path = tmp_dir.name
                FileUtils.copy_files_to_dir(files_to_keep, tmp_dir_path, cut_path=input_file)
                input_files.append(tmp_dir_path)
            else:
                input_files.append(input_file)
                sum_len_all_files += 1
        # IMPORTANT: Need to return tmp_dir as when the TemporaryDirectory object is garbage collected, the tmp dir itself is deleted as well
        # See: https://stackoverflow.com/a/55104228/1106893
        return all_ignores_files, sum_len_all_files, input_files, tmp_dir

    @staticmethod
    def create_zip_as_tmp_file(src_files: List[str], filename: str, compress=False):
        filename, suffix = ZipFileUtils._validate_zip_file_name(filename)
        tmp_file = tempfile.NamedTemporaryFile(prefix=filename, suffix=suffix, delete=False)
        return ZipFileUtils._create_zip_file(src_files, tmp_file, compress=compress)

    @staticmethod
    def create_zip_file(src_files: List[str], filename: str, compress=False, ignore_files: List[str] = None):
        return ZipFileUtils._create_zip_file(
            src_files, open(filename, mode="wb"), compress=compress, ignore_files=ignore_files
        )

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
    def _create_zip_file(src_files, file, compress=False, ignore_files: List[str] = None):
        kwargs = {}
        if compress:
            kwargs["compression"] = zipfile.ZIP_DEFLATED
            kwargs["compresslevel"] = Z_DEFAULT_COMPRESSION  # https://docs.python.org/3/library/zlib.html#zlib.compress
        if not ignore_files:
            ignore_files = []
        zip_file = zipfile.ZipFile(file, "w", **kwargs)
        LOG.info(f"Creating zip file. Target file: {zip_file.filename}, Input files: {src_files}")
        for src_file in src_files:
            if not FileUtils.does_file_exist(src_file):
                LOG.warning("Src file does not exist: %s", src_file)
                continue
            if ignore_files:
                if ZipFileUtils._is_file_ignored(src_file, ignore_files):
                    continue
            if FileUtils.is_dir(src_file, throw_ex=False):
                ZipFileUtils._add_dir_to_zip(src_file, zip_file, ignore_files=ignore_files)
            else:
                LOG.debug(f"Adding file '{src_file}' to zip file '${zip_file.filename}'")
                zip_file.write(src_file, FileUtils.basename(src_file))
        zip_file.close()
        file.seek(0)
        return file

    @staticmethod
    def _is_file_ignored(input_file, ignore_files):
        for ignore in ignore_files:
            if ignore in input_file:
                LOG.debug("Ignoring file while zipping: %s", input_file)
                return True
        return False

    # TODO duplicated os.walk code from FileFinder --> Migrate
    @staticmethod
    def _add_dir_to_zip(src_dir, zip_file, ignore_files: List[str] = None):
        # Iterate over all the files in directory
        LOG.debug(f"Adding directory '{src_dir}' to zip file '${zip_file.filename}'")
        for dirpath, dirnames, filenames in os.walk(src_dir, **FileFinder._get_os_walk_kwargs(ignore_files)):
            LOG.debug(f"[os.walk] dirpath: {dirpath}, dirnames: {dirnames}, filenames: {filenames}")
            dirnames[:] = ZipFileUtils._handle_dir_exclusions(dirnames, ignore_files)
            for filename in filenames:
                ZipFileUtils._add_file_to_zip(zip_file, dirpath, filename, src_dir)

    # TODO duplicated code from FileFinder --> Migrate
    @classmethod
    def _handle_dir_exclusions(cls, dirs, exclude_files):
        if exclude_files:
            # Not enough to check against basename(root) as all other dirs underneath will be walked on the next
            # invocation of the walk generator with the loop statement
            orig_dirs = dirs.copy()
            dirs[:] = [d for d in dirs if d not in exclude_files]
            if len(orig_dirs) != len(dirs):
                LOG.debug(f"Excluded dirs: {list(set(orig_dirs) - set(dirs))}")
        return dirs

    @staticmethod
    def _add_file_to_zip(zip, dirpath, filename, src_dir):
        file_full_path = os.path.join(dirpath, filename)
        dir_path_from_src_dir = dirpath.replace(src_dir, "")
        if dir_path_from_src_dir.startswith(os.sep):
            dir_path_from_src_dir = dir_path_from_src_dir[1:]

        path_in_zip = FileUtils.join_path(dir_path_from_src_dir, filename)
        LOG.debug(f"Writing to zip file {zip}. File full path: {file_full_path}, path in zip file: {path_in_zip}")
        zip.write(file_full_path, path_in_zip)

    @staticmethod
    def get_number_of_files_in_zip(zip_file: str):
        with closing(zipfile.ZipFile(zip_file)) as archive:
            count = len(archive.infolist())
        return count

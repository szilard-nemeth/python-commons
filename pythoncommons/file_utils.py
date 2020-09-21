import errno
import logging
import os
import re
import shutil
import tempfile

import humanize

from pythoncommons.string_utils import RegexUtils

LOG = logging.getLogger(__name__)


class FileUtils:
    previous_cwd = None

    @classmethod
    def write_to_file(cls, file_path, data):
        f = open(file_path, 'w')
        f.write(data)
        f.close()

    @classmethod
    def write_to_tempfile(cls, contents):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        with open(tmp.name, 'w') as f:
            f.write(contents)
        return tmp.name

    @classmethod
    def save_to_file(cls, file_path, contents):
        FileUtils.ensure_file_exists(file_path, create=True)
        file = open(file_path, "w")
        file.write(contents)
        file.close()

    @classmethod
    def append_to_file(cls, file_path, contents):
        file = open(file_path, "a")
        file.write(contents)
        file.close()

    @classmethod
    def ensure_dir_created(cls, dirname, log_exception=False):
        """
    Ensure that a named directory exists; if it does not, attempt to create it.
    """
        try:
            os.makedirs(dirname)
        except OSError as e:
            if log_exception:
                LOG.exception("Failed to create dirs", exc_info=True)
            # If Errno is File exists, don't raise Exception
            if e.errno != errno.EEXIST:
                raise
        return dirname

    @classmethod
    def ensure_file_exists(cls, path, create=False):
        if not path:
            raise ValueError("Path parameter should not be None or empty!")

        if not create and not os.path.exists(path):
            raise ValueError("No such file or directory: {}".format(path))

        path_comps = path.split(os.sep)
        dirs = path_comps[:-1]
        dirpath = os.sep.join(dirs)
        if not os.path.exists(dirpath):
            LOG.info("Creating dirs: %s", dirpath)
            FileUtils.ensure_dir_created(dirpath, log_exception=False)

        if not os.path.exists(path):
            # Create empty file: https://stackoverflow.com/a/12654798/1106893
            LOG.info("Creating file: %s", path)
            open(path, "a").close()

    @classmethod
    def ensure_file_exists_and_readable(cls, file, verbose=False):
        if verbose:
            LOG.info("Trying to open file %s for reading..", file)
        f = open(file, "r")
        if not f.readable():
            raise ValueError("File {} is not readable".format(file))
        return file

    @classmethod
    def ensure_file_exists_and_writable(cls, file, verbose=False):
        if verbose:
            LOG.info("Trying to open file %s for writing..", file)
        f = open(file, "w")
        if not f.writable():
            raise ValueError("File {} is not readable".format(file))
        return file

    @staticmethod
    def search_files(basedir, filename):
        result = []
        for dp, dn, filenames in os.walk(basedir):
            for f in filenames:
                if f == filename:
                    result.append(os.path.join(dp, f))
        return result

    @classmethod
    def find_files(cls, basedir, regex=None, single_level=False, full_path_result=False):
        regex = re.compile(regex)

        res_files = []
        for root, dirs, files in os.walk(basedir):
            for file in files:
                if regex.match(file):
                    if full_path_result:
                        res_files.append(FileUtils.join_path(root, file))
                    else:
                        res_files.append(file)
            if single_level:
                return res_files

        return res_files

    @classmethod
    def remove_files(cls, dir, pattern):
        if not FileUtils.does_file_exist(dir):
            LOG.warning("Directory does not exist: %s", dir)
            return
        for filename in os.listdir(dir):
            file_path = FileUtils.join_path(dir, filename)
            matches = RegexUtils.ensure_matches_pattern(FileUtils.path_basename(file_path), pattern)
            if not matches:
                LOG.debug("Filename not matched: %s", file_path)
                continue
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    LOG.debug("Successfully removed file: %s", file_path)
            except Exception as e:
                LOG.error("Failed to delete %s. Reason: %s", file_path, e)

    @staticmethod
    def copy_file_to_dir(src_file, dst_dir, dst_file_name_func, msg_template=None):
        dest_filename = dst_file_name_func(src_file, dst_dir)
        dest_file_path = os.path.join(dst_dir, dest_filename)

        if msg_template:
            LOG.info(msg_template.format(src_file, dest_file_path))
        shutil.copyfile(src_file, dest_file_path)
        return dest_file_path

    @classmethod
    def get_file_sizes_in_dir(cls, db_copies_dir):
        files = os.listdir(db_copies_dir)
        result = ""
        for f in files:
            file_path = os.path.join(db_copies_dir, f)
            size = os.stat(file_path).st_size
            human_readable_size = humanize.naturalsize(size, gnu=True)
            result += "{size}    {file}\n".format(size=human_readable_size, file=file_path)
        return result

    @classmethod
    def get_file_extension(cls, filename):
        filename, ext = os.path.splitext(filename)
        ext = ext.replace(".", "")
        return ext

    @classmethod
    def does_file_exist(cls, file):
        return os.path.exists(file)

    @classmethod
    def create_files(cls, *files):
        for file in files:
            FileUtils.ensure_file_exists(file, create=True)

    @classmethod
    def verify_if_dir_is_created(cls, path, raise_ex=True):
        if not os.path.exists(path) or not os.path.isdir(path):
            if raise_ex:
                raise ValueError("Directory is not created under path: " + path)
            return False
        return True

    @classmethod
    def get_file_size(cls, file_path, human_readable=True):
        from pathlib import Path

        size = Path(file_path).stat().st_size
        if human_readable:
            return humanize.naturalsize(size, gnu=True)
        else:
            return str(size)

    @classmethod
    def path_basename(cls, path):
        return os.path.basename(path)

    @classmethod
    def join_path(cls, *components):
        return os.path.join(*components)

    @classmethod
    def get_mod_date_of_file(cls, file):
        return os.path.getmtime(file)

    @classmethod
    def get_mod_dates_of_files(cls, basedir, *files):
        result = {}
        for f in files:
            f = FileUtils.join_path(basedir, f)
            if FileUtils.does_file_exist(f):
                result[f] = FileUtils.get_mod_date_of_file(f)
            else:
                result[f] = None
        return result

    @classmethod
    def get_home_path(cls, path):
        return os.path.expanduser(path)

    @classmethod
    def copy_file(cls, src, dest):
        shutil.copyfile(src, dest)

    @classmethod
    def change_cwd(cls, dir):
        cls.previous_cwd = os.getcwd()
        cls._change_cwd(dir)

    @classmethod
    def reset_cwd(cls):
        if not cls.previous_cwd:
            LOG.warning("Can't reset CWD as there's no previous CWD saved!")
        cls._change_cwd(cls.previous_cwd)

    @classmethod
    def _change_cwd(cls, dir):
        try:
            os.chdir(dir)
            LOG.info("Changed current working directory: %s", dir)
        except OSError:
            LOG.error("Can't change the Current Working Directory to %s", dir)
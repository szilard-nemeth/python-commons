import errno
import fnmatch
import hashlib
import logging
import os
import re
import shutil
import tempfile
from enum import Enum
from pathlib import Path

import humanize

from pythoncommons.date_utils import timeit
from pythoncommons.string_utils import RegexUtils

LOG = logging.getLogger(__name__)


class FileMatchType(Enum):
    regex = "regex"
    fnmatch = "fnmatch"


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
    def append_data_to_file(cls, path, data):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        file = open(path, 'a')
        file.write(data)
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
    def ensure_all_files_exist(cls, files):
        for file in files:
            if not os.path.isfile(file):
                raise Exception(file + " does not exist!")

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

    @classmethod
    def ensure_dir_is_writable(cls, d):
        is_dir = FileUtils.is_dir(d)
        if not is_dir:
            raise ValueError("%s is not a directory!", d)

        writable = os.access(d, os.W_OK)
        if not writable:
            raise ValueError("Directory is not writable: %s", d)

    @classmethod
    def ensure_parent_dir_is_writable(cls, f):
        path = Path(f)
        parent_dir = path.parent
        writable = os.access(parent_dir.__str__(), os.W_OK)
        if not writable:
            raise ValueError("Parent directory is not writable: %s", parent_dir)

    @classmethod
    def ensure_dir_is_empty(cls, d):
        is_dir = FileUtils.is_dir(d)
        if not is_dir:
            raise ValueError("%s is not a directory!", d)

        if not FileUtils.is_dir_empty(d):
            raise ValueError("Directory is not empty: %s", d)

    @classmethod
    def is_dir_empty(cls, d):
        children = os.listdir(d)
        if len(children) == 0:
            return True
        return False

    @staticmethod
    def search_files(basedir, filename):
        result = []
        for dp, dn, filenames in os.walk(basedir):
            for f in filenames:
                if f == filename:
                    result.append(os.path.join(dp, f))
        return result

    @staticmethod
    def search_dir(basedir, dirname):
        result = []
        for root, dirs, files in os.walk(basedir):
            for d in dirs:
                if d == dirname:
                    return os.path.join(root, d)
        return result

    @staticmethod
    def find_repo_root_dir(current_script, root_dir_name):
        orig_path = os.path.realpath(current_script)
        path = orig_path
        visited = [path]
        while path != os.sep and not path.endswith(root_dir_name):
            path = FileUtils.get_parent_dir_name(path)
            visited.append(path)
        if path == os.sep:
            raise ValueError(
                "Failed to find directory '{}' starting from path '{}'. "
                "Visited: {}".format(root_dir_name, orig_path, visited))
        return path

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

    @staticmethod
    def list_files_in_dir(dir, pattern=None):
        LOG.info('Listing files in dir: ' + dir)
        if not pattern:
            result = [f for f in os.listdir(dir) if os.path.isfile(os.path.join(dir, f))]
        else:
            result = []
            for f in os.listdir(dir):
                file_path = os.path.join(dir, f)
                if os.path.isfile(file_path) and \
                        FileUtils.does_filename_match(f, pattern, FileMatchType.fnmatch):
                    result.append(file_path)
        return result

    @classmethod
    def does_filename_match(cls, filename, pattern, pattern_match_type):
        if pattern_match_type == FileMatchType.fnmatch and fnmatch.fnmatch(filename, pattern):
            return True
        elif pattern_match_type == FileMatchType.regex and re.search(pattern, filename, re.DOTALL):
            return True
        return False

    @classmethod
    def get_path_from_basedir(cls, basedir, path, include_last_dir=False):
        basedir_idx = path.rindex(basedir)
        start_idx = basedir_idx + len(basedir)
        if not basedir[-1] == os.sep:
            start_idx += len(os.sep)
        if include_last_dir:
            end_idx = len(path)
        else:
            end_idx = path.rindex(os.path.sep) + 1
        return path[start_idx:end_idx]

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

    @classmethod
    def remove_file(cls, path):
        if not os.path.exists(path):
            LOG.warning("Cannot remove file as it does not exist: %s", path)
        os.remove(path)

    @classmethod
    def remove_all_files_in_dir(cls, dir, endswith="lock"):
        if not os.path.exists(dir):
            LOG.error("Can't delete files in dir as dir does not exist: %s", dir)
            return
        for filename in os.listdir(dir):
            file_path = os.path.join(dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    if endswith:
                        if file_path.endswith(endswith):
                            os.unlink(file_path)
                        else:
                            LOG.warning("Skip removing file, does not end with: %", endswith)
                    else:
                        os.unlink(file_path)
                # elif os.path.isdir(file_path):
                #     shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    @classmethod
    def remove_dir(cls, dir):
        os.rmdir(dir)

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
    def does_path_exist(cls, path):
        return os.path.exists(path)

    @classmethod
    def create_files(cls, *files):
        for file in files:
            FileUtils.ensure_file_exists(file, create=True)

    @classmethod
    def create_new_empty_file(cls, path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        file = open(path, 'w')
        file.close()

    @classmethod
    def create_new_dir(cls, path):
        if not os.path.exists(path):
            os.makedirs(path)
        else:
            raise ValueError("Directory already exist: %s", path)

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
    def check_size_match(cls, size, filepath):
        size_on_disk = FileUtils._get_file_size(filepath)
        return size_on_disk == int(size)

    @classmethod
    def check_size_less(cls, size, filepath):
        size_on_disk = FileUtils._get_file_size(filepath)
        return int(size) < size_on_disk

    @classmethod
    def _get_file_size(cls, f):
        return os.stat(f).st_size

    @classmethod
    def get_file_last_modified_date(cls, f):
        return os.path.getmtime(f)

    @classmethod
    def get_mod_date_of_file(cls, file):
        return os.path.getmtime(file)

    @classmethod
    def path_basename(cls, path):
        return os.path.basename(path)

    @classmethod
    def basename(cls, path):
        return os.path.basename(path)

    @classmethod
    def join_path(cls, *components):
        return os.path.join(*components)

    @classmethod
    def make_path(cls, basedir, dirs):
        if not isinstance(dirs, list):
            LOG.warning("%s was called with wrong argument type for 'dirs', "
                        "list is expected. Value of parameter: %s. "
                        "Converting parameter to a list!", FileUtils.make_path, dirs)
            dirs = [dirs]
        return os.path.join(basedir, *dirs)

    @classmethod
    def get_parent_dir_name(cls, dir):
        path = Path(dir)
        return path.parent.__str__()

    @classmethod
    def is_dir_parent_of_dir(cls, parent, dir):
        parent_path_parts = Path(parent).parts
        dir_path_parts = Path(dir).parts
        try:
            idx = dir_path_parts.index(parent_path_parts[0])
        except ValueError as e:
            # Do not log anything
            return False

        for i in range(len(dir_path_parts)):
            if len(parent_path_parts) - 1 >= i and not dir_path_parts[i] == parent_path_parts[idx + i]:
                return False
        return True

    @classmethod
    def get_path_components(cls, path):
        return path.rsplit(os.sep)


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
    def _move_files(cls, src, dst):
        FileUtils.ensure_dir_created(dst)
        files = os.listdir(src)
        for f in files:
            src_path = os.path.join(src, f)
            dst_path = os.path.join(dst, f)
            LOG.info('Moving: {} --> {}', src_path, dst_path)
            os.rename(src_path, dst_path)

    @classmethod
    def change_cwd(cls, dir):
        cls.previous_cwd = os.getcwd()
        cls._change_cwd(dir)

    @classmethod
    def get_filename_from_cwd(cls, filename):
        return os.path.join(os.getcwd(), filename)

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

    @classmethod
    def _hash_files_in_dirs(cls, dirs):
        hash_data = {}
        for dir in dirs:
            hash_data[dir] = {}
            files = os.listdir(dir)
            for f in files:
                file_to_hash = os.path.join(dir, f)
                hash = cls.hash_file(file_to_hash)
                hash_data[dir][hash] = f
        return hash_data

    @classmethod
    def hash_file(cls, f):
        blocksize = 65536
        with open(f, 'rb') as file:
            hasher = hashlib.md5()
            buf = file.read(blocksize)
            while len(buf) > 0:
                hasher.update(buf)
                buf = file.read(blocksize)
        return hasher.hexdigest()

    @classmethod
    def is_file(cls, f):
        if not os.path.exists(f):
            raise ValueError("Path does not exist: %s", f)
        return os.path.isfile(f)

    @classmethod
    def ensure_is_file(cls, f):
        is_file = FileUtils.is_file(f)
        if not is_file:
            raise ValueError("%s is not a file!", f)

    @classmethod
    def is_dir(cls, d, throw_ex=True):
        if not os.path.exists(d):
            if throw_ex:
                raise ValueError("Path does not exist: %s", d)
        return os.path.isdir(d)

    @classmethod
    def get_unique_filepath(cls, dest_file):
        while FileUtils.does_path_exist(dest_file):
            file_path, ext = os.path.splitext(dest_file)
            dest_file = file_path + '_1' + ext
        return dest_file

    @classmethod
    def read_file(cls, f):
        return open(f, 'r').read()


class JsonFileUtils:
    @classmethod
    @timeit
    def write_data_to_file_as_json(cls, path, data):
        import json

        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if not os.path.isdir(dirname):
            raise ValueError("Should have a dir in path, not a file: {}".format(dirname))

        LOG.info("Starting to write to file: %s", path)
        with open(path, 'w') as file:
            json.dump(data, file, sort_keys=True)
        LOG.info("Finished writing to file: %s", path)

    @classmethod
    def load_data_from_json_file(cls, file):
        import json
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            LOG.exception("Error during opening file: %s", file)
            FileUtils.create_new_empty_file(file)
            return None
        except ValueError:
            LOG.exception("Error during reading file: %s", file)
            return None


class CsvFileUtils:
    @classmethod
    def append_row_to_csv_file(cls, path, data, header=None):
        parent_dir = FileUtils.get_parent_dir_name(path)
        if not FileUtils.is_dir(parent_dir, throw_ex=False):
            FileUtils.create_new_dir(parent_dir)

        if not isinstance(data, list):
            raise ValueError("Expected list of data for CSV row!")

        new_file = True if not os.path.exists(path) else False

        with open(path, 'a', newline='') as csvfile:
            import csv
            csv_writer = csv.writer(csvfile, delimiter=';',
                                    quotechar='|', quoting=csv.QUOTE_MINIMAL)
            if new_file and header:
                csv_writer.writerow(header)
            csv_writer.writerow(data)
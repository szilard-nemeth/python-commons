import errno
import logging
import os
import shutil
import humanize

LOG = logging.getLogger(__name__)


class FileUtils:
    @classmethod
    def write_to_file(cls, file_path, data):
        f = open(file_path, 'w')
        f.write(data)
        f.close()

    @classmethod
    def ensure_dir_created(cls, dirname):
        """
    Ensure that a named directory exists; if it does not, attempt to create it.
    """
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        return dirname

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
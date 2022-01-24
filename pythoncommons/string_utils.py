import logging
import math
import os
import string
import re
import unicodedata
from enum import Enum
from typing import List

import pythoncommons.file_utils as fileutils

LOG = logging.getLogger(__name__)


def auto_str(cls, with_repr=True):
    def __str__(self):
        return "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % item for item in vars(self).items()))

    cls.__str__ = __str__

    def __repr__(self):
        return __str__(self)

    if with_repr:
        cls.__repr__ = __repr__
    return cls


# TODO complete this implementation
def auto_str2(cls, with_repr=True, exclude_props=None):
    if not exclude_props:
        exclude_props = []

    def __str__(self):
        props = vars(self).items()
        filtered_props = filter(lambda x: x not in exclude_props, props)
        ret = "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % prop for prop in filtered_props))
        return ret

    cls.__str__ = __str__

    def __repr__(self):
        return __str__(self)

    if with_repr:
        cls.__repr__ = __repr__
    return cls


def auto_repr(cls):
    def __repr__(self):
        return self.__str__()

    cls.__repr__ = __repr__
    return cls


class StringUtils:
    class StripMode(Enum):
        BEGINNING = 0
        END = 1

    @staticmethod
    def list_to_multiline_string(list):
        return "\n".join(str(x) for x in list)

    @staticmethod
    def dict_to_multiline_string(dict):
        return "\n".join([f"{k}: {v}" for k, v in dict.items()])

    @staticmethod
    def make_piped_string(strings: List[str]):
        return "|".join(strings)

    @staticmethod
    def get_first_line_of_multiline_str(multi_line_str):
        return StringUtils.get_line_of_multi_line_str(multi_line_str, 0)

    @staticmethod
    def get_line_of_multi_line_str(multi_line_str, line_number):
        if "\n" not in multi_line_str:
            raise ValueError("String is not a multi line string.")
        return multi_line_str.split("\n")[line_number]

    @staticmethod
    def replace_last(s, to_replace, replace_with, count):
        split = s.rsplit(to_replace, count)
        return replace_with.join(split)

    @staticmethod
    def replace_special_chars(unistr):
        if not isinstance(unistr, str):
            LOG.warning("Object expected to be unicode: " + str(unistr))
            return str(unistr)
        normalized = unicodedata.normalize("NFD", unistr).encode("ascii", "ignore")
        normalized = normalized.decode("utf-8")
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        valid_title = "".join(c for c in normalized if c in valid_chars)
        return valid_title

    @staticmethod
    def convert_string_to_multiline(string, max_line_length, separator=" "):
        if not len(string) > max_line_length:
            return string

        result = ""
        curr_line_length = 0
        parts = string.split(separator)
        for idx, part in enumerate(parts):
            if curr_line_length + len(part) < max_line_length:
                result += part
                # Add length of part + 1 for space to current line length, if required
                curr_line_length += len(part)
            else:
                result += "\n"
                result += part
                curr_line_length = len(part)

            # If not last one, add separator
            if not idx == len(parts) - 1:
                result += separator
                curr_line_length += 1
        return result

    @staticmethod
    def count_leading_zeros(s):
        count = 0
        for i in range(len(s)):
            if s[i] != "0":
                return count
            count += 1

    @staticmethod
    def increase_numerical_str(string):
        num_zeros = StringUtils.count_leading_zeros(string)
        format_str = "%0" + str(num_zeros + 1) + "d"
        return format_str % (int(string) + 1)

    @staticmethod
    def generate_header_line(string, char="=", length=80):
        result = ""
        fill_length = length - len(string)
        filler = char * (math.floor(fill_length / 2))
        result += filler
        result += string
        result += filler
        return result

    @staticmethod
    def strip_strings(filename, strip_strs):
        for str, mode in strip_strs:
            if not isinstance(mode, StringUtils.StripMode):
                raise ValueError(
                    f"Mode of operation is invalid. " f"It should be an instance of: {StringUtils.StripMode.__name__}"
                )
            if mode == StringUtils.StripMode.BEGINNING:
                if filename.startswith(str):
                    filename = filename.split(str)[1]
            elif mode == StringUtils.StripMode.END:
                if filename.endswith(str):
                    filename = filename.split(str)[0]
        LOG.debug("Stripped string: " + filename)
        return filename

    @staticmethod
    def escape_strs(strings: List[str]):
        escaped_lines = []
        for orig_str in strings:
            mod_str = StringUtils.escape_str(orig_str)
            if orig_str != mod_str:
                LOG.debug(f"Modified line. Original: {orig_str}, Modified: {mod_str}")
            escaped_lines.append(orig_str)
        return escaped_lines

    @staticmethod
    def escape_str(orig_str, escape_single_quotes=True, escape_double_quotes=True):
        mod_str = orig_str
        if escape_single_quotes:
            mod_str = mod_str.replace("'", "\\'")
        if escape_double_quotes:
            mod_str = mod_str.replace('"', '\\"')
        return mod_str

    @staticmethod
    def wrap_to_quotes(s):
        return f'"{s}"'

    @staticmethod
    def wrap_to_single_quotes(s):
        return f"'{s}'"

    @staticmethod
    def strip_leading_os_sep(path):
        if path.startswith(os.sep):
            return path[1:]
        return path

    @staticmethod
    def strip_trailing_os_sep(path):
        if path.endswith(os.sep):
            return path[:-1]
        return path

    @staticmethod
    def get_first_dir_of_path(path):
        components = path.split(os.sep)
        if not components or len(components) == 0:
            raise ValueError(f"Invalid path: {path}, can't extract first directory!")
        return components[0]

    @staticmethod
    def get_last_dir_of_path(path):
        components = path.split(os.sep)
        if not components or len(components) == 0:
            raise ValueError(f"Invalid path: {path}, can't extract first directory!")
        return components[-1]

    @staticmethod
    def remove_last_dir_from_path(path):
        path_components = path.split(os.sep)
        path_components = path_components[:-1]
        return os.sep.join(path_components)

    @staticmethod
    def is_path_starting_with_dirname(path, dir_name):
        return path.startswith(os.sep + dir_name)

    @staticmethod
    def prepend_path(orig_path, prepend_with):
        return fileutils.FileUtils.join_path(os.sep, prepend_with, orig_path)

    @staticmethod
    def get_first_dir_of_path_if_multi_component(path):
        if os.sep in path:
            return path.split(os.sep)[0]
        return path

    @staticmethod
    def is_path_multi_component(path):
        if os.sep in path:
            return True
        return False

    @staticmethod
    def is_dir_name_in_path(path, dir_name):
        parts = path.split(os.sep)
        if dir_name in parts:
            return True
        return False

    @staticmethod
    def is_any_of_dir_names_in_path(path, dir_names: List[str]):
        return any(StringUtils.is_dir_name_in_path(path, dirname) for dirname in dir_names)

    @staticmethod
    def get_list_of_components_from_path(path):
        if os.sep in path:
            return path.split(os.sep)
        else:
            return [path]

    @staticmethod
    def find_all(s, expr):
        start = 0
        while True:
            start = s.find(expr, start)
            if start == -1:
                return
            yield start
            start += len(expr)  # use start += 1 to find overlapping matches


class RegexUtils:
    @staticmethod
    def filter_list_by_regex(list, regex):
        p = re.compile(regex)
        return [s for s in list if p.match(s)]

    @staticmethod
    def ensure_matches_pattern(string, regex, raise_exception=False):
        regex_obj = re.compile(regex)
        result = regex_obj.match(string)
        if raise_exception and not result:
            raise ValueError("String '{}' does not match regex pattern: {}".format(string, regex))
        return result

    @staticmethod
    def get_matched_group(str, regex, group):
        match = re.match(regex, str)
        if not match or len(match.groups()) < group:
            raise ValueError(
                "String '{}' does not have match with group number '{}'. Regex: '{}', Match object: '{}'",
                str,
                group,
                regex,
                match,
            )
        return match.group(group)

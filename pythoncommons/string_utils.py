import logging
import math
import string
import re
import unicodedata
from enum import Enum
from typing import List

from tabulate import tabulate

LOG = logging.getLogger(__name__)


def auto_str(cls, with_repr=True):
    def __str__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join('%s=%s' % item for item in vars(self).items())
        )

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
    def replace_special_chars(unistr):
        if not isinstance(unistr, str):
            LOG.warning("Object expected to be unicode: " + str(unistr))
            return str(unistr)
        normalized = unicodedata.normalize('NFD', unistr).encode('ascii', 'ignore')
        normalized = normalized.decode('utf-8')
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        valid_title = ''.join(c for c in normalized if c in valid_chars)
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
                raise ValueError(f"Mode of operation is invalid. "
                                 f"It should be an instance of: {StringUtils.StripMode.__name__}")
            if mode == StringUtils.StripMode.BEGINNING:
                if filename.startswith(str):
                    filename = filename.split(str)[1]
            elif mode == StringUtils.StripMode.END:
                if filename.endswith(str):
                    filename = filename.split(str)[0]
        LOG.debug("Stripped string: " + filename)
        return filename


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


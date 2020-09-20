import logging
import string
import unicodedata
LOG = logging.getLogger(__name__)


def auto_str(cls):
    def __str__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join('%s=%s' % item for item in vars(self).items())
        )

    cls.__str__ = __str__
    return cls


class StringUtils:
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

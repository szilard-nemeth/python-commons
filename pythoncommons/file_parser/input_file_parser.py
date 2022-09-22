import pprint
import re
from enum import Enum
import logging
from re import Pattern
from typing import Dict, Tuple, List, Any, Callable

from pythoncommons.file_parser.parser_config_reader import (
    RegexGenerator,
    DEFAULT_PARSE_PREFIX_SEPARATOR,
    GREEDY_FIELD_POSTFIX,
)
from pythoncommons.file_utils import FileUtils

LOG = logging.getLogger(__name__)


class DiagnosticInfoType(Enum):
    PARSED_OBJECTS = ("PARSED_OBJECT", "Parsed object: %s")
    MATCH_OBJECT = ("MATCH_OBJECT", "Match object: %s")
    MULTI_LINE_BLOCK_HEADER = ("MULTI_LINE_BLOCK_HEADER", "Found multi-line block header: %s")
    EXCLUDED_LINE = ("EXCLUDED_LINE", "Found excluded line: %s")
    MULTI_LINE_BLOCK = ("MULTI_LINE_BLOCK", "Found multi-line block: %s")
    SINGLE_LINE_BLOCK = ("SINGLE_LINE_BLOCK", "Found single-line block: %s")

    def __init__(self, value, log_pattern):
        self.log_pattern = log_pattern


class DiagnosticConfig:
    def __init__(
        self,
        print_date_lines: bool = False,
        print_multi_line_block_headers: bool = False,
        print_multi_line_blocks: bool = False,
        print_match_objs: bool = False,
        print_parsed_objects: bool = True,
        print_single_line_blocks: bool = True,
    ):
        self.print_match_objs = print_match_objs
        self.print_parsed_objects = print_parsed_objects
        self.print_date_lines = print_date_lines
        self.print_multi_line_block_headers = print_multi_line_block_headers
        self.print_multi_line_blocks = print_multi_line_blocks
        self.print_single_line_blocks = print_single_line_blocks
        self.conf_dict: Dict[DiagnosticInfoType, bool] = {
            DiagnosticInfoType.MULTI_LINE_BLOCK_HEADER: self.print_multi_line_block_headers,
            DiagnosticInfoType.EXCLUDED_LINE: self.print_date_lines,
            DiagnosticInfoType.MULTI_LINE_BLOCK: self.print_multi_line_blocks,
            DiagnosticInfoType.MATCH_OBJECT: self.print_match_objs,
            DiagnosticInfoType.PARSED_OBJECTS: self.print_parsed_objects,
            DiagnosticInfoType.SINGLE_LINE_BLOCK: self.print_single_line_blocks,
        }


class DiagnosticPrinter:
    def __init__(self, diagnostic_config: DiagnosticConfig):
        self.diagnostic_config = diagnostic_config

    def print_line(self, line, info_type: DiagnosticInfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, line)

    def pretty_print(self, obj, info_type: DiagnosticInfoType):
        enabled = self.diagnostic_config.conf_dict[info_type]
        if enabled:
            LOG.debug(info_type.log_pattern, pprint.pformat(obj))


class GenericLineByLineParser:
    def __init__(self, generic_parser_config, diagnostic_config):
        self.generic_parser_config = generic_parser_config
        self.printer = DiagnosticPrinter(diagnostic_config)
        self._field_objects = self.generic_parser_config.generic_parser_settings.fields
        self.fields_by_regexes, additional_fields = RegexGenerator.get_regexes(self._field_objects)
        self._field_objects.update(additional_fields)
        LOG.info("Fields by regexes: %s", self.fields_by_regexes)
        self.lines_of_file = None

    def parse(self, file, parsed_object_dataclass: Any, line_to_obj_parser_func: Callable):
        file_contents = FileUtils.read_file(file)
        # TODO change to debug level
        LOG.info("File contents: %s\n", file_contents)
        self.lines_of_file = file_contents.split("\n")
        parsed_objects: List[parsed_object_dataclass] = []
        for idx, line in enumerate(self.lines_of_file):
            parsed_object = self._process_line(line, line_to_obj_parser_func)
            parsed_objects.append(parsed_object)
        self.printer.pretty_print(parsed_objects, DiagnosticInfoType.PARSED_OBJECTS)
        return parsed_objects

    def _process_line(self, line, line_to_obj_parser_func):
        matches: Dict[str, str] = {}
        for field_name, regexes in self.fields_by_regexes.items():
            for regex in regexes:
                LOG.debug("Trying to match field with name '%s' on line '%s' with regex '%s'", field_name, line, regex)
                match = re.search(regex, line)
                if match:
                    field_object = self._field_objects[field_name]
                    matched_str = match.group(field_name)
                    if not matched_str:
                        continue

                    result_str = matched_str
                    if field_object.parse_prefix:
                        prefix_with_sep = field_object.parse_prefix + DEFAULT_PARSE_PREFIX_SEPARATOR
                        if matched_str.startswith(prefix_with_sep):
                            result_str = matched_str[len(prefix_with_sep) :]
                            LOG.debug(
                                "Stripping prefix '%s' from string '%s', resulted string: '%s'",
                                prefix_with_sep,
                                matched_str,
                                result_str,
                            )
                    LOG.debug("Match: %s", result_str)
                    self._add_to_matches(field_name, field_object, matches, result_str)
                    self.printer.print_line(match, DiagnosticInfoType.MATCH_OBJECT)
                    line = line.replace(matched_str, "")
                    line = line.lstrip()
                    line = line.rstrip()
                else:
                    LOG.debug("Field with name '%s' on line '%s' with regex '%s' not found!", field_name, line, regex)
        LOG.debug("Final matches: %s", matches)
        return line_to_obj_parser_func(matches)

    @staticmethod
    def _add_to_matches(field_name, field_object, matches, result_str):
        if field_object.eat_greedy_without_parse_prefix:
            original_field_name = field_name.replace(GREEDY_FIELD_POSTFIX, "")
            if original_field_name not in matches or not matches[original_field_name]:
                matches[field_name] = result_str
        else:
            matches[field_name] = result_str


class GenericBlockBasedInputFileParser:
    def __init__(
        self, block_regex, block_open_chars, block_close_chars, diagnostic_config, excluded_line_patterns: List[Pattern]
    ):
        self.block_regex = block_regex
        self.printer = DiagnosticPrinter(diagnostic_config)
        self.block_open_chars = block_open_chars
        self.block_close_chars = block_close_chars
        self.block_definer = BlockDefiner(
            self.block_open_chars, self.block_close_chars, excluded_line_patterns, self.printer
        )
        self.line_ranges_of_blocks: List[Tuple[int, int]] = []
        self.excluded_line_patterns = excluded_line_patterns

    def parse(self, file: str, parsed_object_dataclass: Any, block_to_obj_parser_func: Callable):
        file_contents = FileUtils.read_file(file)
        self.lines_of_file = file_contents.split("\n")
        self.block_definer.define_blocks(self.lines_of_file)
        parsed_objects = self._process_line_ranges(parsed_object_dataclass, block_to_obj_parser_func)
        self.printer.pretty_print(parsed_objects, DiagnosticInfoType.PARSED_OBJECTS)
        return parsed_objects

    def _process_line_ranges(self, parsed_object_dataclass, block_to_obj_parser_func: Callable):
        self.lines_by_ranges: List[Tuple[List[str], str]] = self._get_lines_by_ranges()

        parsed_objects: List[parsed_object_dataclass] = []
        for list_of_lines, date in self.lines_by_ranges:
            lines = "\n".join(list_of_lines)
            match = re.match(self.block_regex, lines, re.MULTILINE)
            if not match:
                LOG.error("Block not matched: %s", lines)
                continue
            self.printer.print_line(match, DiagnosticInfoType.MATCH_OBJECT)
            parsed_objects.append(block_to_obj_parser_func(match, date))
        return parsed_objects

    def _get_lines_by_ranges(self):
        result: List[Tuple[List[str], str]] = []
        curr_date_idx = 0
        for range in self.block_definer.line_ranges_of_blocks:
            list_of_lines = self.lines_of_file[range[0] : range[1] + 1]
            if (len(self.block_definer.excluded_lines) - 1) != curr_date_idx and range[
                1
            ] > self.block_definer.excluded_lines[curr_date_idx + 1]:
                curr_date_idx += 1
            date_idx = self.block_definer.excluded_lines[curr_date_idx]
            date = self.lines_of_file[date_idx]
            result.append((list_of_lines, date))
        return result


class BlockDefiner:
    MULTI_LINE_BLOCK_CONTINUED = (-1, -1)
    MULTI_LINE_BLOCK_HEADER = (-2, -2)
    EMPTY_LINE = (-3, -3)

    def __init__(
        self, block_open_chars, block_close_chars, excluded_line_patterns: List[Pattern], printer: DiagnosticPrinter
    ):
        self.block_open_chars = block_open_chars
        self.block_close_chars = block_close_chars
        self.multiline_start_idx = -1
        self.multiline_end_idx = -1
        self.inside_multiline_block = False
        self.excluded_lines = []
        self.excluded_line_patterns = excluded_line_patterns
        self.printer = printer
        self.line_ranges_of_blocks = []

    def define_blocks(self, lines_of_file: List[str]):
        for idx, line in enumerate(lines_of_file):
            if self._determine_if_line_excluded(line):
                self.excluded_lines.append(idx)
            else:
                line_range = self._get_line_ranges_of_blocks(line, idx)
                if line_range not in (
                    BlockDefiner.EMPTY_LINE,
                    BlockDefiner.MULTI_LINE_BLOCK_CONTINUED,
                    BlockDefiner.MULTI_LINE_BLOCK_HEADER,
                ):
                    self.line_ranges_of_blocks.append(line_range)

    def _determine_if_line_excluded(self, line) -> bool:
        for excl_pattern in self.excluded_line_patterns:  # type: Pattern
            match = excl_pattern.match(line)
            if match:
                self.printer.print_line(line, DiagnosticInfoType.EXCLUDED_LINE)
                return True
        return False

    def _get_line_ranges_of_blocks(self, line, idx: int) -> Tuple[int, int]:
        if not line:
            LOG.debug("Encountered empty line")
            return BlockDefiner.EMPTY_LINE
        multi_line_opened: bool = any([char in line for char in self.block_open_chars])
        multi_line_closed: bool = any([char in line for char in self.block_close_chars])
        if multi_line_opened and not self.inside_multiline_block:
            self.inside_multiline_block = True
            self.multiline_start_idx = idx
            self.printer.print_line(line, DiagnosticInfoType.MULTI_LINE_BLOCK_HEADER)
            return self.MULTI_LINE_BLOCK_HEADER
        elif multi_line_closed and self.inside_multiline_block:
            self.inside_multiline_block = False
            self.multiline_end_idx = idx
            line_range = (self.multiline_start_idx, self.multiline_end_idx)
            self.printer.print_line(line_range, DiagnosticInfoType.MULTI_LINE_BLOCK)
            return line_range
        elif not multi_line_closed and self.inside_multiline_block:
            return self.MULTI_LINE_BLOCK_CONTINUED
        elif idx not in self.excluded_lines and (line and not line.isspace()):
            # Single line block
            line_range = (idx, idx)
            self.printer.print_line(line_range, DiagnosticInfoType.SINGLE_LINE_BLOCK)
            return line_range
        raise ValueError("Unexpected line: " + line)

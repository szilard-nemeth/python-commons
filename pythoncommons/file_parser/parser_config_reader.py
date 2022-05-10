import json
import logging
import os
import re
from dataclasses import field, dataclass
from enum import Enum
from typing import Dict, List, Pattern, Callable

from dataclasses_json import LetterCase, dataclass_json

from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import JsonFileUtils
from pythoncommons.string_utils import auto_str

DEFAULT_PARSER_CONFIG_FILENAME = "parserconfig.json"

LOG = logging.getLogger(__name__)


class FieldType(Enum):
    REGEX = "regex"
    LITERAL = "literal"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExtractableField:
    type: FieldType
    value: str
    optional: bool
    extract_inner_group: bool = False


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ParsedBlockFormat:
    format_string: str
    fields: Dict[str, ExtractableField] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    mandatory_fields: List[str] = field(default_factory=list)
    FIELD_FORMAT: str = r"<([a-zA-Z0-9_ ]+)>"
    VAR_PATTERN: str = r"VAR\(([a-zA-Z_]+)\)"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericParserSettings:
    parsed_block_format: ParsedBlockFormat
    date_formats: List[str] = field(
        default_factory=list
    )  # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericParserConfig:
    generic_parser_settings: GenericParserSettings

    # dynamic properties
    field_positions: List[str] = None


@auto_str
class ParserConfigReader:
    def __init__(self, data, data_class):
        self.data = data
        self.data_class = data_class
        conf, ext_conf = self._parse()
        self.config: GenericParserConfig = conf
        self.extended_config: data_class = ext_conf
        self.parsed_block_format = self.config.generic_parser_settings.parsed_block_format

        # Post init
        self._validate()
        self.config.date_regexes = self._convert_date_formats_to_patterns()

    def _validate(self):
        if not self.config.generic_parser_settings.date_formats:
            raise ValueError("No date format specified!")

        format_string = self.parsed_block_format.format_string
        actual_field_names = frozenset((self.parsed_block_format.fields.keys()))
        self.config.field_positions = list(re.findall(ParsedBlockFormat.FIELD_FORMAT, format_string))
        expected_field_names = set(self.config.field_positions)

        if not expected_field_names or any([fn == "" for fn in expected_field_names]):
            raise ValueError(
                "Expected field names is empty, this is not normal. Value: {}".format(expected_field_names)
            )

        diff = set(self.parsed_block_format.mandatory_fields).difference(actual_field_names)
        if diff:
            raise ValueError(
                "Found unknown field names: {}. Allowed field names: {}".format(
                    diff, self.parsed_block_format.mandatory_fields
                )
            )

        diff = expected_field_names.difference(actual_field_names)
        if diff:
            raise ValueError(
                "The following fields are not having the field config object {}. "
                "Expected field names: {}".format(diff, expected_field_names)
            )

        self._check_variables()
        self._validate_date_formats(self.config.generic_parser_settings.date_formats)
        self._validate_regexes()

    def _check_variables(self):
        for field_name, field_object in self.parsed_block_format.fields.items():
            vars = re.findall(ParsedBlockFormat.VAR_PATTERN, field_object.value)
            vars_set = set(vars)
            if vars_set:
                LOG.debug("Find variables in field '%s': '%s'", field_name, field_object.value)
                available_vars = self.parsed_block_format.variables
                diff = set(vars_set).difference(set(available_vars.keys()))
                if diff:
                    raise ValueError(
                        "Unknown variables '{}' in {}: {}. Available variables: {}".format(
                            diff, field_name, field_object.value, available_vars.keys()
                        )
                    )
                ParserConfigReader.resolve_variables(available_vars, field_name, field_object, vars_set)

    @staticmethod
    def resolve_variables(available_vars, field_name, field_object, vars_set):
        field_value = field_object.value
        LOG.debug("Resolving variables in string: %s", field_value)

        original_value = str(field_value)
        new_value = str(original_value)
        for var in vars_set:
            new_value = new_value.replace(f"VAR({var})", available_vars[var])
        LOG.debug("Resolved variables for '%s'. Old: %s, New: %s", field_name, original_value, new_value)
        field_object.value = new_value

    def _validate_regexes(self):
        for f in self.parsed_block_format.fields.values():  # type: ExtractableField
            if f.extract_inner_group:
                if f.type != FieldType.REGEX:
                    raise ValueError(
                        "Invalid config. If 'extractInnerGroup' is enabled, field type should be regex. Field object: {}".format(
                            f
                        )
                    )
                elif not (self._ensure_there_is_only_one_regex_group(f.value)):
                    raise ValueError(
                        "Invalid config. If 'extractInnerGroup' is enabled, the regex should only have at most one group. Field object: {}".format(
                            f
                        )
                    )

    @staticmethod
    def _validate_date_formats(format_strings):
        for fmt in format_strings:
            LOG.debug("Formatting current date with format '%s': %s", fmt, DateUtils.now_formatted(fmt))
        # TODO

    @staticmethod
    def read_from_file(data_class, dir=None, filename=None):
        if filename:
            parser_conf_file = filename
        elif dir:
            parser_conf_file = os.path.join(dir, DEFAULT_PARSER_CONFIG_FILENAME)
        else:
            parser_conf_file = DEFAULT_PARSER_CONFIG_FILENAME

        data_dict = JsonFileUtils.load_data_from_json_file(parser_conf_file)
        return ParserConfigReader(data_dict, data_class)

    def _parse(self):
        generic_parser_config = GenericParserConfig.from_json(json.dumps(self.data))
        LOG.info("Generic parser config: %s", generic_parser_config)

        extended_parser_config = self.data_class.from_json(json.dumps(self.data))
        LOG.info("Extended parser config: %s", extended_parser_config)
        return generic_parser_config, extended_parser_config

    def _convert_date_formats_to_patterns(self):
        mappings = {"%m": "\\d\\d", "%d": "\\d\\d", "%Y": "\\d\\d\\d\\d", ".": "\\."}
        regexes: List[Pattern] = []
        for fmt in self.config.generic_parser_settings.date_formats:
            curr_regex = fmt
            for orig, pattern in mappings.items():
                curr_regex = curr_regex.replace(orig, pattern)
            curr_regex += "$"
            regexes.append(re.compile(curr_regex))
        return regexes

    @staticmethod
    def _ensure_there_is_only_one_regex_group(regex: str):
        count_open = regex.count("(")
        count_close = regex.count(")")
        if count_open != count_close:
            return False
        if count_open > 1 or count_open == 0:
            return False
        return True

    def __repr__(self):
        return self.__str__()


class RegexGenerator:
    @staticmethod
    def create_final_regex(config: GenericParserConfig):
        field_objects: Dict[str, ExtractableField] = config.generic_parser_settings.parsed_block_format.fields
        final_regex = r""
        used_group_names = {}
        for field_name in config.field_positions:
            field_object = field_objects[field_name]
            group_name = field_name
            if group_name not in used_group_names:
                used_group_names[group_name] = 1
                final_regex += RegexGenerator._create_regex(group_name, field_object)
            else:
                if group_name not in config.generic_parser_settings.parsed_block_format.mandatory_fields:
                    used_group_names[group_name] += 1
                    group_name = f"{group_name}_{used_group_names[group_name]}"
                    final_regex += RegexGenerator._create_regex(group_name, field_object)
                else:
                    raise ValueError("Group name is already used in regex: {}".format(group_name))
        LOG.info("FINAL REGEX: %s", final_regex)
        return final_regex

    @staticmethod
    def _create_regex(group_name, field_object: ExtractableField):
        regex_value = field_object.value
        if field_object.extract_inner_group:
            grouped_regex = RegexGenerator._get_inner_group_grouped_regex(group_name, regex_value)
            if field_object.optional:
                grouped_regex = f"({grouped_regex})*"
        else:
            grouped_regex = f"(?P<{group_name}>{regex_value})"
            if field_object.optional:
                grouped_regex += "*"
        return grouped_regex

    @staticmethod
    def _get_inner_group_grouped_regex(group_name, regex_value):
        open_idx = regex_value.find("(")
        close_idx = regex_value.rfind(")")
        quantifier = regex_value[close_idx + 1]
        if quantifier not in ["*", "?", "+"]:
            quantifier = ""
        start = regex_value[:open_idx]
        end = regex_value[close_idx + 1 :]
        group = regex_value[open_idx + 1 : close_idx] + quantifier
        grouped_regex = f"(?P<{group_name}>{group})"
        new_regex_value = f"{start}{grouped_regex}{end}"
        return new_regex_value

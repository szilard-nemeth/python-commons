import json
import logging
import os
import re
from copy import copy
from dataclasses import field, dataclass
from enum import Enum
from typing import Dict, List, Pattern

from dataclasses_json import LetterCase, dataclass_json

from pythoncommons.date_utils import DateUtils
from pythoncommons.file_utils import JsonFileUtils
from pythoncommons.string_utils import auto_str

REGEX_DOT = "\\."

REGEX_TWO_DIGITS = "\\d\\d"
REGEX_FOUR_DIGITS = REGEX_TWO_DIGITS + REGEX_TWO_DIGITS

DEFAULT_PARSER_CONFIG_FILENAME = "parserconfig.json"
DEFAULT_PARSE_PREFIX_SEPARATOR = ":"
DEFAULT_ALLOWED_VALUES_SEPARATOR = ","
GREEDY_FIELD_POSTFIX = "_greedy"

LOG = logging.getLogger(__name__)

REGEX_FOR_STRING = "[a-zA-ZÀ-ú0-9-:@<>_@().,'|\\[\\]\\/]+"
REGEX_FOR_MULTI_WORD_STRING = '"[ a-zA-ZÀ-ú0-9-:@<>_@().,\'|\\[\\]\\/]+"'
REGEX_FOR_MULTI_WORD_STRING_GREEDY = "[ a-zA-ZÀ-ú0-9-:@<>_@().,'|\\[\\]\\/]+"


class FieldParseType(Enum):
    REGEX = "regex"
    REGEX_WITH_SMART_PARSE = "regexSmartParse"
    LITERAL = "literal"
    BOOL = "bool"
    INT = "int"


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class ExtractableField:
    parse_type: FieldParseType
    optional: bool
    value: str = None
    extract_inner_group: bool = False
    allowed_values: str or None = field(default=None)
    parse_prefix: str or None = field(default=None)
    precedence: int or None = field(default=100)
    eat_greedy_without_parse_prefix: bool or None = field(default=False)

    def __post_init__(self):
        if self.allowed_values:
            self.allowed_values_list = self.allowed_values.split(",")


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
class GenericBlockParserSettings:
    parsed_block_format: ParsedBlockFormat
    date_formats: List[str] = field(
        default_factory=list
    )  # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    @property
    def fields_proxy(self):
        return self.parsed_block_format.fields

    @property
    def variables_proxy(self):
        return self.parsed_block_format.variables

    @property
    def mandatory_fields_proxy(self):
        return self.parsed_block_format.mandatory_fields

    @property
    def format_string_proxy(self):
        return self.parsed_block_format.format_string


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericBlockParserConfig:
    generic_parser_settings: GenericBlockParserSettings

    # dynamic properties
    field_positions: List[str] = None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericLineParserSettings:
    fields: Dict[str, ExtractableField] = field(default_factory=dict)
    variables: Dict[str, str] = field(default_factory=dict)
    date_formats: List[str] = field(
        default_factory=list
    )  # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes

    @property
    def fields_proxy(self):
        return self.fields

    @property
    def mandatory_fields_proxy(self):
        return []

    @property
    def variables_proxy(self):
        return self.variables

    @property
    def format_string_proxy(self):
        return None


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass
class GenericLineParserConfig:
    generic_parser_settings: GenericLineParserSettings


@auto_str
class ParserConfigReader:
    def __init__(self, data, obj_data_class, config_type):
        self.data = data
        self.obj_data_class = obj_data_class
        conf, ext_conf = self._parse(config_type)
        self.config: config_type = conf
        self.extended_config: obj_data_class = ext_conf
        self.generic_parser_settings = self.config.generic_parser_settings

        # Post init
        self._validate()
        self.config.date_regexes = self._convert_date_formats_to_patterns()

    def _validate(self):
        if not self.config.generic_parser_settings.date_formats:
            raise ValueError("No date format specified!")

        format_string = self.generic_parser_settings.format_string_proxy
        actual_field_names = frozenset((self.generic_parser_settings.fields_proxy.keys()))
        if format_string:
            self.config.field_positions = list(re.findall(ParsedBlockFormat.FIELD_FORMAT, format_string))
            expected_field_names = set(self.config.field_positions)

            if not expected_field_names or any([fn == "" for fn in expected_field_names]):
                raise ValueError(
                    "Expected field names is empty, this is not normal. Value: {}".format(expected_field_names)
                )

            diff = expected_field_names.difference(actual_field_names)
            if diff:
                raise ValueError(
                    "The following fields are not having the field config object {}. "
                    "Expected field names: {}".format(diff, expected_field_names)
                )
        else:
            self.config.field_positions = list(self.generic_parser_settings.fields_proxy.keys())

        diff = set(self.generic_parser_settings.mandatory_fields_proxy).difference(actual_field_names)
        if diff:
            raise ValueError(
                "Found unknown field names: {}. Allowed field names: {}".format(
                    diff, self.generic_parser_settings.mandatory_fields_proxy
                )
            )

        self._check_variables()
        self._validate_date_formats(self.config.generic_parser_settings.date_formats)
        self._validate_regexes()
        self._validate_alllowed_values()

    def _check_variables(self):
        for field_name, field_object in self.generic_parser_settings.fields_proxy.items():
            if field_object.parse_type != FieldParseType.REGEX:
                continue
            vars = re.findall(ParsedBlockFormat.VAR_PATTERN, field_object.value)
            vars_set = set(vars)
            if vars_set:
                LOG.debug("Find variables in field '%s': '%s'", field_name, field_object.value)
                available_vars = self.generic_parser_settings.variables_proxy
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
        for f in self.generic_parser_settings.fields_proxy.values():  # type: ExtractableField
            if f.extract_inner_group:
                if f.type != FieldParseType.REGEX:
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

    def _validate_alllowed_values(self):
        for field_name, field_object in self.config.generic_parser_settings.fields_proxy.items():
            if field_object.parse_type == FieldParseType.BOOL and not field_object.allowed_values:
                raise ValueError(
                    "Parse type is set to '{}' on field '{}', but allowed values are not specified!".format(
                        FieldParseType.BOOL.value, field_name
                    )
                )

    @staticmethod
    def read_from_file(obj_data_class, config_type, dir=None, filename=None):
        if filename:
            parser_conf_file = filename
        elif dir:
            parser_conf_file = os.path.join(dir, DEFAULT_PARSER_CONFIG_FILENAME)
        else:
            parser_conf_file = DEFAULT_PARSER_CONFIG_FILENAME

        data_dict = JsonFileUtils.load_data_from_json_file(parser_conf_file)
        return ParserConfigReader(data_dict, obj_data_class, config_type)

    def _parse(self, config_type):
        generic_parser_config = config_type.from_json(json.dumps(self.data))
        LOG.info("Generic parser config: %s", generic_parser_config)

        extended_parser_config = self.obj_data_class.from_json(json.dumps(self.data))
        LOG.info("Extended parser config: %s", extended_parser_config)
        return generic_parser_config, extended_parser_config

    def _convert_date_formats_to_patterns(self):
        mappings = {"%m": REGEX_TWO_DIGITS, "%d": REGEX_TWO_DIGITS, "%Y": REGEX_FOUR_DIGITS, ".": REGEX_DOT}
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


class RegexFieldMatchType(Enum):
    SINGLE_MATCH = "single"
    MATCH_ANYWHERE = "anywhere"


class RegexGenerator:
    MATCH_TYPE = RegexFieldMatchType.MATCH_ANYWHERE

    @staticmethod
    def get_regexes(field_objects: Dict[str, ExtractableField]):
        # Order dict by precedence
        field_objects = {k: v for k, v in sorted(field_objects.items(), key=lambda item: item[1].precedence)}

        regex_dict: Dict[str, List[str]] = {}
        additional_fields: Dict[str, ExtractableField] = {}
        used_group_names = {}
        for field_name, field_object in field_objects.items():
            group_name = field_name  # use uppercase field name everywhere
            if group_name not in used_group_names:
                used_group_names[group_name] = True
                regex_dict[group_name] = RegexGenerator._create_regexes(group_name, field_object)
            else:
                raise ValueError("Group name is already used in regex: {}".format(group_name))
            if field_object.eat_greedy_without_parse_prefix:
                field_key = group_name + GREEDY_FIELD_POSTFIX
                regex_dict[field_key] = RegexGenerator._create_regexes(
                    field_key, field_object, use_parse_prefix=False, greedy=True
                )
                copied_field = copy(field_object)
                additional_fields[field_key] = copied_field
        return regex_dict, additional_fields

    @staticmethod
    # TODO Only monthlyexpensesummarizer uses this, remove later
    def create_final_regex(parser_config):
        field_objects: Dict[str, ExtractableField] = parser_config.generic_parser_settings.fields_proxy
        final_regex = r""
        used_group_names = {}
        for field_name in parser_config.field_positions:
            field_object = field_objects[field_name]
            group_name = field_name
            if group_name not in used_group_names:
                used_group_names[group_name] = 1
                final_regex += RegexGenerator._create_regexes(group_name, field_object)
            else:
                if group_name not in parser_config.generic_parser_settings.mandatory_fields_proxy:
                    used_group_names[group_name] += 1
                    group_name = f"{group_name}_{used_group_names[group_name]}"
                    final_regex += RegexGenerator._create_regexes(group_name, field_object)
                else:
                    raise ValueError("Group name is already used in regex: {}".format(group_name))
        LOG.info("FINAL REGEX: %s", final_regex)
        return final_regex

    @staticmethod
    def _create_regexes(group_name, field_object: ExtractableField, use_parse_prefix=True, greedy=False) -> List[str]:
        regex_values: List[str] = [field_object.value]
        parse_prefix = ""
        if use_parse_prefix:
            parse_prefix = field_object.parse_prefix
            if not parse_prefix:
                parse_prefix = ""
            else:
                parse_prefix += DEFAULT_PARSE_PREFIX_SEPARATOR
        elif field_object.parse_type == FieldParseType.INT:
            regex_values = [r"\d+"]
        elif field_object.parse_type == FieldParseType.BOOL:
            regex_values = ["|".join(field_object.allowed_values_list)]

        if field_object.parse_type == FieldParseType.REGEX_WITH_SMART_PARSE:
            # Add another regex with quoted string + multiple word capability
            # example values could be parsed:
            # from: "word1 word2 word3"
            # from: word1
            if greedy:
                # NOTE: Order is important, need to match multi-word strings before single word string
                regex_values = [REGEX_FOR_MULTI_WORD_STRING_GREEDY, REGEX_FOR_STRING]
            else:
                regex_values = [REGEX_FOR_STRING, REGEX_FOR_MULTI_WORD_STRING]

        regex_values = RegexGenerator._create_prefixed_regexes(parse_prefix, regex_values)
        grouped_regexes = RegexGenerator._create_grouped_regexes(field_object, group_name, regex_values)
        return grouped_regexes

    @staticmethod
    def _create_prefixed_regexes(parse_prefix, regex_values):
        # TODO
        # if RegexGenerator.MATCH_TYPE == RegexFieldMatchType.MATCH_ANYWHERE:
        # return [f".*{parse_prefix}{r}" for r in regex_values]
        return [f"{parse_prefix}{r}" for r in regex_values]

    @staticmethod
    def _create_grouped_regexes(field_object, group_name, regex_values):
        if field_object.extract_inner_group:
            grouped_regexes = RegexGenerator._get_inner_group_grouped_regexes(group_name, regex_values)
            if field_object.optional:
                grouped_regexes = [f"({r})*" for r in grouped_regexes]
        else:
            grouped_regexes = [f"(?P<{group_name}>{r})" for r in regex_values]
            if field_object.optional:
                grouped_regexes = [f"{r}*" for r in grouped_regexes]
        return grouped_regexes

    @staticmethod
    def _get_inner_group_grouped_regexes(group_name, regex_values):
        ret = []
        for regex_value in regex_values:
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
            ret.append(new_regex_value)
        return ret

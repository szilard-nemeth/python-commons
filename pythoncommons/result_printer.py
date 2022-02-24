import logging
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Any
from colr import color
from pythoncommons.string_utils import StringUtils, auto_str
from tabulate import tabulate

LOG = logging.getLogger(__name__)


class TabulateTableFormat(Enum):
    GRID = "fancy_grid"
    HTML = "html"
    UNSAFE_HTML = "unsafehtml"


DEFAULT_TABLE_FORMATS = [TabulateTableFormat.GRID, TabulateTableFormat.HTML]


@dataclass
class TableCellLink:
    link_name: str
    link_value: str

    def to_html(self):
        return f'<a href="{self.link_value}">{self.link_name}</a>'


class GenericTableWithHeader:
    def __init__(
        self,
        header_title: str,
        header_list: List[str],
        source_data: Any,
        rendered_table: str,
        table_fmt: TabulateTableFormat,
        colorized: bool = False,
    ):
        self.header = (
            StringUtils.generate_header_line(
                header_title, char="═", length=len(StringUtils.get_first_line_of_multiline_str(rendered_table))
            )
            + "\n"
        )
        self.header_list = header_list
        self.source_data = source_data
        self.table = rendered_table
        self.table_fmt: TabulateTableFormat = table_fmt
        self.colorized = colorized

    def __str__(self):
        return self.header + self.table


class Color(Enum):
    GREEN = "green"
    RED = "red"


class ColorType(Enum):
    FOREGROUND = "fore"
    BACKROUND = "back"


class MatchType(Enum):
    ALL = "all"
    ANY = "any"


class EvaluationMethod(Enum):
    ALL = 0
    FIRST_TRUTHY = 1


@auto_str
class ColorDescriptor:
    def __init__(
        self,
        type,
        value,
        color: Color,
        match_type: MatchType,
        scan_range: Tuple[int, int],
        colorize_range: Tuple[int, int],
        color_type: ColorType = ColorType.FOREGROUND,
    ):
        self.type = type
        self.value = value
        self.color: Color = color
        self.match_type: MatchType = match_type
        self.scan_range: Tuple[int, int] = scan_range
        self.colorize_range: Tuple[int, int] = colorize_range
        self.color_type = color_type


@auto_str
class ConversionResult:
    def __init__(self, src_data, result_data):
        self.src_data = src_data
        self.dst_data = result_data


@auto_str
class ColorizeConfig:
    def __init__(
        self, descriptors: List[ColorDescriptor], eval_method: EvaluationMethod = EvaluationMethod.FIRST_TRUTHY
    ):
        self.descriptors = descriptors
        self.eval_method = eval_method


@auto_str
class BoolConversionConfig:
    def __init__(self, convert_true_to="X", convert_false_to="-"):
        self.convert_true_to = convert_true_to
        self.convert_false_to = convert_false_to


@auto_str
class TableRenderingConfig:
    def __init__(
        self,
        row_callback,  # TODO specify type
        join_lists_by_comma: bool = True,
        add_row_numbers: bool = True,
        max_width: int = None,
        max_width_separator: str = " ",
        bool_conversion_config: BoolConversionConfig = None,
        colorize_config: ColorizeConfig = None,
        print_result: bool = True,
        tabulate_format: TabulateTableFormat = None,
        tabulate_formats: List[TabulateTableFormat] = None,
    ):
        self.row_callback = row_callback
        self.join_lists_by_comma = join_lists_by_comma
        self.add_row_numbers = add_row_numbers
        self.max_width = max_width
        self.max_width_separator = max_width_separator
        self.bool_conversion_config = bool_conversion_config
        self.colorize_config = colorize_config
        self.print_result = print_result
        self.tabulate_format = tabulate_format
        self.tabulate_formats = tabulate_formats

        # Validation
        if not self.tabulate_format and not self.tabulate_formats:
            raise ValueError("Either of tabulate_format or tabulate_formats should be specified!")
        if self.tabulate_format and self.tabulate_formats:
            raise ValueError(
                "Can't decide if tabulate_format or tabulate_formats should be used. Please only use either of them!"
            )


class ResultPrinter:
    @staticmethod
    def print_tables(
        data,
        header,
        render_conf: TableRenderingConfig,
        verbose=False,
    ):
        tables = {}
        if verbose:
            LOG.debug("Rendering config for table is: %s", render_conf)
        for table_format in render_conf.tabulate_formats:
            # TODO this is a dirty hack to avoid: AttributeError: 'NoneType' object has no attribute 'value'
            render_conf.tabulate_format = table_format
            if verbose:
                LOG.debug("Calling %s with table format: %s", ResultPrinter.print_table.__name__, table_format)
            tables[table_format] = ResultPrinter.print_table(data, header, render_conf=render_conf)
        return tables

    @staticmethod
    def print_table(data, header, render_conf: TableRenderingConfig):
        conversion_result = ResultPrinter.convert_list_data(data, render_conf)
        # LOG.debug(f"Conversion result: {conversion_result}")
        tabulated = tabulate(conversion_result.dst_data, header, tablefmt=render_conf.tabulate_format.value)
        if render_conf.print_result:
            print(tabulated)
        return tabulated

    @staticmethod
    def convert_list_data(src_data, render_conf: TableRenderingConfig):
        result = []
        for idx, src_row in enumerate(src_data):
            row = render_conf.row_callback(src_row)
            converted_row = []
            if render_conf.add_row_numbers:
                converted_row.append(idx + 1)
            for cell in row:
                if render_conf.join_lists_by_comma and isinstance(cell, list):
                    cell = ", ".join(cell)

                bcc = render_conf.bool_conversion_config
                if bcc and isinstance(cell, bool):
                    cell = bcc.convert_true_to if cell else bcc.convert_false_to
                if isinstance(cell, TableCellLink):
                    cell = cell.to_html()
                elif render_conf.max_width and isinstance(cell, str):
                    cell = StringUtils.convert_string_to_multiline(
                        cell, max_line_length=render_conf.max_width, separator=render_conf.max_width_separator
                    )
                converted_row.append(cell)

            if render_conf.colorize_config:
                ResultPrinter._colorize_row(render_conf.colorize_config, converted_row, row)
            result.append(converted_row)

        return ConversionResult(src_data, result)

    @staticmethod
    def _colorize_row(conf: ColorizeConfig, converted_row, row):
        largest_range_end = -1
        for desc in conf.descriptors:
            range_end = desc.colorize_range[1]
            largest_range_end = max(largest_range_end, range_end)
        if largest_range_end >= len(converted_row):
            raise ValueError(
                "Invalid colorize config. Range is larger than number of columns in row. "
                "Colorize config: {}, row: {}".format(conf, row)
            )

        row_as_list = list(row)
        truthy = []
        for cd in conf.descriptors:
            filtered_type_values = list(
                filter(lambda x: type(x) == cd.type, row_as_list[cd.scan_range[0] : cd.scan_range[1]])
            )
            match_count = 0
            for idx, val in enumerate(filtered_type_values):
                if val == cd.value:
                    match_count += 1
            if cd.match_type == MatchType.ANY and match_count > 0:
                truthy.append(cd)
            elif cd.match_type == MatchType.ALL and match_count == len(filtered_type_values):
                truthy.append(cd)

        for cd in truthy:
            color_args = {cd.color_type.value: cd.color.value}
            for i in range(*cd.colorize_range):
                # Color multiline strings line by line
                if "\n" in str(converted_row[i]):
                    lines = converted_row[i].splitlines()
                    colored = []
                    for idx, line in enumerate(lines):
                        colored.append(color(line, **color_args))
                    converted_row[i] = "\n".join(colored)
                else:
                    converted_row[i] = color(converted_row[i], **color_args)
            if conf.eval_method == EvaluationMethod.FIRST_TRUTHY:
                break

    # TODO Users of this function should be migrated to _colorize_row and the new ResultPrinter
    @staticmethod
    def colorize_row(
        curr_row,
        convert_bools=False,
        char_if_present="X",
        char_if_not_present="-",
        color_if_okay="green",
        color_if_not_okay="red",
    ):
        res = []
        missing_backport = False
        if not all(curr_row[1:]):
            missing_backport = True

        # Mark first cell with red if any of the backports are missing
        # Mark first cell with green if all backports are present
        # Mark any bool cell with green if True, red if False
        for idx, cell in enumerate(curr_row):
            if (isinstance(cell, bool) and cell) or not missing_backport:
                if convert_bools and isinstance(cell, bool):
                    cell = char_if_present if cell else char_if_not_present
                res.append(color(cell, fore=color_if_okay))
            else:
                if convert_bools and isinstance(cell, bool):
                    cell = char_if_present if cell else char_if_not_present
                res.append(color(cell, fore=color_if_not_okay))
        return res


class BasicResultPrinter:
    @staticmethod
    def print_table(data, headers):
        LOG.info("Printing result table with format: fancy_grid")
        LOG.info(tabulate(data, headers, tablefmt=TabulateTableFormat.GRID.name))

    @staticmethod
    def print_table_html(data, headers):
        LOG.info("Printing result table with format: html")
        LOG.info(tabulate(data, headers, tablefmt=TabulateTableFormat.HTML.name))

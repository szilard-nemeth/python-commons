from typing import List, Tuple

from bs4 import BeautifulSoup


class HtmlGenerator:
    def __init__(self):
        self.last_html_separator = None
        self.html = None
        self.finished_html = False
        self.soup = BeautifulSoup()

    def begin_html_tag(self):
        self.html = self.soup.new_tag("html")
        return self

    def finish_html(self):
        if self.finished_html:
            raise ValueError("Invalid state. Already finished html.")
        if not self.html:
            raise ValueError("Invalid state. Please call 'begin_html_tag' first.")

        self.soup.append(self.html)
        self.finished_html = True
        return self

    def render(self):
        if not self.finished_html:
            self.finish_html()
        return self.soup.prettify()

    def add_basic_table_style(self):
        if not self.html:
            raise ValueError("Invalid state. Please call 'begin_html_tag' first.")

        head = self.soup.new_tag("head")
        style = self.soup.new_tag("style")
        style.string = """
table, th, td {
  border: 1px solid black;
}
"""
        head.append(style)
        self.html.append(head)
        return self

    def append_paragraphs(self, strings: List[str]):
        for line in strings:
            self.append_paragraph(line)
        return self

    def append_paragraph(self, string):
        p = self.soup.new_tag("p")
        p.append(string)
        self.soup.append(p)
        return self

    @staticmethod
    def generate_separator(tag="hr", breaks=2):
        html_sep: str = f"<{tag}/>"
        html_sep += breaks * "<br/>"
        return html_sep

    def append_html_tables(self,
                           table_tups: List[Tuple[str, str]],
                           separator=None,
                           additional_separator_at_beginning=False,
                           header_type="h1"):
        if not self.html:
            raise ValueError("Invalid state. Please call 'begin_html_tag' first.")

        tables_html = ""
        if not separator:
            separator = ""
        ht = header_type

        if additional_separator_at_beginning:
            tables_html += separator

        # header = tup[0], table = tup[1]
        tables_html += separator.join([f"<h1>{tup[0]}</h1>" + tup[1] for tup in table_tups])
        gen_tables_soup = BeautifulSoup(tables_html, "html.parser")
        self.html.append(gen_tables_soup)
        return self

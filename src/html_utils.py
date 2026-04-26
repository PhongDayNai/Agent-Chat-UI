"""HTML extraction helpers."""

import re
from html.parser import HTMLParser

class HtmlTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}
    BLOCK_TAGS = {
        "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt",
        "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4",
        "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section",
        "table", "td", "th", "tr", "ul",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return
        self.parts.append(text)
        self.parts.append(" ")

    def text(self):
        content = "".join(self.parts)
        content = re.sub(r"[ \t]+\n", "\n", content)
        content = re.sub(r"\n[ \t]+", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r"[ \t]{2,}", " ", content)
        return content.strip()

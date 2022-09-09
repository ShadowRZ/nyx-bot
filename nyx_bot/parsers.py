from html import escape
from html.parser import HTMLParser


class MatrixHTMLParser(HTMLParser):
    def __init__(self, strip_reply=True):
        self.strip_reply = strip_reply
        self.is_in_reply = False
        self.buffer = ""
        self.limit = 1000
        self.data_length = 0
        self.stack = []
        self.should_parse = True
        super().__init__()

    def handle_startendtag(self, tag, attrs):
        if self.should_parse:
            if not self.is_in_reply:
                if tag == "br":
                    self.buffer += "\n"

    def handle_starttag(self, tag, attrs):
        if self.should_parse:
            if tag == "mx-reply" and self.strip_reply:
                self.is_in_reply = True
            if not self.is_in_reply:
                self.stack.append(tag)
                if tag == "a":
                    for attr in attrs:
                        if attr[0] == "href":
                            self.buffer += (
                                '<span underline="single" underline_color="blue">'
                            )
                        else:
                            self.buffer += "<span>"
                elif tag in ("b", "strong"):
                    self.buffer += "<b>"
                elif tag in ("s", "del"):
                    self.buffer += "<s>"
                elif tag == "blockquote":
                    if not self.buffer.endswith("\n"):
                        self.buffer += "\n"
                    self.buffer += '<span background="#D3D3D380">'
                elif tag == "font":
                    for attr in attrs:
                        if attr[0] == "color":
                            self.buffer += f'<span color="{attr[1]}">'
                        else:
                            self.buffer += "<span>"
                elif tag == "span":
                    for attr in attrs:
                        if attr[0] == "data-mx-spoiler":
                            self.buffer += '<span color="black" background="black">'
                        else:
                            self.buffer += "<span>"

    def handle_endtag(self, tag):
        if self.should_parse:
            if not self.is_in_reply:
                if self.stack:
                    self.stack.pop()
                if tag in ("a", "font", "blockquote", "span"):
                    self.buffer += "</span>"
                elif tag in ("b", "strong"):
                    self.buffer += "</b>"
                elif tag in ("s", "del"):
                    self.buffer += "</s>"
            if tag == "mx-reply" and self.strip_reply:
                self.is_in_reply = False

    def handle_data(self, data):
        if self.should_parse:
            if not self.is_in_reply:
                remaining = self.limit - self.data_length
                if len(data) > remaining:
                    self.buffer += f"{data[:remaining]}"
                    for i in reversed(self.stack):
                        self.handle_endtag(i)
                    self.stack.clear()
                    self.should_parse = False
                    self.buffer += "..."
                    return
                self.buffer += escape(data)
                self.data_length += len(data)

    def into_pango_markup(self):
        ret = self.buffer
        self.buffer = ""
        return ret

#!/usr/bin/env python3
"""
web_js_analyzer.py

Static URL analyzer for HTML and JavaScript.

Designed to work from old-style Vanilla JS through modern JavaScript /
Node.js code. It does NOT execute JavaScript.

Usage:
    python web_js_analyzer.py <file> [output-json]
    python web_js_analyzer.py <directory> [output-json]

Examples:
    python web_js_analyzer.py web/flagship.html
    python web_js_analyzer.py web/static/remote.js output.json
    python web_js_analyzer.py web output.json

For a directory, run it once per HTML/JS file; a directory mode can be
added later if desired.
"""

import ast
import json
import re
import sys
from pathlib import Path
from html.parser import HTMLParser


# ============================================================
# General helpers
# ============================================================

URL_SCHEMES = (
    "http://",
    "https://",
    "ws://",
    "wss://",
    "ftp://",
    "file://",
)

URL_ATTRIBUTES = {
    "href": "link",
    "action": "form",
    "src": "resource",
    "poster": "resource",
    "cite": "resource",
    "data": "resource",
    "formaction": "form",
    "manifest": "resource",
}

HTTP_METHODS = {
    "get": "GET",
    "post": "POST",
    "put": "PUT",
    "patch": "PATCH",
    "delete": "DELETE",
    "head": "HEAD",
    "options": "OPTIONS",
}


def looks_like_url(value):
    """Return True when a string looks like a URL/path reference."""

    if not isinstance(value, str):
        return False

    value = value.strip()

    if not value:
        return False

    lower = value.lower()

    if lower.startswith(URL_SCHEMES):
        return True

    if value.startswith(("/", "./", "../", "#", "?")):
        return True

    # Common endpoint-like strings.
    if value.startswith(("api/", "v1/", "v2/", "v3/")):
        return True

    # Avoid treating ordinary words as URLs.
    if "/" in value:
        return True

    return False


def url_kind(value):
    """Classify URL/reference scheme."""

    if not isinstance(value, str):
        return "unknown"

    lower = value.lower()

    if lower.startswith("http://"):
        return "http"

    if lower.startswith("https://"):
        return "https"

    if lower.startswith("ws://"):
        return "websocket"

    if lower.startswith("wss://"):
        return "websocket"

    if lower.startswith("ftp://"):
        return "ftp"

    if lower.startswith("file://"):
        return "file"

    if value.startswith("/"):
        return "absolute_path"

    if value.startswith(("./", "../")):
        return "relative_path"

    if value.startswith("#"):
        return "fragment"

    return "relative_or_dynamic"


def source_line(source, position):
    """Return 1-based line number for a character position."""

    return source.count("\n", 0, position) + 1


# ============================================================
# URL record
# ============================================================

class URLCollector:
    """Collect and de-duplicate URL records."""

    def __init__(self, source_file):
        self.source_file = str(source_file)
        self.urls = []
        self._keys = set()

    def add(
        self,
        url=None,
        url_type="unknown",
        line=None,
        method=None,
        expression=None,
        source=None,
        resolved=True,
        attribute=None,
        tag=None,
        api=None,
        details=None,
    ):
        if url is not None and not looks_like_url(url):
            return

        key = (
            url,
            url_type,
            line,
            method,
            expression,
        )

        if key in self._keys:
            return

        self._keys.add(key)

        record = {
            "url": url,
            "type": url_type,
            "line": line,
        }

        if method:
            record["method"] = method

        if expression:
            record["expression"] = expression

        if source:
            record["source"] = source

        record["resolved"] = bool(resolved)

        if attribute:
            record["attribute"] = attribute

        if tag:
            record["tag"] = tag

        if api:
            record["api"] = api

        if details:
            record.update(details)

        if url is not None:
            record["url_kind"] = url_kind(url)

        self.urls.append(record)


# ============================================================
# HTML analyzer
# ============================================================

class HTMLAnalyzer(HTMLParser):
    """Analyze URLs in HTML without executing embedded JavaScript."""

    def __init__(self, source, collector):
        super().__init__(
            convert_charrefs=True
        )

        self.source = source
        self.collector = collector

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        for attribute, url_type in URL_ATTRIBUTES.items():

            if attribute not in attrs_dict:
                continue

            value = attrs_dict[attribute]

            if not value:
                continue

            self.collector.add(
                url=value,
                url_type=url_type,
                line=self.getpos()[0],
                attribute=attribute,
                tag=tag,
                source=f"<{tag} {attribute}>",
            )

        # Explicit WebSocket / URL-like data attributes.
        for attribute, value in attrs:
            if not value:
                continue

            lower_attribute = attribute.lower()

            if (
                "url" in lower_attribute
                or "endpoint" in lower_attribute
                or "websocket" in lower_attribute
            ):
                if looks_like_url(value):
                    self.collector.add(
                        url=value,
                        url_type="data_url",
                        line=self.getpos()[0],
                        attribute=attribute,
                        tag=tag,
                        source=f"<{tag} {attribute}>",
                    )

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def analyze_html(source, source_file):
    collector = URLCollector(source_file)

    parser = HTMLAnalyzer(
        source,
        collector
    )

    try:
        parser.feed(source)
        parser.close()

    except Exception as error:
        # HTMLParser is intentionally forgiving, but preserve a
        # diagnostic if malformed input causes a parser error.
        collector.add(
            url=None,
            url_type="parser_error",
            line=getattr(parser, "getpos", lambda: (1, 0))()[0],
            resolved=False,
            details={
                "error": str(error)
            },
        )

    # Analyze JavaScript embedded in HTML.
    for match in re.finditer(
        r"<script\b[^>]*>(.*?)</script\s*>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        js_source = match.group(1)
        base_line = source_line(
            source,
            match.start(1)
        )

        analyze_javascript(
            js_source,
            collector,
            line_offset=base_line - 1,
            source_name="inline <script>",
        )

    return collector


# ============================================================
# JavaScript static analyzer
# ============================================================

class JavaScriptAnalyzer:
    """
    Regex/token-oriented JavaScript analyzer.

    This deliberately does not attempt to parse JavaScript with Python's
    ast module because JavaScript syntax differs substantially from Python.

    It therefore works across:
        - Vanilla JS
        - ES5
        - ES6+
        - async/await
        - modules
        - CommonJS
        - Node.js-style code
        - fetch
        - XMLHttpRequest
        - WebSocket
        - Axios
        - jQuery AJAX
        - Node http/https
        - URL constructors
        - location/navigation APIs

    Dynamic expressions are retained rather than executed.
    """

    def __init__(
        self,
        source,
        collector,
        line_offset=0,
        source_name=None,
    ):
        self.source = source
        self.collector = collector
        self.line_offset = line_offset
        self.source_name = source_name or "javascript"

    def line(self, position):
        return source_line(
            self.source,
            position
        ) + self.line_offset

    def add(
        self,
        url,
        url_type,
        position,
        method=None,
        expression=None,
        api=None,
        resolved=True,
        details=None,
    ):
        self.collector.add(
            url=url,
            url_type=url_type,
            line=self.line(position),
            method=method,
            expression=expression,
            source=self.source_name,
            api=api,
            resolved=resolved,
            details=details,
        )

    def run(self):
        self.find_fetch()
        self.find_websocket()
        self.find_xhr()
        self.find_jquery_ajax()
        self.find_axios()
        self.find_node_http()
        self.find_location()
        self.find_window_open()
        self.find_history()
        self.find_imports()
        self.find_static_url_strings()

    # --------------------------------------------------------
    # String extraction
    # --------------------------------------------------------

    @staticmethod
    def string_value(text):
        """
        Decode a simple JS string literal.

        Handles:
            "..."
            '...'
            `...`
        """

        text = text.strip()

        if len(text) < 2:
            return None

        if text[0] not in ("'", '"', "`"):
            return None

        if text[-1] != text[0]:
            return None

        body = text[1:-1]

        # Do not claim that a template literal with ${...} is static.
        if text[0] == "`" and "${" in body:
            return None

        try:
            # Conservative JS-string escape handling.
            body = (
                body
                .replace(r"\/", "/")
                .replace(r"\'", "'")
                .replace(r'\"', '"')
                .replace(r"\n", "\n")
                .replace(r"\r", "\r")
                .replace(r"\t", "\t")
                .replace(r"\\", "\\")
            )
        except Exception:
            pass

        return body

    @staticmethod
    def split_call_arguments(text):
        """
        Split a JavaScript argument list while respecting strings and
        nested brackets. This is intentionally lightweight.
        """

        args = []
        start = 0
        depth = 0
        quote = None
        escaped = False

        for index, char in enumerate(text):

            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue

            if char in ("'", '"', "`"):
                quote = char
                continue

            if char in "([{":
                depth += 1

            elif char in ")]}":
                depth -= 1

            elif char == "," and depth == 0:
                args.append(
                    text[start:index].strip()
                )
                start = index + 1

        tail = text[start:].strip()

        if tail:
            args.append(tail)

        return args

    # --------------------------------------------------------
    # Find complete-ish function calls
    # --------------------------------------------------------

    def find_calls(self, pattern):
        """
        Find function names followed by (...) and return:
            position, argument_text
        """

        results = []

        for match in re.finditer(
            pattern,
            self.source,
            flags=re.IGNORECASE,
        ):
            open_pos = match.end() - 1

            depth = 0
            quote = None
            escaped = False

            for index in range(
                open_pos,
                len(self.source)
            ):
                char = self.source[index]

                if quote:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == quote:
                        quote = None
                    continue

                if char in ("'", '"', "`"):
                    quote = char
                    continue

                if char == "(":
                    depth += 1

                elif char == ")":
                    depth -= 1

                    if depth == 0:
                        results.append(
                            (
                                match.start(),
                                self.source[
                                    open_pos + 1:index
                                ],
                            )
                        )
                        break

        return results

    # --------------------------------------------------------
    # fetch()
    # --------------------------------------------------------

    def find_fetch(self):
        for position, args_text in self.find_calls(
            r"\bfetch\s*\("
        ):
            args = self.split_call_arguments(
                args_text
            )

            if not args:
                continue

            expression = args[0]
            value = self.string_value(
                expression
            )

            method = "GET"

            # fetch(url, { method: "POST" })
            if len(args) >= 2:
                method_match = re.search(
                    r"""\bmethod\s*:\s*(['"`])([A-Za-z]+)\1""",
                    args[1],
                    flags=re.IGNORECASE,
                )

                if method_match:
                    method = method_match.group(2).upper()

            if value is not None:
                self.add(
                    url=value,
                    url_type="fetch",
                    position=position,
                    method=method,
                    expression=expression,
                    api="fetch",
                )
            else:
                self.add(
                    url=None,
                    url_type="fetch",
                    position=position,
                    method=method,
                    expression=expression,
                    api="fetch",
                    resolved=False,
                )

    # --------------------------------------------------------
    # WebSocket
    # --------------------------------------------------------

    def find_websocket(self):
        for position, args_text in self.find_calls(
            r"\bnew\s+WebSocket\s*\("
        ):
            args = self.split_call_arguments(
                args_text
            )

            if not args:
                continue

            expression = args[0]
            value = self.string_value(
                expression
            )

            if value is not None:
                self.add(
                    url=value,
                    url_type="websocket",
                    position=position,
                    expression=expression,
                    api="WebSocket",
                )
            else:
                self.add(
                    url=None,
                    url_type="websocket",
                    position=position,
                    expression=expression,
                    api="WebSocket",
                    resolved=False,
                )

    # --------------------------------------------------------
    # XMLHttpRequest
    # --------------------------------------------------------

    def find_xhr(self):
        # xhr.open("GET", "/api/status")
        pattern = (
            r"\b[A-Za-z_$][\w$]*\s*\.\s*open\s*\("
        )

        for position, args_text in self.find_calls(
            pattern
        ):
            args = self.split_call_arguments(
                args_text
            )

            if len(args) < 2:
                continue

            method = self.string_value(args[0])
            expression = args[1]
            value = self.string_value(expression)

            if method is None:
                method = "UNKNOWN"
            else:
                method = method.upper()

            if value is not None:
                self.add(
                    url=value,
                    url_type="xhr",
                    position=position,
                    method=method,
                    expression=expression,
                    api="XMLHttpRequest.open",
                )
            else:
                self.add(
                    url=None,
                    url_type="xhr",
                    position=position,
                    method=method,
                    expression=expression,
                    api="XMLHttpRequest.open",
                    resolved=False,
                )

    # --------------------------------------------------------
    # jQuery AJAX
    # --------------------------------------------------------

    def find_jquery_ajax(self):
        # $.ajax({...}) and jQuery.ajax({...})
        for pattern, api in (
            (r"\$\s*\.\s*ajax\s*\(", "$.ajax"),
            (r"\bjQuery\s*\.\s*ajax\s*\(", "jQuery.ajax"),
        ):
            for position, args_text in self.find_calls(pattern):
                self.analyze_ajax_object(
                    args_text,
                    position,
                    api
                )

        # $.get("/x"), $.post("/x"), etc.
        for method_name, method in HTTP_METHODS.items():
            for pattern in (
                rf"\$\s*\.\s*{method_name}\s*\(",
                rf"\bjQuery\s*\.\s*{method_name}\s*\(",
            ):
                for position, args_text in self.find_calls(pattern):
                    args = self.split_call_arguments(args_text)

                    if not args:
                        continue

                    expression = args[0]
                    value = self.string_value(expression)

                    if value is not None:
                        self.add(
                            url=value,
                            url_type="ajax",
                            position=position,
                            method=method,
                            expression=expression,
                            api=f"jQuery.{method_name}",
                        )
                    else:
                        self.add(
                            url=None,
                            url_type="ajax",
                            position=position,
                            method=method,
                            expression=expression,
                            api=f"jQuery.{method_name}",
                            resolved=False,
                        )

    def analyze_ajax_object(
        self,
        args_text,
        position,
        api,
    ):
        url_match = re.search(
            r"""\burl\s*:\s*(['"`])(.+?)\1""",
            args_text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        method_match = re.search(
            r"""\btype\s*:\s*(['"`])([A-Za-z]+)\1""",
            args_text,
            flags=re.IGNORECASE,
        )

        if method_match is None:
            method_match = re.search(
                r"""\bmethod\s*:\s*(['"`])([A-Za-z]+)\1""",
                args_text,
                flags=re.IGNORECASE,
            )

        method = (
            method_match.group(2).upper()
            if method_match
            else "GET"
        )

        if url_match:
            value = url_match.group(2)

            self.add(
                url=value,
                url_type="ajax",
                position=position,
                method=method,
                expression=url_match.group(0),
                api=api,
            )
        else:
            self.add(
                url=None,
                url_type="ajax",
                position=position,
                method=method,
                expression="url: <dynamic>",
                api=api,
                resolved=False,
            )

    # --------------------------------------------------------
    # Axios
    # --------------------------------------------------------

    def find_axios(self):
        for method_name, method in HTTP_METHODS.items():
            pattern = (
                rf"\baxios\s*\.\s*{method_name}\s*\("
            )

            for position, args_text in self.find_calls(pattern):
                args = self.split_call_arguments(args_text)

                if not args:
                    continue

                expression = args[0]
                value = self.string_value(expression)

                if value is not None:
                    self.add(
                        url=value,
                        url_type="axios",
                        position=position,
                        method=method,
                        expression=expression,
                        api=f"axios.{method_name}",
                    )
                else:
                    self.add(
                        url=None,
                        url_type="axios",
                        position=position,
                        method=method,
                        expression=expression,
                        api=f"axios.{method_name}",
                        resolved=False,
                    )

        # axios({ method: "POST", url: "/api/x" })
        for position, args_text in self.find_calls(
            r"\baxios\s*\("
        ):
            url_match = re.search(
                r"""\burl\s*:\s*(['"`])(.+?)\1""",
                args_text,
                flags=re.IGNORECASE | re.DOTALL,
            )

            if not url_match:
                continue

            method_match = re.search(
                r"""\bmethod\s*:\s*(['"`])([A-Za-z]+)\1""",
                args_text,
                flags=re.IGNORECASE,
            )

            method = (
                method_match.group(2).upper()
                if method_match
                else "GET"
            )

            self.add(
                url=url_match.group(2),
                url_type="axios",
                position=position,
                method=method,
                expression=url_match.group(0),
                api="axios",
            )

    # --------------------------------------------------------
    # Node.js http / https
    # --------------------------------------------------------

    def find_node_http(self):
        """
        Detect common Node.js forms such as:

            http.get("http://...")
            https.get("https://...")

        and:

            http.request({ hostname: ..., path: ... })
            https.request(...)
        """

        for protocol in ("http", "https"):
            for method_name, method in (
                ("get", "GET"),
                ("request", "REQUEST"),
            ):
                pattern = (
                    rf"\b{protocol}\s*\.\s*"
                    rf"{method_name}\s*\("
                )

                for position, args_text in self.find_calls(pattern):
                    args = self.split_call_arguments(
                        args_text
                    )

                    if not args:
                        continue

                    first = args[0]
                    value = self.string_value(first)

                    if value is not None and looks_like_url(value):
                        self.add(
                            url=value,
                            url_type="node_http",
                            position=position,
                            method=method,
                            expression=first,
                            api=f"{protocol}.{method_name}",
                        )
                        continue

                    # options object
                    url_match = re.search(
                        r"""\b(?:url|href)\s*:\s*(['"`])(.+?)\1""",
                        first,
                        flags=re.IGNORECASE | re.DOTALL,
                    )

                    path_match = re.search(
                        r"""\bpath\s*:\s*(['"`])(.+?)\1""",
                        first,
                        flags=re.IGNORECASE | re.DOTALL,
                    )

                    if url_match:
                        self.add(
                            url=url_match.group(2),
                            url_type="node_http",
                            position=position,
                            method=method,
                            expression=url_match.group(0),
                            api=f"{protocol}.{method_name}",
                        )

                    elif path_match:
                        self.add(
                            url=path_match.group(2),
                            url_type="node_http",
                            position=position,
                            method=method,
                            expression=path_match.group(0),
                            api=f"{protocol}.{method_name}",
                        )

                    else:
                        self.add(
                            url=None,
                            url_type="node_http",
                            position=position,
                            method=method,
                            expression=first,
                            api=f"{protocol}.{method_name}",
                            resolved=False,
                        )

    # --------------------------------------------------------
    # location / navigation
    # --------------------------------------------------------

    def find_location(self):
        patterns = [
            (
                r"\b(?:window\.)?location\s*\.\s*"
                r"(?:href|assign|replace)\s*=\s*",
                "location",
            ),
            (
                r"\b(?:window\.)?location\s*\.\s*"
                r"(?:assign|replace)\s*\(",
                "location",
            ),
        ]

        for pattern, api in patterns:
            for match in re.finditer(
                pattern,
                self.source,
                flags=re.IGNORECASE,
            ):
                position = match.start()

                tail = self.source[
                    match.end():
                ]

                string_match = re.match(
                    r"""\s*(['"`])(.+?)\1""",
                    tail,
                    flags=re.DOTALL,
                )

                if string_match:
                    self.add(
                        url=string_match.group(2),
                        url_type="redirect",
                        position=position,
                        expression=string_match.group(0).strip(),
                        api=api,
                    )
                else:
                    self.add(
                        url=None,
                        url_type="redirect",
                        position=position,
                        expression=tail[:100].strip(),
                        api=api,
                        resolved=False,
                    )

    # --------------------------------------------------------
    # window.open()
    # --------------------------------------------------------

    def find_window_open(self):
        for position, args_text in self.find_calls(
            r"\bwindow\s*\.\s*open\s*\("
        ):
            args = self.split_call_arguments(args_text)

            if not args:
                continue

            expression = args[0]
            value = self.string_value(expression)

            if value is not None:
                self.add(
                    url=value,
                    url_type="navigation",
                    position=position,
                    expression=expression,
                    api="window.open",
                )
            else:
                self.add(
                    url=None,
                    url_type="navigation",
                    position=position,
                    expression=expression,
                    api="window.open",
                    resolved=False,
                )

    # --------------------------------------------------------
    # History API
    # --------------------------------------------------------

    def find_history(self):
        for method_name in (
            "pushState",
            "replaceState",
        ):
            pattern = (
                rf"\bhistory\s*\.\s*"
                rf"{method_name}\s*\("
            )

            for position, args_text in self.find_calls(pattern):
                args = self.split_call_arguments(args_text)

                # pushState(state, title, url)
                if len(args) < 3:
                    continue

                expression = args[2]
                value = self.string_value(expression)

                if value is not None:
                    self.add(
                        url=value,
                        url_type="navigation",
                        position=position,
                        expression=expression,
                        api=f"history.{method_name}",
                    )
                else:
                    self.add(
                        url=None,
                        url_type="navigation",
                        position=position,
                        expression=expression,
                        api=f"history.{method_name}",
                        resolved=False,
                    )

    # --------------------------------------------------------
    # ES modules / CommonJS
    # --------------------------------------------------------

    def find_imports(self):
        # import "..."; dynamic import("...")
        for match in re.finditer(
            r"""\bimport\s*\(\s*(['"`])(.+?)\1\s*\)""",
            self.source,
            flags=re.DOTALL,
        ):
            self.add(
                url=match.group(2),
                url_type="module",
                position=match.start(),
                expression=match.group(0),
                api="import()",
            )

        # Static ES module imports.
        for match in re.finditer(
            r"\bimport\s+(?:.+?\s+from\s+)?"
            r"""(['"`])(.+?)\1""",
            self.source,
            flags=re.DOTALL,
        ):
            value = match.group(2)

            if value.startswith(("./", "../", "/")):
                self.add(
                    url=value,
                    url_type="module",
                    position=match.start(),
                    expression=match.group(0),
                    api="import",
                )

        # CommonJS require()
        for position, args_text in self.find_calls(
            r"\brequire\s*\("
        ):
            args = self.split_call_arguments(args_text)

            if not args:
                continue

            expression = args[0]
            value = self.string_value(expression)

            if value is not None and (
                value.startswith(("./", "../", "/"))
                or looks_like_url(value)
            ):
                self.add(
                    url=value,
                    url_type="module",
                    position=position,
                    expression=expression,
                    api="require",
                )

    # --------------------------------------------------------
    # Static strings
    # --------------------------------------------------------

    def find_static_url_strings(self):
        """
        Find URL-like string literals not already captured by a
        specific API. These are useful as a safety net, but are
        labeled 'string_url' rather than pretending to know how
        the application uses them.
        """

        pattern = (
            r"""""(?P<quote>['"`])"""""
            r"""(?P<value>(?:\\.|(?!\1).)*?)"""
            r"""(?P=quote)"""
        )

        for match in re.finditer(
            pattern,
            self.source,
            flags=re.DOTALL,
        ):
            value = match.group("value")

            if not looks_like_url(value):
                continue

            # Ignore obvious CSS/JS file imports already captured
            # only when they are module references; otherwise keep
            # the string because it may still be meaningful.
            self.add(
                url=value,
                url_type="string_url",
                position=match.start(),
                expression=match.group(0),
                api="literal",
            )


def analyze_javascript(
    source,
    collector,
    line_offset=0,
    source_name=None,
):
    analyzer = JavaScriptAnalyzer(
        source,
        collector,
        line_offset=line_offset,
        source_name=source_name,
    )

    analyzer.run()

    return collector


# ============================================================
# Report construction
# ============================================================

def build_report(
    source_file,
    file_type,
    source,
    collector,
):
    counts = {}

    for item in collector.urls:
        url_type = item["type"]
        counts[url_type] = (
            counts.get(url_type, 0) + 1
        )

    # Sort by source line while keeping unresolved entries.
    urls = sorted(
        collector.urls,
        key=lambda item: (
            item.get("line") or 0,
            item.get("type") or "",
            item.get("url") or "",
        ),
    )

    return {
        "analyzer_version": "2.0",
        "source_file": str(source_file),
        "file_type": file_type,
        "urls": urls,
        "summary": {
            "total": len(urls),
            "by_type": counts,
        },
    }


# ============================================================
# Analyze one file
# ============================================================

def analyze_file(source_file):
    source_file = Path(source_file)

    source = source_file.read_text(
        encoding="utf-8"
    )

    suffix = source_file.suffix.lower()

    if suffix in (".html", ".htm"):
        file_type = "html"

        collector = analyze_html(
            source,
            source_file
        )

    elif suffix in (".js", ".mjs", ".cjs"):
        file_type = "javascript"

        collector = URLCollector(
            source_file
        )

        analyze_javascript(
            source,
            collector,
            source_name="javascript"
        )

    else:
        raise ValueError(
            "Supported file types are "
            ".html, .htm, .js, .mjs and .cjs"
        )

    return build_report(
        source_file,
        file_type,
        source,
        collector
    )


# ============================================================
# Human-readable output
# ============================================================

def print_report(report):
    print()
    print("=" * 80)
    print("HTML / JAVASCRIPT URL ANALYSIS")
    print("=" * 80)

    print()
    print(
        f'Source: {report["source_file"]}'
    )

    print(
        f'Type:   {report["file_type"]}'
    )

    print()

    if not report["urls"]:
        print("No URLs found.")
        return

    print("URLs")
    print("-" * 80)

    for item in report["urls"]:
        line = item.get("line", "?")
        url_type = item.get("type", "unknown")
        url = item.get("url")

        if url is None:
            url = (
                "[dynamic] "
                + item.get(
                    "expression",
                    "<unknown>"
                )
            )

        method = item.get("method")

        method_text = (
            f"{method} "
            if method
            else ""
        )

        print(
            f"line {line:>5}  "
            f"{method_text:<7}"
            f"{url_type:<16} "
            f"{url}"
        )

    print()
    print("SUMMARY")
    print("-" * 80)

    print(
        f'Total URLs/references: '
        f'{report["summary"]["total"]}'
    )

    for key, value in sorted(
        report["summary"]["by_type"].items()
    ):
        print(
            f"  {key:<20} {value}"
        )



# ============================================================
# Recursive directory analyzer - Version 2
# ============================================================

SUPPORTED_HTML = {".html", ".htm"}
SUPPORTED_JS = {".js", ".mjs", ".cjs"}


def discover_web_files(input_directory):
    """
    Recursively find all HTML and JavaScript files.

    Hidden directories are skipped, as are common generated/dependency
    directories such as node_modules, .git, __pycache__, dist and build.
    """

    root = Path(input_directory).resolve()

    ignored_directories = {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
        ".cache",
    }

    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        # Skip files inside ignored directories.
        relative_parts = path.relative_to(root).parts

        if any(
            part in ignored_directories
            for part in relative_parts[:-1]
        ):
            continue

        # Skip hidden files.
        if path.name.startswith("."):
            continue

        suffix = path.suffix.lower()

        if suffix in SUPPORTED_HTML or suffix in SUPPORTED_JS:
            files.append(path)

    return sorted(files)


def build_directory_report(input_directory, file_reports):
    """
    Build the final JSON document for an entire web directory.
    """

    root = Path(input_directory).resolve()

    html_files = []
    javascript_files = []

    all_urls = []

    for report in file_reports:
        source_path = Path(
            report["source_file"]
        ).resolve()

        try:
            relative_path = str(
                source_path.relative_to(root)
            )
        except ValueError:
            relative_path = str(source_path)

        report["source_file_absolute"] = str(
            source_path
        )
        report["source_file_relative"] = relative_path

        # Keep source_file for backward compatibility, but the
        # relative path is the useful developer-documentation value.
        if report["file_type"] == "html":
            html_files.append(report)

        elif report["file_type"] == "javascript":
            javascript_files.append(report)

        for url in report.get("urls", []):
            url_copy = dict(url)
            url_copy["source_file"] = relative_path
            all_urls.append(url_copy)

    by_type = {}

    for item in all_urls:
        key = item.get("type", "unknown")
        by_type[key] = by_type.get(key, 0) + 1

    return {
        "analyzer_version": "2.0",
        "input_directory": str(root),
        "summary": {
            "total_files": len(file_reports),
            "html_files": len(html_files),
            "javascript_files": len(javascript_files),
            "total_urls_and_references": len(all_urls),
            "urls_by_type": by_type,
        },
        "files": {
            "html": html_files,
            "javascript": javascript_files,
        },
        "all_urls": all_urls,
    }


def analyze_directory(input_directory):
    """
    Recursively analyze every HTML and JavaScript file in a directory.
    """

    root = Path(input_directory).resolve()

    if not root.is_dir():
        raise ValueError(
            f"Input directory does not exist: {root}"
        )

    discovered_files = discover_web_files(root)

    file_reports = []
    errors = []

    for source_file in discovered_files:
        try:
            report = analyze_file(source_file)
            file_reports.append(report)

        except Exception as error:
            errors.append({
                "source_file": str(
                    source_file.relative_to(root)
                ),
                "error": str(error),
            })

    report = build_directory_report(
        root,
        file_reports
    )

    report["errors"] = errors

    return report


def print_directory_report(report):
    print()
    print("=" * 80)
    print("RECURSIVE HTML / JAVASCRIPT URL ANALYSIS - VERSION 2")
    print("=" * 80)

    print()
    print(
        f'Input directory: '
        f'{report["input_directory"]}'
    )

    summary = report["summary"]

    print()
    print("SUMMARY")
    print("-" * 80)

    print(
        f'HTML files:                 '
        f'{summary["html_files"]}'
    )

    print(
        f'JavaScript files:           '
        f'{summary["javascript_files"]}'
    )

    print(
        f'Total files:                '
        f'{summary["total_files"]}'
    )

    print(
        f'Total URLs/references:      '
        f'{summary["total_urls_and_references"]}'
    )

    print()
    print("FILES")
    print("-" * 80)

    for file_type in ("html", "javascript"):
        print()
        print(
            file_type.upper()
        )

        for report_item in report["files"][file_type]:
            relative = report_item[
                "source_file_relative"
            ]

            count = len(
                report_item.get("urls", [])
            )

            print(
                f"    {relative:<60} "
                f"{count} URL/reference(s)"
            )

    if report.get("errors"):
        print()
        print("ERRORS")
        print("-" * 80)

        for item in report["errors"]:
            print(
                f'    {item["source_file"]}: '
                f'{item["error"]}'
            )

    print()
    print("URL TYPES")
    print("-" * 80)

    for key, value in sorted(
        summary["urls_by_type"].items()
    ):
        print(
            f"    {key:<25} {value}"
        )



# ============================================================
# Main
# ============================================================

def main():
    if len(sys.argv) not in (2, 3):
        print(
            "Usage:\n"
            "  Single file:\n"
            "    python web_js_analyzer.py <file> [output-json]\n\n"
            "  Recursive directory:\n"
            "    python web_js_analyzer.py <directory> [output-json]"
        )
        sys.exit(1)

    input_path = Path(
        sys.argv[1]
    )

    if not input_path.exists():
        print(
            f"ERROR: Path not found: "
            f"{input_path}"
        )
        sys.exit(1)

    try:
        if input_path.is_dir():
            report = analyze_directory(
                input_path
            )

            print_directory_report(
                report
            )

        else:
            report = analyze_file(
                input_path
            )

            print_report(
                report
            )

    except UnicodeDecodeError as error:
        print(
            "ERROR: File is not valid UTF-8:"
        )
        print(error)
        sys.exit(1)

    except Exception as error:
        print(
            f"ERROR: {error}"
        )
        sys.exit(1)

    if len(sys.argv) == 3:
        output_file = Path(
            sys.argv[2]
        )

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print()
        print(
            "JSON written to:"
        )
        print(
            f"    {output_file}"
        )


if __name__ == "__main__":
    main()

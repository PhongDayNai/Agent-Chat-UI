"""Assistant markdown rendering helpers."""

import re
from html import escape
from urllib.parse import quote

try:
    from markdown_it import MarkdownIt
    from markdown_it.common.utils import escapeHtml
except ImportError:
    MarkdownIt = None
    escapeHtml = None

try:
    from mdit_py_plugins.tasklists import tasklists_plugin
except ImportError:
    tasklists_plugin = None

from constants import TRAILING_URL_PUNCTUATION, URL_RE

LATEX_COMMAND_REPLACEMENTS = {
    r"\leq": "<=",
    r"\geq": ">=",
    r"\neq": "!=",
    r"\times": "x",
    r"\cdot": "*",
    r"\to": "->",
    r"\rightarrow": "->",
    r"\leftarrow": "<-",
    r"\Rightarrow": "=>",
    r"\approx": "~",
    r"\pm": "+/-",
    r"\infty": "infinity",
    r"\alpha": "alpha",
    r"\beta": "beta",
    r"\gamma": "gamma",
    r"\delta": "delta",
    r"\lambda": "lambda",
    r"\mu": "mu",
    r"\pi": "pi",
    r"\sigma": "sigma",
    r"\theta": "theta",
}

MARKDOWN_RENDERER = None


def render_latexish_text(text):
    if not text:
        return text

    fence_pattern = re.compile(r"(```[\s\S]*?(?:```|$))")
    inline_code_pattern = re.compile(r"(`[^`\n]+`)")

    def replace_math_segment(match):
        return normalize_latexish_segment(match.group(1))

    parts = fence_pattern.split(text)
    processed_parts = []
    for part in parts:
        if part.startswith("```"):
            processed_parts.append(part)
            continue

        inline_parts = inline_code_pattern.split(part)
        for index, inline_part in enumerate(inline_parts):
            if inline_part.startswith("`") and inline_part.endswith("`"):
                continue
            inline_part = re.sub(r"\\\(([\s\S]*?)\\\)", replace_math_segment, inline_part)
            inline_part = re.sub(r"\\\[([\s\S]*?)\\\]", replace_math_segment, inline_part)
            inline_part = re.sub(r"\$([^$\n]+)\$", replace_math_segment, inline_part)
            inline_parts[index] = inline_part
        processed_parts.append("".join(inline_parts))

    return "".join(processed_parts)


def normalize_latexish_segment(text):
    text = text.strip()
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
    text = re.sub(r"([A-Za-z0-9)\]}])\s*\^\s*\{([^{}]+)\}", r"\1^(\2)", text)
    text = re.sub(r"([A-Za-z0-9)\]}])\s*\^\s*([A-Za-z0-9]+)", r"\1^\2", text)
    text = re.sub(r"([A-Za-z0-9)\]}])\s*_\s*\{([^{}]+)\}", r"\1_(\2)", text)
    text = re.sub(r"([A-Za-z0-9)\]}])\s*_\s*([A-Za-z0-9]+)", r"\1_\2", text)
    for command, replacement in LATEX_COMMAND_REPLACEMENTS.items():
        text = text.replace(command, replacement)
    text = text.replace("\\", "")
    return text


def prepare_assistant_markdown(text):
    return prepare_assistant_html(text)


def prepare_assistant_html(text):
    text = text or "..."
    return html_document(render_markdown_blocks(text))


def html_document(body):
    return (
        "<html><head><style>"
        "body{color:#e8eaed;font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:15px;line-height:1.55;}"
        "p{margin:0 0 10px 0;}"
        "h1,h2,h3,h4{color:#f4f5f6;margin:12px 0 8px 0;}"
        "ul,ol{margin-top:4px;margin-bottom:10px;}"
        "li{margin-bottom:4px;}"
        "blockquote{color:#c7cacf;margin:10px 0;padding-left:12px;border-left:3px solid #3a3f44;}"
        "table{border-collapse:collapse;margin:8px 0 12px 0;}"
        "th,td{border:1px solid #30363d;padding:6px 8px;}"
        "th{background:#15191d;color:#f4f5f6;font-weight:700;}"
        "td{color:#e8eaed;}"
        "hr{border:0;border-top:1px solid #30363d;margin:14px 0;}"
        "s{color:#aeb4ba;}"
        "a{color:#57a6ff;text-decoration:underline;}"
        "a:hover{color:#2f7ed8;text-decoration:underline;}"
        "pre{margin:0 0 12px 0;padding:12px;background:#090b0d;border:1px solid #30363d;"
        "color:#dbe7f3;font-family:'IBM Plex Mono','Consolas',monospace;white-space:pre-wrap;}"
        "code{color:#ffd18a;background-color:#15191d;font-family:'IBM Plex Mono','Consolas',monospace;}"
        "</style></head><body>"
        f"{body}"
        "</body></html>"
    )


def get_markdown_renderer():
    global MARKDOWN_RENDERER
    if MARKDOWN_RENDERER is not None:
        return MARKDOWN_RENDERER
    if MarkdownIt is None:
        return None

    try:
        renderer = MarkdownIt(
            "gfm-like",
            {
                "html": False,
                "linkify": True,
                "typographer": False,
                "breaks": False,
            },
        )
    except Exception:
        renderer = MarkdownIt(
            "commonmark",
            {
                "html": False,
                "linkify": False,
                "typographer": False,
                "breaks": False,
            },
        )
        for rule_name in ("table", "strikethrough"):
            try:
                renderer.enable(rule_name)
            except Exception:
                pass

    if tasklists_plugin is not None:
        try:
            renderer.use(tasklists_plugin, enabled=True)
        except TypeError:
            renderer.use(tasklists_plugin)
        except Exception:
            pass

    def render_code_inline(tokens, idx, _options, _env):
        return render_inline_code_link(tokens[idx].content)

    renderer.renderer.rules["code_inline"] = render_code_inline
    MARKDOWN_RENDERER = renderer
    return MARKDOWN_RENDERER


def render_markdown_blocks(text):
    parts = []
    for segment_type, content, language in split_markdown_code_segments(text):
        if segment_type == "code":
            parts.append(render_code_block_html(content, language))
        else:
            parts.append(render_text_markdown_html(render_latexish_text(content)))
    return "".join(parts)


def split_markdown_code_segments(text):
    parts = []
    lines = text.splitlines(keepends=True)
    text_buffer = []
    code_buffer = []
    in_code = False
    fence_char = ""
    fence_length = 0
    language = ""

    def flush_text():
        if text_buffer:
            parts.append(("text", "".join(text_buffer), ""))
            text_buffer.clear()

    def flush_code():
        parts.append(("code", "".join(code_buffer), language))
        code_buffer.clear()

    for line in lines:
        if not in_code:
            open_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})([^\n\r]*)[\r\n]*$", line)
            if open_match:
                flush_text()
                marker = open_match.group(1)
                fence_char = marker[0]
                fence_length = len(marker)
                language = open_match.group(2).strip()
                in_code = True
                continue
            text_buffer.append(line)
            continue

        close_match = re.match(
            r"^[ \t]{0,3}(" + re.escape(fence_char) + r"{" + str(fence_length) + r",})[ \t]*[\r\n]*$",
            line,
        )
        if close_match:
            flush_code()
            in_code = False
            fence_char = ""
            fence_length = 0
            language = ""
        else:
            code_buffer.append(line)

    if in_code:
        flush_code()
    else:
        flush_text()
    return parts


def render_text_markdown_html(text):
    renderer = get_markdown_renderer()
    if renderer is not None:
        try:
            return normalize_markdown_renderer_html(renderer.render(text or ""))
        except Exception:
            pass

    lines = text.splitlines()
    parts = []
    paragraph = []
    list_items = []
    list_kind = None

    def flush_paragraph():
        if paragraph:
            parts.append(f"<p>{'<br>'.join(inline_markdown_html(line) for line in paragraph)}</p>")
            paragraph.clear()

    def flush_list():
        nonlocal list_kind
        if list_items:
            tag = "ol" if list_kind == "ol" else "ul"
            parts.append(f"<{tag}>")
            for item in list_items:
                parts.append(f"<li>{inline_markdown_html(item)}</li>")
            parts.append(f"</{tag}>")
            list_items.clear()
            list_kind = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
        quote_match = re.match(r"^>\s?(.+)$", stripped)

        if heading:
            flush_paragraph()
            flush_list()
            level = len(heading.group(1))
            parts.append(f"<h{level}>{inline_markdown_html(heading.group(2))}</h{level}>")
        elif bullet:
            flush_paragraph()
            if list_kind not in {None, "ul"}:
                flush_list()
            list_kind = "ul"
            list_items.append(bullet.group(1))
        elif ordered:
            flush_paragraph()
            if list_kind not in {None, "ol"}:
                flush_list()
            list_kind = "ol"
            list_items.append(ordered.group(1))
        elif quote_match:
            flush_paragraph()
            flush_list()
            parts.append(f"<blockquote>{inline_markdown_html(quote_match.group(1))}</blockquote>")
        else:
            flush_list()
            paragraph.append(stripped)

    flush_paragraph()
    flush_list()
    return "".join(parts)


def normalize_markdown_renderer_html(html):
    html = re.sub(
        r'<input\b(?=[^>]*\bchecked="checked")[^>]*>',
        "☑",
        html,
    )
    html = re.sub(
        r"<input\b[^>]*>",
        "☐",
        html,
    )
    html = re.sub(r'<li class="task-list-item(?: enabled)?">', "<li>", html)
    html = html.replace('<ul class="contains-task-list">', "<ul>")
    return html


def inline_markdown_html(text):
    html, _index = parse_inline_markdown(text or "", 0, None)
    return html


def parse_inline_markdown(text, start_index=0, end_marker=None):
    parts = []
    index = start_index
    while index < len(text):
        if end_marker and text.startswith(end_marker, index):
            return "".join(parts), index + len(end_marker)

        if text[index] == "\\" and index + 1 < len(text):
            if text[index + 1] in r"\`*_{}[]()#+-.!|>":
                parts.append(escape(text[index + 1], quote=False))
                index += 2
            else:
                parts.append("\\")
                index += 1
            continue

        if text[index] == "`":
            closing = text.find("`", index + 1)
            if closing != -1:
                parts.append(render_inline_code_link(text[index + 1:closing]))
                index = closing + 1
                continue

        if text.startswith("**", index) or text.startswith("__", index):
            marker = text[index:index + 2]
            closing = text.find(marker, index + 2)
            if closing != -1:
                inner_html, _unused = parse_inline_markdown(text[index + 2:closing], 0, None)
                parts.append(f"<strong>{inner_html}</strong>")
                index = closing + 2
                continue

        if text[index] == "*" and not text.startswith("**", index):
            closing = text.find("*", index + 1)
            if closing != -1:
                inner_html, _unused = parse_inline_markdown(text[index + 1:closing], 0, None)
                parts.append(f"<em>{inner_html}</em>")
                index = closing + 1
                continue

        link_match = re.match(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text[index:])
        if link_match:
            label_html, _unused = parse_inline_markdown(link_match.group(1), 0, None)
            href = escape(link_match.group(2), quote=True)
            parts.append(f'<a href="{href}">{label_html}</a>')
            index += link_match.end()
            continue

        url_match = URL_RE.match(text, index)
        if url_match:
            raw_url = url_match.group(0)
            url = raw_url.rstrip(TRAILING_URL_PUNCTUATION)
            trailing = raw_url[len(url):]
            if url:
                safe_url = escape(url, quote=True)
                parts.append(f'<a href="{safe_url}">{escape(url, quote=False)}</a>')
                if trailing:
                    parts.append(escape(trailing, quote=False))
                index = url_match.end()
                continue

        next_index = next_inline_special_index(text, index + 1)
        parts.append(escape(text[index:next_index], quote=False))
        index = next_index
    return "".join(parts), index


def next_inline_special_index(text, start_index):
    candidates = [len(text)]
    for marker in ["\\", "`", "**", "__", "*", "[", "http://", "https://"]:
        marker_index = text.find(marker, start_index)
        if marker_index != -1:
            candidates.append(marker_index)
    return min(candidates)


def render_inline_code_html(code):
    safe_code = escapeHtml(code) if escapeHtml is not None else escape(code, quote=False)
    return (
        '<span style="'
        "color:#ffd18a; "
        "background-color:#15191d; "
        "font-family:IBM Plex Mono, Consolas, monospace;"
        f'">{safe_code}</span>'
    )


def render_inline_code_link(code):
    safe_code = escapeHtml(code) if escapeHtml is not None else escape(code, quote=False)
    href = copy_code_href(code)
    return (
        f'<a href="{href}" style="'
        "color:#ffd18a; "
        "background-color:#15191d; "
        "text-decoration:none; "
        "font-family:IBM Plex Mono, Consolas, monospace;"
        f'">{safe_code}</a>'
    )


def render_code_block_html(code, language=""):
    code = code.rstrip("\n")
    safe_code = escape(code, quote=False)
    language_label = escape(language, quote=False) if language else "code"
    return (
        '<p style="margin:8px 0 4px 0; color:#8c9298; font-size:12px;">'
        f"{language_label}"
        "</p>"
        "<pre>"
        f"{safe_code or '&nbsp;'}</pre>"
    )


def copy_code_href(text):
    return f"copy-code:{quote(text, safe='')}"


def html_text_with_links(text):
    text = text or ""
    inline_code_pattern = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
    parts = []
    last_index = 0
    for match in inline_code_pattern.finditer(text):
        parts.append(html_text_segment_with_links(text[last_index:match.start()]))
        parts.append(render_inline_code_link(match.group(1)))
        last_index = match.end()
    parts.append(html_text_segment_with_links(text[last_index:]))
    return "".join(parts) or "&nbsp;"


def html_text_segment_with_links(text, already_escaped=False):
    parts = []
    last_index = 0
    for match in URL_RE.finditer(text):
        raw_url = match.group(0)
        url = raw_url.rstrip(TRAILING_URL_PUNCTUATION)
        if not url:
            continue
        trailing = raw_url[len(url):]
        parts.append(escape_html_text(text[last_index:match.start()], already_escaped=already_escaped))
        safe_url = escape(url, quote=True)
        parts.append(f'<a href="{safe_url}">{escape_html_text(url, already_escaped=already_escaped)}</a>')
        parts.append(escape_html_text(trailing, already_escaped=already_escaped))
        last_index = match.end()
    parts.append(escape_html_text(text[last_index:], already_escaped=already_escaped))
    return "".join(parts)


def escape_html_text(text, already_escaped=False):
    if not already_escaped:
        text = escape(text, quote=False)
    return text.replace("\n", "<br>")


def linkify_markdown_urls(text):
    fence_pattern = re.compile(r"(```[\s\S]*?```)")
    inline_code_pattern = re.compile(r"(`[^`\n]+`)")
    parts = fence_pattern.split(text)
    processed_parts = []
    for part in parts:
        if part.startswith("```") and part.endswith("```"):
            processed_parts.append(part)
            continue

        inline_parts = inline_code_pattern.split(part)
        for index, inline_part in enumerate(inline_parts):
            if inline_part.startswith("`") and inline_part.endswith("`"):
                continue
            inline_parts[index] = linkify_markdown_segment(inline_part)
        processed_parts.append("".join(inline_parts))
    return "".join(processed_parts)


def linkify_markdown_segment(text):
    parts = []
    last_index = 0
    for match in URL_RE.finditer(text):
        raw_url = match.group(0)
        url = raw_url.rstrip(TRAILING_URL_PUNCTUATION)
        if not url or is_existing_markdown_url(text, match.start()):
            continue
        trailing = raw_url[len(url):]
        parts.append(text[last_index:match.start()])
        parts.append(f"[{url}]({url})")
        parts.append(trailing)
        last_index = match.end()
    parts.append(text[last_index:])
    return "".join(parts)


def is_existing_markdown_url(text, start_index):
    if start_index > 0 and text[start_index - 1] == "<":
        return True
    if start_index > 0 and text[start_index - 1] == "[":
        return True
    if start_index > 1 and text[start_index - 1] == "(" and text[start_index - 2] == "]":
        return True
    return False

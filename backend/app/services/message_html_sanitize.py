"""消息正文 HTML 轻量消毒（发布草稿用）。

禁止脚本/事件处理器；保留常见排版标签。纯文本路径只做空白规整。
"""
from __future__ import annotations

import re

_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)([^>]*)>", re.I)
_EVENT_RE = re.compile(r"\son\w+\s*=", re.I)
_JS_HREF_RE = re.compile(r"javascript:", re.I)
_ALLOWED = {
    "p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li",
    "span", "div", "h1", "h2", "h3", "h4", "a", "blockquote",
}


def strip_to_plain(text: str) -> str:
    s = re.sub(r"<[^>]+>", " ", text or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sanitize_message_html(html: str | None) -> str | None:
    if not html:
        return None
    raw = str(html)
    if _EVENT_RE.search(raw) or _JS_HREF_RE.search(raw):
        raw = _EVENT_RE.sub(" ", raw)
        raw = _JS_HREF_RE.sub("", raw)

    def _repl(m: re.Match) -> str:
        tag = (m.group(1) or "").lower()
        if tag not in _ALLOWED:
            return ""
        attrs = m.group(2) or ""
        if tag == "a":
            hm = re.search(r'href\s*=\s*("|\')([^"\']+)\1', attrs, re.I)
            href = hm.group(2) if hm else ""
            if href and not href.startswith(("http://", "https://", "/")):
                href = ""
            return f'<a href="{href}">' if not m.group(0).startswith("</") else "</a>"
        if m.group(0).startswith("</"):
            return f"</{tag}>"
        if tag == "br":
            return "<br/>"
        return f"<{tag}>"

    cleaned = _TAG_RE.sub(_repl, raw)
    return cleaned.strip() or None

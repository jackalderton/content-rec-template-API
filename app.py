import re
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Dict

import requests
from bs4 import (
    BeautifulSoup, Tag, NavigableString, Comment,
    Doctype, ProcessingInstruction
)

# =========================================================
# CONFIG / CONSTANTS
# =========================================================

ALWAYS_STRIP = {"script", "style", "noscript", "template"}

INLINE_TAGS = {
    "a","span","strong","em","b","i","u","s","small","sup","sub","mark",
    "abbr","time","code","var","kbd"
}

DEFAULT_EXCLUDE = [
    "header", "footer", "nav",
    ".cookie", ".newsletter",
    "[class*='breadcrumb']",
    "[class*='wishlist']",
    "[class*='simplesearch']",
    "[id*='gallery']",
    "[class*='usp']",
    "[class*='feefo']",
    "[class*='associated-blogs']",
    "[class*='popular']",
    ".sr-main.js-searchpage-content.visible",
    "[class~='sr-main'][class~='js-searchpage-content'][class~='visible']",
    "[class*='js-searchpage-content']",
    "[class*='searchpage-content']",
    ".lmd-map-modal-create.js-lmd-map-modal-map",
]

DATE_TZ = "Europe/London"
DATE_FMT = "%d/%m/%Y"

NOISE_SUBSTRINGS = (
    "google tag manager",
    "loading results",
    "load more",
    "updating results",
    "something went wrong",
    "filters",
    "apply filters",
    "clear",
    "sort by",
    "to collect end-user usage analytics",
    "place this code immediately before the closing",
)

# =========================================================
# TYPES
# =========================================================

@dataclass
class ExtractOptions:
    exclude_selectors: list[str]
    annotate_links: bool = False
    remove_before_h1: bool = False
    include_img_src: bool = False

Meta = Dict[str, str]

# =========================================================
# UTILITIES
# =========================================================

def uk_today_str() -> str:
    return datetime.now(ZoneInfo(DATE_TZ)).strftime(DATE_FMT)

def clean_slug_to_name(slug: str) -> str:
    return slug.replace("-", " ").strip().title()

def fallback_page_name_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    try:
        i = parts.index("destinations")
        if len(parts) > i + 2:
            return clean_slug_to_name(parts[i + 2])
    except ValueError:
        pass
    return clean_slug_to_name(parts[-1] if parts else (urlparse(url).hostname or "Page"))

def fetch_html(url: str) -> tuple[str, bytes]:
    resp = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ContentRecTool/1.0)"}
    )
    resp.raise_for_status()
    return resp.url, resp.content

def normalise_keep_newlines(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    return s

def is_noise(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    return any(sub in t for sub in NOISE_SUBSTRINGS)

def safe_filename(name: str, maxlen: int = 120) -> str:
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r'[\\/*?:"<>|]+', "", name)
    name = name.replace(",", "")
    return (name[:maxlen]).rstrip(". ")

def annotate_anchor_text(a: Tag, annotate_links: bool) -> str:
    text = a.get_text(" ", strip=True)
    href = a.get("href", "")
    return f"{text} (→ {href})" if (annotate_links and href) else text

def extract_text_preserve_breaks(node: Tag | NavigableString, annotate_links: bool) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    parts = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "br":
                parts.append("\n")
            elif child.name == "a":
                parts.append(annotate_anchor_text(child, annotate_links))
            else:
                parts.append(extract_text_preserve_breaks(child, annotate_links))
    return "".join(parts)

# =========================================================
# MAIN EXTRACTION
# =========================================================

def extract_signposted_lines_from_body(body: Tag, annotate_links: bool, include_img_src: bool = False) -> list[str]:
    """
    Extract structured content lines from a <body>.
    Emits headings, paragraphs, lists, and <img> with alt/src.
    """
    lines: list[str] = []

    def emit_lines(tag_name: str, text: str):
        text = normalise_keep_newlines(text)
        segments = text.split("\n")
        for seg in segments:
            seg_stripped = seg.strip()
            if seg_stripped:
                if tag_name == "p" and is_noise(seg_stripped):
                    continue
                lines.append(f"<{tag_name}> {seg_stripped}")
            else:
                if tag_name == "p":
                    lines.append("<p>")

    def emit_img(img_tag: Tag):
        if not isinstance(img_tag, Tag) or img_tag.name != "img":
            return
        alt = (img_tag.get("alt") or "").strip().replace('"', '\\"')
        if include_img_src:
            src = (img_tag.get("src") or "").strip().replace('"', '\\"')
            if src:
                lines.append(f'<img alt="{alt}" src="{src}">')
                return
        lines.append(f'<img alt="{alt}">')

    def handle(tag: Tag):
        name = tag.name
        if name in ALWAYS_STRIP:
            return
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            txt = extract_text_preserve_breaks(tag, annotate_links)
            if txt.strip():
                emit_lines(name, txt)
            return
        if name == "p":
            txt = tag.get_text(" ", strip=True)
            if txt.strip():
                emit_lines("p", txt)
            for img in tag.find_all("img"):
                emit_img(img)
            return
        if name in {"ul", "ol"}:
            for li in tag.find_all("li", recursive=False):
                txt = extract_text_preserve_breaks(li, annotate_links)
                if txt.strip():
                    emit_lines("p", txt)
                for img in li.find_all("img"):
                    emit_img(img)
                for sub in li.find_all(["ul", "ol"], recursive=False):
                    for sub_li in sub.find_all("li", recursive=False):
                        sub_txt = extract_text_preserve_breaks(sub_li, annotate_links)
                        if sub_txt.strip():
                            emit_lines("p", sub_txt)
                        for img in sub_li.find_all("img"):
                            emit_img(img)
            return
        buf = []
        def flush_buf():
            if not buf:
                return
            joined = normalise_keep_newlines("".join(buf))
            if joined.strip() and not is_noise(joined):
                emit_lines("p", joined)
            buf.clear()
        for child in tag.children:
            if isinstance(child, (Comment, Doctype, ProcessingInstruction)):
                continue
            if isinstance(child, NavigableString):
                buf.append(str(child))
            elif isinstance(child, Tag):
                if child.name == "br":
                    buf.append("\n")
                elif child.name == "img":
                    flush_buf()
                    emit_img(child)
                elif child.name in INLINE_TAGS:
                    buf.append(extract_text_preserve_breaks(child, annotate_links))
                else:
                    flush_buf()
                    handle(child)
        flush_buf()

    for child in body.children:
        if isinstance(child, (Comment, Doctype, ProcessingInstruction)):
            continue
        if isinstance(child, NavigableString):
            raw = normalise_keep_newlines(str(child))
            if raw.strip() and not is_noise(raw):
                emit_lines("p", raw)
        elif isinstance(child, Tag):
            if child.name == "img":
                emit_img(child)
            else:
                handle(child)

    deduped, prev = [], None
    for ln in lines:
        if ln != prev:
            deduped.append(ln)
        prev = ln
    return deduped

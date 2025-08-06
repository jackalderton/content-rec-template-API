import io
import re
import csv
import zipfile
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import streamlit as st
import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from docx import Document
from docx.text.paragraph import Paragraph
from docx.oxml import OxmlElement

# -------------------------
# CONFIG / CONSTANTS
# -------------------------
ALWAYS_STRIP = {"script", "style", "noscript", "template"}
DEFAULT_EXCLUDE = [
    "header", "footer", "nav",
    ".cookie", ".newsletter",
    "[class='breadcrumb']",
    "[class='wishlist']",
    "[class='simplesearch']",
    "[id='gallery']",
    "[class='usp']",
    "[class='feefo']",
    "[class='associated-blogs']",
    "[class='popular']",
    "[class*='menu']",
    "[id*='menu']",
    "[role='navigation']",
]
DATE_TZ = "Europe/London"
DATE_FMT = "%d/%m/%Y"

# -------------------------
# UTILITIES
# -------------------------
def uk_today_str():
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

def fetch_html(url: str) -> tuple[str, str]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.url, resp.text

def normalise_keep_newlines(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"[ \t]\n[ \t]", "\n", s)
    return s

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

def extract_signposted_lines_from_body(body: Tag, annotate_links: bool) -> list[str]:
    lines: list[str] = []
    def emit_lines(tag_name: str, text: str):
        text = normalise_keep_newlines(text)
        segments = text.split("\n")
        for seg in segments:
            seg_stripped = seg.strip()
            if seg_stripped:
                lines.append(f"<{tag_name}> {seg_stripped}")
            else:
                if tag_name == "p":
                    lines.append("<p>")
    def handle(tag: Tag):
        name = tag.name
        if name in ALWAYS_STRIP:
            return
        if name in {"h1","h2","h3","h4","h5","h6"}:
            txt = extract_text_preserve_breaks(tag, annotate_links)
            if txt.strip():
                emit_lines(name, txt)
        elif name == "p":
            txt = extract_text_preserve_breaks(tag, annotate_links)
            if txt.strip() or "\n" in txt:
                emit_lines("p", txt)
        elif name in {"ul", "ol"}:
            for li in tag.find_all("li", recursive=False):
                txt = extract_text_preserve_breaks(li, annotate_links)
                if txt.strip():
                    emit_lines("p", txt)
                for sub in li.find_all(["ul", "ol"], recursive=False):
                    for sub_li in sub.find_all("li", recursive=False):
                        sub_txt = extract_text_preserve_breaks(sub_li, annotate_links)
                        if sub_txt.strip():
                            emit_lines("p", sub_txt)
        for child in tag.children:
            if isinstance(child, Tag):
                handle(child)
    for child in body.children:
        if isinstance(child, Tag):
            handle(child)
    deduped, prev = [], None
    for ln in lines:
        if ln != prev:
            deduped.append(ln)
        prev = ln
    return deduped

def first_h1_text(soup: BeautifulSoup) -> str | None:
    if not soup.body:
        return None
    h1 = soup.body.find("h1")
    if not h1:
        return None
    txt = extract_text_preserve_breaks(h1, annotate_links=False)
    txt = normalise_keep_newlines(txt)
    return txt.strip() or None

def remove_before_first_h1(soup: BeautifulSoup):
    if not soup.body:
        return
    h1 = soup.body.find("h1")
    if not h1:
        return
    # Remove ALL prior elements in document order
    found = False
    for el in list(soup.body.descendants):
        if isinstance(el, Tag) and el.name == "h1":
            found = True
            break
        if isinstance(el, Tag):
            el.decompose()
    if not found:
        return

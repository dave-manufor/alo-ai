"""What the ingestion job reads from a book file (PRD 9.1): the story's text, its sentences and
words, the page count and the share of pages with a picture. PDF and EPUB, the formats African
Storybook, Book Dash and StoryWeaver publish.

Front and back matter (the licence, the credits, web addresses) is left out of the text, so the
level estimate and the word count are of the story itself. The licence and the attribution are
not read from here: a person checks them against the publisher's page (the manifest).
"""

import io
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser

from pypdf import PdfReader

# A line that belongs to the front or back matter, not to the story.
_MATTER = re.compile(
    r"creative commons|licen[cs]e|\bcc[ -]?by\b|https?://|www\.|©|copyright|isbn|"
    r"storybook|storyweaver|book ?dash|pratham|translated|illustrat|written by|this story|"
    r"you are free|attribution|all rights",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")


@dataclass(frozen=True)
class Extracted:
    sentences: tuple[str, ...]
    word_count: int
    page_count: int
    illustration_ratio: float


def read_book(name: str, data: bytes) -> Extracted:
    """The story in a PDF or EPUB file. ValueError for another format or a book with no text."""
    lower = name.lower()
    if lower.endswith(".pdf"):
        pages = _pdf_pages(data)
    elif lower.endswith(".epub"):
        pages = _epub_pages(data)
    else:
        raise ValueError(f"{name}: only PDF and EPUB books can be read")
    if not pages:
        raise ValueError(f"{name}: no pages")
    lines = [line for text, _ in pages for line in _story_lines(text)]
    sentences = tuple(
        part.strip() for line in lines for part in _SENTENCE_END.split(line) if _WORD.search(part)
    )
    if not sentences:
        raise ValueError(f"{name}: no story text could be read")
    return Extracted(
        sentences=sentences,
        word_count=sum(len(_WORD.findall(sentence)) for sentence in sentences),
        page_count=len(pages),
        illustration_ratio=round(sum(pictured for _, pictured in pages) / len(pages), 3),
    )


def _story_lines(text: str) -> list[str]:
    lines = (" ".join(line.split()) for line in text.splitlines())
    return [line for line in lines if line and not _MATTER.search(line)]


def _pdf_pages(data: bytes) -> list[tuple[str, bool]]:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pictured = len(page.images) > 0
        except Exception:  # noqa: BLE001 - an image pypdf cannot decode still counts as a picture
            pictured = True
        pages.append((page.extract_text() or "", pictured))
    return pages


def _epub_pages(data: bytes) -> list[tuple[str, bool]]:
    """The spine's documents in reading order (EPUB 2 and 3): each one's text and whether it
    has an image."""
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        container = ET.fromstring(book.read("META-INF/container.xml"))
        opf_path = next(
            element.attrib["full-path"]
            for element in container.iter()
            if element.tag.endswith("rootfile")
        )
        opf = ET.fromstring(book.read(opf_path))
        base = posixpath.dirname(opf_path)
        hrefs = {
            item.attrib["id"]: item.attrib["href"]
            for item in opf.iter()
            if item.tag.endswith("item") and "id" in item.attrib
        }
        pages = []
        for itemref in (e for e in opf.iter() if e.tag.endswith("itemref")):
            href = hrefs.get(itemref.attrib.get("idref", ""))
            if href is None:
                continue
            reader = _Text()
            reader.feed(book.read(posixpath.normpath(posixpath.join(base, href))).decode("utf-8"))
            pages.append(("\n".join(reader.lines), reader.images > 0))
    return pages


class _Text(HTMLParser):
    """A document's text, one line per block, and how many images it has."""

    BLOCKS = {"p", "div", "br", "h1", "h2", "h3", "h4", "li", "tr", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.images = 0
        self._current: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("img", "image", "svg"):
            self.images += 1
        if tag in ("script", "style", "head"):
            self._skip += 1
        if tag in self.BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head") and self._skip:
            self._skip -= 1
        if tag in self.BLOCKS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._current.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        line = " ".join("".join(self._current).split())
        if line:
            self.lines.append(line)
        self._current = []

    def feed(self, data: str) -> None:
        super().feed(data)
        self.close()

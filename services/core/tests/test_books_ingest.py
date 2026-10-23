"""The book ingestion job (PRD 9.1): reading PDF and EPUB books, the publisher-level map, the
manifest check, and ingesting into a memory store, with tiny fictional books made here (no real
book, no network, no model)."""

import io
import json
import zipfile
from datetime import UTC, datetime

import aloai_env
import pytest
from aloai_blobs import MemoryBlobs
from aloai_contracts import validator
from aloai_store import MemoryStore
from services.core.books import ingest as ingest_module
from services.core.books.embedding import azure_embedding_model
from services.core.books.extract import read_book
from services.core.books.ingest import Ingest, check_entry, load_manifest, main
from services.core.books.levels import publisher_arl
from services.core.generator import data

BOOK = validator("book.schema.json")
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
STORY = [
    "Ada has a red ball.",
    "She kicks the ball to Tunde.",
    "Tunde runs and kicks it back.",
    "They play until the sun goes down.",
]


def pdf(pages: list[tuple[list[str], bool]]) -> bytes:
    """A small valid PDF: each page's lines in Helvetica, and a 1x1 image where asked."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    image = add(
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream"
    )
    pages_id = len(objects) + 1 + 2 * len(pages)
    page_ids = []
    for lines, pictured in pages:
        ops = ["BT /F1 12 Tf 20 280 Td 14 TL"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({escaped}) Tj T*")
        ops.append("ET")
        if pictured:
            ops.append("q 10 0 0 10 200 20 cm /Im1 Do Q")
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        resources = (
            b"<< /Font << /F1 %d 0 R >> /XObject << /Im1 %d 0 R >> >>" % (font, image)
            if pictured
            else b"<< /Font << /F1 %d 0 R >> >>" % font
        )
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 300 300] /Contents %d 0 R "
                b"/Resources %s >>" % (pages_id, content, resources)
            )
        )
    kids = b" ".join(b"%d 0 R" % page for page in page_ids)
    assert add(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))) == pages_id
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, catalog, start)
    )
    return out.getvalue()


def epub(pages: list[tuple[list[str], bool]]) -> bytes:
    """A small EPUB 3: one XHTML document per page, in spine order."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        items, spine = [], []
        for number, (lines, pictured) in enumerate(pages, start=1):
            body = "".join(f"<p>{line}</p>" for line in lines)
            if pictured:
                body += '<img src="p.png" alt=""/>'
            book.writestr(
                f"OEBPS/text/p{number}.xhtml",
                "<html xmlns='http://www.w3.org/1999/xhtml'><head><title>t</title>"
                f"<style>p {{ color: red }}</style></head><body>{body}</body></html>",
            )
            items.append(
                f'<item id="p{number}" href="text/p{number}.xhtml" media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="p{number}"/>')
        spine.append('<itemref idref="missing"/>')
        book.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            f"<manifest>{''.join(items)}</manifest><spine>{''.join(spine)}</spine></package>",
        )
    return out.getvalue()


PAGES = [
    (["The Red Ball"], True),
    (STORY[:2], True),
    (STORY[2:], False),
    (
        [
            "This story is licensed under a Creative Commons Attribution 4.0 licence.",
            "www.africanstorybook.org",
        ],
        False,
    ),
]


# ---- reading the files


@pytest.mark.parametrize("name, make", [("ball.pdf", pdf), ("ball.epub", epub)])
def test_a_book_is_read_without_its_licence_page(name, make):
    found = read_book(name, make(PAGES))
    assert found.page_count == 4
    assert found.illustration_ratio == 0.5
    text = " ".join(found.sentences)
    for sentence in STORY:
        assert sentence in text
    assert "Creative Commons" not in text and "africanstorybook" not in text
    assert found.word_count == 3 + sum(len(s.split()) for s in STORY)  # the title, then the story


def test_only_pdf_and_epub_books_are_read():
    with pytest.raises(ValueError, match="only PDF and EPUB"):
        read_book("ball.docx", b"x")


@pytest.mark.parametrize("name, make", [("blank.pdf", pdf), ("blank.epub", epub)])
def test_a_book_with_no_story_text_is_refused(name, make):
    with pytest.raises(ValueError, match="no story text"):
        read_book(name, make([(["www.example.org"], True)]))


def test_an_epub_with_an_empty_spine_has_no_pages():
    with pytest.raises(ValueError, match="no pages"):
        read_book("empty.epub", epub([]))


# ---- the level map and the manifest


@pytest.mark.parametrize(
    "publisher, level, arl",
    [
        ("African Storybook", "Level 1", 1),
        ("African Storybook", "Level 3: First paragraphs", 4),
        ("African Storybook", "level 5", 8),
        ("StoryWeaver", "Level 2", 4),
        ("StoryWeaver", "Level 9", None),
        ("Book Dash", "Ages 3-6", None),
        ("African Storybook", "First words", None),
    ],
)
def test_a_publisher_level_maps_to_an_arl(publisher, level, arl):
    assert publisher_arl(publisher, level) == arl


def entry(**changes) -> dict:
    base = {
        "book_id": "book_red_ball",
        "file": "ball.pdf",
        "title": "The Red Ball",
        "author": "A. Writer",
        "illustrator": "B. Artist",
        "publisher": "African Storybook",
        "source_url": "https://www.africanstorybook.org/",
        "licence": "CC BY 4.0",
        "attribution": "The Red Ball, by A. Writer, illustrated by B. Artist, African Storybook, CC BY 4.0",
        "language": "en",
        "publisher_level": "Level 2",
        "topic_tags": ["football", "family"],
        "west_african_setting": True,
        "description": "Ada and Tunde play football with a red ball until sunset.",
    }
    merged = base | changes
    return {key: value for key, value in merged.items() if value is not None}


def test_a_complete_entry_gives_its_mapped_arl():
    assert check_entry(entry()) == 2


@pytest.mark.parametrize(
    "changes, problem",
    [
        ({"licence": None}, "missing licence"),
        ({"attribution": ""}, "missing attribution"),
        ({"topic_tags": []}, "missing topic_tags"),
        ({"rating": 5}, "unknown fields rating"),
        ({"book_id": "Red Ball"}, "book_id"),
        ({"arl": 3}, "arl_reason"),
        ({"publisher": "Book Dash", "publisher_level": "Ages 3-6"}, "give arl and arl_reason"),
    ],
)
def test_an_incomplete_or_unmapped_entry_is_refused(changes, problem):
    with pytest.raises(ValueError, match=problem):
        check_entry(entry(**changes))


def test_an_arl_given_by_hand_needs_a_reason():
    hand = entry(
        publisher="Book Dash",
        publisher_level="Ages 3-6",
        arl=3,
        arl_reason="read-aloud picture book for ages 3 to 6",
    )
    assert check_entry(hand) == 3


def test_every_book_in_the_shipped_manifest_is_complete_and_has_its_arl():
    books = load_manifest()
    assert len(books) == len({book["book_id"] for book in books}) > 0
    for book in books:
        assert 1 <= check_entry(book) <= 12, book["book_id"]
        assert book["topic_tags"] and set(book["topic_tags"]) <= set(data.taxonomy().tags), book[
            "book_id"
        ]


def test_a_manifest_must_hold_a_list(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"books": {"x": 1}}))
    with pytest.raises(ValueError, match="must be a list"):
        load_manifest(path)


# ---- ingesting


class Embedder:
    def __init__(self, size: int = 768) -> None:
        self.texts: list[str] = []
        self.size = size

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [0.25] * self.size


def job(tmp_path, embedder=None, store=None, blobs=None):
    (tmp_path / "ball.pdf").write_bytes(pdf(PAGES))
    return (
        Ingest(
            store=store if store is not None else MemoryStore(),
            blobs=blobs if blobs is not None else MemoryBlobs(),
            embedder=embedder if embedder is not None else Embedder(),
            model="gemini-embedding-001",
            cloud="azure",
            bucket="books",
            names=data.names(),
            now=lambda: NOW,
        ),
        tmp_path,
    )


def test_a_book_is_ingested_as_a_valid_catalogue_document(tmp_path):
    ingest, files = job(tmp_path)
    report = ingest.run([entry()], files)
    assert report.added == ["book_red_ball"] and not report.failed
    book = ingest.store.get("books/book_red_ball")
    BOOK.validate(book)
    assert (book["arl"], book["held_for_review"], book["embedding_model"]) == (
        2,
        False,
        "gemini-embedding-001",
    )
    assert book["attribution"].startswith("The Red Ball, by A. Writer")
    assert book["raw_uri"] == f"az://books/raw/{book['file_hash']}.pdf"
    assert ingest.blobs.exists(book["raw_uri"])
    assert book["ingested_at"] == "2026-10-23T12:00:00Z"
    assert ingest.embedder.texts == [
        "Ada and Tunde play football with a red ball until sunset.\nfamily, football"
    ]


def test_running_it_again_changes_nothing(tmp_path):
    ingest, files = job(tmp_path)
    ingest.run([entry()], files)
    first = ingest.store.get("books/book_red_ball")
    report = ingest.run([entry()], files)
    assert report.already == ["book_red_ball"] and report.added == []
    assert ingest.store.get("books/book_red_ball") == first
    assert len(ingest.embedder.texts) == 1


def test_a_changed_attribution_updates_the_book_but_keeps_its_vector(tmp_path):
    ingest, files = job(tmp_path)
    ingest.run([entry()], files)
    report = ingest.run([entry(attribution="Fixed attribution, CC BY 4.0")], files)
    assert report.updated == ["book_red_ball"]
    assert ingest.store.get("books/book_red_ball")["attribution"] == "Fixed attribution, CC BY 4.0"
    assert len(ingest.embedder.texts) == 1


def test_a_changed_description_is_embedded_again(tmp_path):
    ingest, files = job(tmp_path)
    ingest.run([entry()], files)
    ingest.run([entry(description="Two friends and a ball.")], files)
    assert len(ingest.embedder.texts) == 2


def test_a_book_far_from_its_publisher_level_is_held_for_a_person(tmp_path):
    ingest, files = job(tmp_path)
    report = ingest.run(
        [entry(publisher="Book Dash", publisher_level="Ages 10-12", arl=12, arl_reason="test")],
        files,
    )
    assert "book_red_ball" in report.held
    assert ingest.store.get("books/book_red_ball")["held_for_review"] is True


def test_one_bad_book_does_not_stop_the_others(tmp_path):
    ingest, files = job(tmp_path)
    report = ingest.run([entry(book_id="book_missing", file="nope.pdf"), entry()], files)
    assert report.added == ["book_red_ball"]
    assert "book_missing" in report.failed


def test_a_vector_of_the_wrong_size_is_refused(tmp_path):
    ingest, files = job(tmp_path, embedder=Embedder(size=512))
    report = ingest.run([entry()], files)
    assert "512" in report.failed["book_red_ball"]
    assert ingest.store.get("books/book_red_ball") is None


def test_only_the_books_asked_for_are_ingested(tmp_path):
    ingest, files = job(tmp_path)
    report = ingest.run([entry(), entry(book_id="book_other")], files, only=["book_other"])
    assert report.added == ["book_other"]


def test_a_check_run_touches_no_store_and_calls_no_model(tmp_path):
    ingest, files = job(tmp_path)
    ingest.store, ingest.blobs = None, None
    report = ingest.run([entry()], files, check=True)
    assert report.added == ["book_red_ball"] and ingest.embedder.texts == []


# ---- the command


def write_manifest(tmp_path, entries) -> str:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"books": entries}))
    return str(path)


def test_the_check_command_reports_each_book(tmp_path, capsys):
    (tmp_path / "ball.pdf").write_bytes(pdf(PAGES))
    manifest = write_manifest(
        tmp_path, [entry(), entry(book_id="book_far", arl=12, arl_reason="test")]
    )
    assert main(["--files", str(tmp_path), "--manifest", manifest, "--check"]) == 0
    out = capsys.readouterr().out
    assert "would add 2" in out and "HELD book_far" in out


def test_the_check_command_fails_on_a_bad_book(tmp_path, capsys):
    manifest = write_manifest(tmp_path, [entry(file="nope.pdf")])
    assert main(["--files", str(tmp_path), "--manifest", manifest, "--check"]) == 1
    assert "FAILED book_red_ball" in capsys.readouterr().out


def test_the_command_refuses_a_missing_manifest_or_the_wrong_cloud(tmp_path, capsys):
    assert (
        main(["--files", str(tmp_path), "--manifest", str(tmp_path / "none.json"), "--check"]) == 1
    )
    manifest = write_manifest(tmp_path, [])
    assert main(["--files", str(tmp_path), "--manifest", manifest], env={}) == 1
    assert "CLOUD=azure and AI_MODE=live" in capsys.readouterr().err


def test_the_azure_embedding_model_is_the_providers_or_openais():
    gemini = aloai_env.load(
        {
            "CLOUD": "azure",
            "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
            "LLM_API_KEY": "fictional-key",
            "AZURE_OPENAI_DEPLOYMENTS": json.dumps({"embedding": "gemini-embedding-001"}),
        }
    )
    assert azure_embedding_model(gemini) == "gemini-embedding-001"
    openai = aloai_env.load(
        {"CLOUD": "azure", "AZURE_OPENAI_DEPLOYMENTS": json.dumps({"embedding": "x"})}
    )
    assert azure_embedding_model(openai) == "text-embedding-3-small"


def test_the_job_writes_book_schema_version_3():
    assert ingest_module.SCHEMA_VERSION == 3


def test_a_page_whose_images_cannot_be_read_still_counts_as_pictured(monkeypatch):
    from services.core.books import extract

    class Page:
        @property
        def images(self):
            raise ValueError("an image pypdf cannot decode")

        def extract_text(self):
            return "Ada has a red ball."

    class Reader:
        def __init__(self, _stream):
            self.pages = [Page()]

    monkeypatch.setattr(extract, "PdfReader", Reader)
    found = read_book("odd.pdf", b"%PDF")
    assert (found.illustration_ratio, found.sentences) == (1.0, ("Ada has a red ball.",))


def test_a_gutenberg_book_keeps_only_what_lies_between_its_markers():
    pages = [
        (
            [
                "The Project Gutenberg eBook of The Red Ball",
                "This eBook is for the use of anyone anywhere.",
            ],
            False,
        ),
        (["*** START OF THE PROJECT GUTENBERG EBOOK THE RED BALL ***", *STORY], True),
        (
            [
                "*** END OF THE PROJECT GUTENBERG EBOOK THE RED BALL ***",
                "Updated editions will replace the previous one.",
            ],
            False,
        ),
    ]
    found = read_book("ball.epub", epub(pages))
    assert found.sentences == tuple(STORY)


def test_an_epub_href_with_a_fragment_or_an_escape_is_read_once():
    """An OPF href is a URL: it can carry a #fragment and %-escapes, which the ZIP member name
    does not, and two spine entries can point into one document."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as book:
        book.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles></container>',
        )
        book.writestr(
            "OEBPS/text/Chapter One.xhtml",
            f"<html><body><p>{STORY[0]}</p><p>{STORY[1]}</p></body></html>",
        )
        book.writestr("OEBPS/text/two.xhtml", f"<html><body><p>{STORY[2]}</p></body></html>")
        book.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0"><manifest>'
            '<item id="a" href="text/Chapter%20One.xhtml#start" media-type="application/xhtml+xml"/>'
            '<item id="b" href="text/Chapter%20One.xhtml#middle" media-type="application/xhtml+xml"/>'
            '<item id="c" href="text/two.xhtml#top" media-type="application/xhtml+xml"/>'
            '</manifest><spine><itemref idref="a"/><itemref idref="b"/><itemref idref="c"/></spine></package>',
        )
    found = read_book("fragments.epub", out.getvalue())
    assert found.sentences == tuple(STORY[:3])
    assert found.page_count == 2

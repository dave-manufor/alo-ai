"""Embedding the catalogue again on another cloud's model (services/core/books). A fake
embedder and a memory store: nothing here reaches Azure."""

import copy
from types import SimpleNamespace

import pytest
from aloai_store import MemoryStore
from services.core.books import embedding, reembed
from services.core.books.embedding import book_text, reembed_books
from services.core.grader.azure import EMBEDDING_MODEL
from services.core.tests.support import contract

BOOK = contract("book.sample.json")
NEW = [0.25] * 768


class Embedder:
    def __init__(self, vector=NEW, fail_on=()):
        self.vector, self.fail_on, self.asked = vector, fail_on, []

    def embed(self, text):
        self.asked.append(text)
        if any(marker in text for marker in self.fail_on):
            raise ConnectionError("Azure OpenAI is unavailable")
        return list(self.vector)


def book(book_id="book_a", model="text-embedding-005", **changes):
    return copy.deepcopy(BOOK) | {"book_id": book_id, "embedding_model": model} | changes


def catalogue(*books) -> MemoryStore:
    return MemoryStore({f"books/{b['book_id']}": b for b in books})


# ---- what is embedded


def test_a_book_is_embedded_from_its_description_and_its_tags_as_interests_are_written():
    text = book_text(book(description="A boy and his goats.", topic_tags=["animals", "farm"]))
    assert text == "A boy and his goats.\nanimals, farm"


def test_the_tags_are_written_in_one_order_so_the_same_book_has_the_same_text():
    one = book_text(book(topic_tags=["farm", "animals"]))
    other = book_text(book(topic_tags=["animals", "farm"]))
    assert one == other


def test_the_models_are_the_ones_the_schema_allows():
    assert set(embedding.KNOWN_MODELS) == {"text-embedding-005", "text-embedding-3-small"}
    assert EMBEDDING_MODEL in embedding.KNOWN_MODELS


# ---- moving the catalogue


def test_a_book_on_another_model_is_embedded_again_and_everything_else_is_kept():
    store = catalogue(book())
    before = store.get("books/book_a")
    report = reembed_books(store, Embedder(), EMBEDDING_MODEL)
    after = store.get("books/book_a")
    assert report.done == ["book_a"] and report.failed == {} and report.already == 0
    assert (after["embedding"], after["embedding_model"]) == (NEW, EMBEDDING_MODEL)
    assert {k: v for k, v in after.items() if k not in ("embedding", "embedding_model")} == {
        k: v for k, v in before.items() if k not in ("embedding", "embedding_model")
    }


def test_the_text_sent_is_the_books_own():
    embedder = Embedder()
    store = catalogue(book(description="Rain on the farm.", topic_tags=["farm"]))
    reembed_books(store, embedder, EMBEDDING_MODEL)
    assert embedder.asked == ["Rain on the farm.\nfarm"]


def test_a_book_already_on_the_model_is_counted_and_left_alone():
    store = catalogue(book("book_a", EMBEDDING_MODEL, embedding=[0.5] * 768), book("book_b"))
    embedder = Embedder()
    report = reembed_books(store, embedder, EMBEDDING_MODEL)
    assert (report.done, report.already) == (["book_b"], 1)
    assert len(embedder.asked) == 1
    assert store.get("books/book_a")["embedding"] == [0.5] * 768


def test_running_it_again_has_nothing_left_to_do():
    store = catalogue(book("book_a"), book("book_b"))
    reembed_books(store, Embedder(), EMBEDDING_MODEL)
    embedder = Embedder()
    report = reembed_books(store, embedder, EMBEDDING_MODEL)
    assert (report.done, report.already, embedder.asked) == ([], 2, [])


def test_a_dry_run_says_what_it_would_do_and_changes_nothing():
    store = catalogue(book())
    report = reembed_books(store, Embedder(), EMBEDDING_MODEL, dry_run=True)
    assert report.done == ["book_a"]
    assert store.get("books/book_a")["embedding_model"] == "text-embedding-005"


def test_only_the_books_asked_for_are_embedded():
    store = catalogue(book("book_a"), book("book_b"))
    report = reembed_books(store, Embedder(), EMBEDDING_MODEL, only=["book_b"])
    assert report.done == ["book_b"]
    assert store.get("books/book_a")["embedding_model"] == "text-embedding-005"


# ---- a book that cannot be moved


def test_a_vector_of_the_wrong_size_is_reported_and_the_book_is_left_as_it_was():
    store = catalogue(book())
    before = store.get("books/book_a")
    report = reembed_books(store, Embedder([0.1] * 1536), EMBEDDING_MODEL)
    assert "1536 numbers, not 768" in report.failed["book_a"]
    assert report.done == [] and store.get("books/book_a") == before


def test_a_vector_that_would_break_the_book_schema_is_not_written():
    store = catalogue(book())
    before = store.get("books/book_a")
    report = reembed_books(store, Embedder(["x"] * 768), EMBEDDING_MODEL)
    assert "book_a" in report.failed and store.get("books/book_a") == before


def test_one_book_that_fails_does_not_stop_the_others():
    store = catalogue(book("book_a", description="BAD"), book("book_b"))
    report = reembed_books(store, Embedder(fail_on=("BAD",)), EMBEDDING_MODEL)
    assert list(report.failed) == ["book_a"] and "unavailable" in report.failed["book_a"]
    assert report.done == ["book_b"]
    assert store.get("books/book_a")["embedding_model"] == "text-embedding-005"


def test_a_model_the_schema_does_not_allow_is_refused():
    with pytest.raises(ValueError, match="not an embedding model"):
        reembed_books(catalogue(book()), Embedder(), "text-embedding-004")


# ---- the command


@pytest.fixture
def azure(monkeypatch):
    store = catalogue(book("book_a"), book("book_b"))
    monkeypatch.setattr(reembed, "open_store", lambda settings: store)
    monkeypatch.setattr(reembed, "open_openai", lambda settings: SimpleNamespace())
    monkeypatch.setattr(reembed, "AzureEmbedder", lambda client, name: Embedder())
    return store


ENV = {
    "ALO_ENV": "local",
    "CLOUD": "azure",
    "AI_MODE": "live",
    "AZURE_OPENAI_ENDPOINT": "https://aloai.openai.azure.com",
    "AZURE_OPENAI_DEPLOYMENTS": '{"embedding": "aloai-embedding"}',
}


def test_the_command_embeds_the_catalogue_and_says_how_many(azure, capsys):
    assert reembed.main([], ENV) == 0
    assert "re-embedded 2 books; 0 already on text-embedding-3-small" in capsys.readouterr().out
    assert azure.get("books/book_a")["embedding_model"] == EMBEDDING_MODEL


def test_the_command_can_be_a_dry_run_for_some_books_only(azure, capsys):
    assert reembed.main(["--dry-run", "--book-id", "book_a"], ENV) == 0
    assert "would re-embed 1 books" in capsys.readouterr().out
    assert azure.get("books/book_a")["embedding_model"] == "text-embedding-005"


def test_the_command_exits_non_zero_when_a_book_could_not_be_moved(azure, monkeypatch, capsys):
    monkeypatch.setattr(reembed, "AzureEmbedder", lambda client, name: Embedder([0.1] * 3))
    assert reembed.main([], ENV) == 1
    assert "FAILED book_a" in capsys.readouterr().out


@pytest.mark.parametrize(
    "env",
    [
        {"ALO_ENV": "local", "AI_MODE": "live"},
        {"ALO_ENV": "local", "CLOUD": "azure", "AI_MODE": "fixtures"},
    ],
    ids=["not azure", "not live"],
)
def test_the_command_refuses_anything_but_a_live_azure_run(azure, env, capsys):
    assert reembed.main([], env) == 1
    assert "CLOUD=azure and AI_MODE=live" in capsys.readouterr().err


def test_the_command_needs_the_embedding_deployment(azure, capsys):
    assert reembed.main([], ENV | {"AZURE_OPENAI_DEPLOYMENTS": "{}"}) == 1
    assert "'embedding'" in capsys.readouterr().err

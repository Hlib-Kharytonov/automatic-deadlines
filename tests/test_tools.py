import json
from pathlib import Path

import pytest

from exam_agent.mail.fake import FakeMailbox
from exam_agent.tools import TOOL_DEFINITIONS, run_tool

FIXTURES = Path(__file__).parent / "fixtures" / "emails.json"


@pytest.fixture
def mailbox():
    return FakeMailbox(FIXTURES)


def ids(results):
    return [r["id"] for r in results]


def test_search_finds_word_ignoring_case_and_accents(mailbox):
    # e1, e2, e4 are exam emails; e5 is the "dossier de bourse" trap, which a
    # keyword search cannot tell apart. Telling them apart is Claude's job.
    assert sorted(ids(mailbox.search("EXAMEN"))) == ["e1", "e2", "e4", "e5"]


def test_search_or(mailbox):
    assert sorted(ids(mailbox.search("quizz OR report"))) == ["e3", "e6"]


def test_search_words_without_or_must_all_appear(mailbox):
    assert ids(mailbox.search("examen bourse")) == ["e5"]


def test_search_matches_whole_words_only(mailbox):
    # "CC" must not match "CC1" or "CC2"
    assert mailbox.search("CC") == []


def test_search_returns_newest_first_without_body(mailbox):
    results = mailbox.search("examen")
    assert [r["date"] for r in results] == sorted((r["date"] for r in results), reverse=True)
    assert "body" not in results[0]


def test_read_returns_full_body(mailbox):
    assert "de 16h30 à 18h30" in mailbox.read("e1")["body"]


def test_read_unknown_id_is_an_error(mailbox):
    with pytest.raises(ValueError, match="No email with id"):
        mailbox.read("nope")


def test_run_tool_returns_json_text(mailbox):
    result = json.loads(run_tool("read_email", {"email_id": "e3"}, mailbox))
    assert result["date"] == "2026-03-24"


def test_run_tool_unknown_tool(mailbox):
    with pytest.raises(ValueError, match="Unknown tool"):
        run_tool("delete_everything", {}, mailbox)


def test_every_definition_has_what_the_api_needs():
    for tool in TOOL_DEFINITIONS:
        assert {"name", "description", "input_schema"} <= tool.keys()

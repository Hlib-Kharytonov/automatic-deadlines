"""process_report: what code does with Claude's report_exams call. No API calls here."""

from datetime import date, datetime
from pathlib import Path

import pytest

from exam_agent.dates import PARIS
from exam_agent.mail.fake import FakeMailbox
from exam_agent.tools import FINAL_TOOL, TOOL_DEFINITIONS, process_report

FIXTURES = Path(__file__).parent / "fixtures" / "emails.json"


@pytest.fixture
def mailbox():
    return FakeMailbox(FIXTURES)


def exam(**overrides):
    """A report_exams entry with every field present, as strict mode guarantees."""
    entry = {
        "email_id": "e1",
        "course_code": "UL2IN009",
        "exam_name": "Introduction aux bases de données relationnelles",
        "date": {"day": 28, "month": 5, "year": None, "weekday": "thursday", "relative": None},
        "start": "16:30",
        "end": "18:30",
        "duration_minutes": None,
        "groups": [],
        "quote": "L'examen aura lieu le jeudi 28 mai de 16h30 à 18h30",
    }
    return entry | overrides


def relative(word, weekday=None):
    return {"day": None, "month": None, "year": None, "weekday": weekday, "relative": word}


def test_absolute_date_with_start_and_end(mailbox):
    [result] = process_report([exam()], mailbox)
    assert result["status"] == "scheduled"
    assert result["date"] == date(2026, 5, 28)
    assert result["start"] == datetime(2026, 5, 28, 16, 30, tzinfo=PARIS)
    assert result["end"] == datetime(2026, 5, 28, 18, 30, tzinfo=PARIS)


def test_ce_soir_uses_the_email_date_and_default_length(mailbox):
    # e4 is dated 2026-03-12: "ce soir à 18h15", no end given -> 2 hours
    [result] = process_report(
        [exam(email_id="e4", date=relative("today"), start="18:15", end=None)], mailbox
    )
    assert result["start"] == datetime(2026, 3, 12, 18, 15, tzinfo=PARIS)
    assert result["end"] == datetime(2026, 3, 12, 20, 15, tzinfo=PARIS)


def test_ce_jeudi_without_time_is_time_unknown(mailbox):
    # e3 is dated Tuesday 2026-03-24: "ce jeudi" -> 2026-03-26
    [result] = process_report(
        [exam(email_id="e3", date=relative("this", "thursday"), start=None, end=None, groups=["1", "3"])],
        mailbox,
    )
    assert result["status"] == "time_unknown"
    assert result["date"] == date(2026, 3, 26)
    assert result["start"] is None and result["end"] is None
    assert result["groups"] == ["1", "3"]


def test_duration_instead_of_end(mailbox):
    [result] = process_report([exam(end=None, duration_minutes=90)], mailbox)
    assert result["end"] == datetime(2026, 5, 28, 18, 0, tzinfo=PARIS)


def test_one_bad_exam_rejects_the_whole_report_and_names_every_problem(mailbox):
    wrong_weekday = exam(date={"day": 28, "month": 5, "year": None, "weekday": "friday", "relative": None})
    unknown_email = exam(email_id="e99", exam_name="Ghost")
    with pytest.raises(ValueError) as error:
        process_report([exam(), wrong_weekday, unknown_email], mailbox)
    message = str(error.value)
    assert message.startswith("Nothing was recorded")
    assert "Exam 2" in message and "friday" in message
    assert "Exam 3" in message and "e99" in message
    assert "Exam 1" not in message


def test_empty_report_is_valid(mailbox):
    assert process_report([], mailbox) == []


def test_report_tool_is_strict_and_every_exam_field_is_required():
    [tool] = [t for t in TOOL_DEFINITIONS if t["name"] == FINAL_TOOL]
    assert tool["strict"] is True
    exam_schema = tool["input_schema"]["properties"]["exams"]["items"]
    assert set(exam_schema["required"]) == set(exam_schema["properties"])

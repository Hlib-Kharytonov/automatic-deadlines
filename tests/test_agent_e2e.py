"""End to end: the real agent on the sample emails, compared with `expected`.

Calls the Claude API, so it costs a little and is skipped by default. Run it with:
    uv run pytest -m api
"""

from datetime import date
from pathlib import Path

import pytest

from exam_agent.groups import GroupMemory, normalize
from exam_agent.mail.fake import FakeMailbox

FIXTURES = Path(__file__).parent / "fixtures" / "emails.json"


def key(course_code, status, day, start, end, groups):
    """What must match. Exam names are free text, so they are not compared."""
    return (course_code, status, day, start, end, tuple(sorted(normalize(g) for g in groups)))


@pytest.mark.api
def test_agent_finds_every_expected_exam(tmp_path):
    import json

    from exam_agent.loop import run_agent

    def no_student(course, options):
        raise AssertionError(f"Asked for {course}, but every group is pre-saved")

    groups = GroupMemory(tmp_path / "groups.json", ask=no_student)
    groups.groups = {"UL2IN013": "2", "UL2XX002": "2"}

    exams = run_agent(
        "Find the exams announced in my email.", FakeMailbox(FIXTURES), groups, date(2026, 3, 1)
    )

    expected = [
        key(e["course_code"], e["status"], e["date"], e.get("start"), e.get("end"), e.get("groups", []))
        for email in json.loads(FIXTURES.read_text(encoding="utf-8"))
        for e in email["expected"]
    ]
    got = [
        key(
            e["course_code"],
            e["status"],
            e["date"].isoformat(),
            e["start"] and f"{e['start']:%H:%M}",
            e["end"] and f"{e['end']:%H:%M}",
            e["groups"],
        )
        for e in exams
    ]
    assert sorted(got) == sorted(expected)

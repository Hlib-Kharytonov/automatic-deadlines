"""The .ics file: build it, read it back, check what a calendar app will see. No API calls."""

from datetime import UTC, date, datetime, timedelta

from icalendar import Calendar

from exam_agent.calendar_file import build_calendar, event_uid, select_for_calendar, write_ics
from exam_agent.dates import PARIS, exam_times

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
TODAY = date(2026, 11, 16)


def exam(day: date, start: str | None = "18:30", end: str | None = None, **overrides) -> dict:
    """An exam as process_report returns it."""
    start_at, end_at = exam_times(day, start, end) if start else (None, None)
    entry = {
        "email_id": "m1",
        "course_code": "UL2IN010",
        "exam_name": "CC1 Introduction aux bases de données",
        "status": "scheduled" if start else "time_unknown",
        "date": day,
        "start": start_at,
        "end": end_at,
        "groups": [],
        "quote": "vous allez avoir votre première CC1 le 30 Novembre à 18h30",
    }
    return entry | overrides


def events_in(calendar: Calendar) -> list:
    return list(calendar.walk("VEVENT"))


def test_only_upcoming_scheduled_exams_go_in_the_calendar():
    upcoming = exam(date(2026, 11, 30))
    today_exam = exam(TODAY)
    past = exam(date(2026, 11, 2))
    no_time = exam(date(2026, 12, 7), start=None)
    assert select_for_calendar([upcoming, today_exam, past, no_time], TODAY) == [upcoming, today_exam]


def test_event_has_paris_times_title_quote_and_reminder():
    [event] = events_in(build_calendar([exam(date(2026, 11, 30))], NOW))
    assert event["summary"] == "CC1 Introduction aux bases de données (UL2IN010)"
    assert event.decoded("dtstart") == datetime(2026, 11, 30, 18, 30, tzinfo=PARIS)
    assert event.decoded("dtend") == datetime(2026, 11, 30, 20, 30, tzinfo=PARIS)
    assert event["dtstart"].params["TZID"] == "Europe/Paris"
    assert "première CC1 le 30 Novembre" in event["description"]

    [alarm] = event.walk("VALARM")
    assert alarm["action"] == "DISPLAY"
    assert alarm.decoded("trigger") == -timedelta(days=1)


def test_uid_is_stable_and_differs_between_exams():
    a = exam(date(2026, 11, 30))
    assert event_uid(a) == event_uid(exam(date(2026, 11, 30))) == "ul2in010-20261130t1830@exam-agent"
    assert event_uid(a) != event_uid(exam(date(2026, 12, 7)))


def test_course_code_not_repeated_in_title():
    [event] = events_in(build_calendar([exam(date(2026, 11, 30), exam_name="UL2IN010 CC1")], NOW))
    assert event["summary"] == "UL2IN010 CC1"


def test_file_round_trip_includes_paris_timezone(tmp_path):
    path = tmp_path / "exams.ics"
    write_ics([exam(date(2026, 11, 30)), exam(date(2026, 12, 7), "10:45", "12:15")], path, NOW)
    calendar = Calendar.from_ical(path.read_bytes())
    assert len(events_in(calendar)) == 2
    assert [tz["tzid"] for tz in calendar.walk("VTIMEZONE")] == ["Europe/Paris"]


def test_empty_calendar_is_still_a_valid_file(tmp_path):
    path = tmp_path / "exams.ics"
    write_ics([], path, NOW)
    calendar = Calendar.from_ical(path.read_bytes())
    assert calendar["version"] == "2.0" and events_in(calendar) == []

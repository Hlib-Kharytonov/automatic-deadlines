"""Write exams to an .ics file that any calendar app can import.

No AI here: the agent loop already returned checked data, so this is plain code.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from icalendar import Alarm, Calendar, Event

REMINDER = timedelta(days=1)


def select_for_calendar(exams: list[dict], today: date) -> list[dict]:
    """Only exams with a real time slot, today or later.

    time_unknown exams stay notices (no event: we would have to invent a time),
    and past exams are useless in a calendar.
    """
    return [e for e in exams if e["status"] == "scheduled" and e["date"] >= today]


def event_uid(exam: dict) -> str:
    """Stable id: the same exam gets the same UID on every run, so re-importing
    the file updates the event instead of adding a duplicate."""
    course = exam["course_code"] or "unknown-course"
    return f"{course}-{exam['start']:%Y%m%dT%H%M}@exam-agent".lower()


def event_title(exam: dict) -> str:
    title = exam["exam_name"]
    if exam["course_code"] and exam["course_code"] not in title:
        title += f" ({exam['course_code']})"
    return title


def build_calendar(exams: list[dict], now: datetime) -> Calendar:
    calendar = Calendar()
    calendar.add("prodid", "-//exam-agent//EN")
    calendar.add("version", "2.0")

    for exam in exams:
        event = Event()
        event.add("uid", event_uid(exam))
        event.add("dtstamp", now)
        event.add("dtstart", exam["start"])  # aware datetimes in Europe/Paris
        event.add("dtend", exam["end"])
        title = event_title(exam)
        event.add("summary", title)
        event.add("description", f'"{exam["quote"]}"\n\nFound by exam-agent in email {exam["email_id"]}.')

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("trigger", -REMINDER)
        alarm.add("description", f"Tomorrow: {title}")
        event.add_component(alarm)

        calendar.add_component(event)

    # Adds the VTIMEZONE block for Europe/Paris, so apps don't have to guess the zone.
    calendar.add_missing_timezones()
    return calendar


def write_ics(exams: list[dict], path: Path, now: datetime) -> None:
    path.write_bytes(build_calendar(exams, now).to_ical())

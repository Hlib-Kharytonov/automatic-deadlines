"""ExamCalendar with a stand-in for the Google Calendar API: no network, no account."""

import json
from datetime import date

import httplib2
import pytest
from googleapiclient.errors import HttpError

from exam_agent.dates import exam_times
from exam_agent.gcal import ExamCalendar, event_body

TODAY = date(2026, 11, 16)


def exam(day: date, start: str = "18:30", name: str = "CC1 Bases de données") -> dict:
    start_at, end_at = exam_times(day, start)
    return {
        "email_id": "m1", "course_code": "UL2IN010", "exam_name": name, "status": "scheduled",
        "date": day, "start": start_at, "end": end_at, "groups": [],
        "quote": "vous allez avoir votre première CC1 le 30 Novembre à 18h30",
    }


class FakeCalendarApi:
    """Mimics service.calendars().insert / events().list / events().insert, and records writes."""

    def __init__(self, existing_uids=(), calendar_gone=False):
        self.existing = list(existing_uids)
        self.calendar_gone = calendar_gone
        self.writes = []      # every call that changes something in Google
        self.list_params = []

    def calendars(self):
        return _Resource(insert=self._insert_calendar)

    def events(self):
        return _Resource(list=self._list_events, insert=self._insert_event)

    def _insert_calendar(self, body):
        self.writes.append(("create calendar", body["summary"]))
        return {"id": "cal123"}

    def _list_events(self, **params):
        self.list_params.append(params)
        if self.calendar_gone:
            raise HttpError(httplib2.Response({"status": 404}), b"not found")
        return {"items": [{"iCalUID": uid} for uid in self.existing]}

    def _insert_event(self, calendarId, body):
        self.writes.append(("insert event", calendarId, body["iCalUID"]))
        return {"id": "e1"}


class _Resource:
    def __init__(self, **methods):
        self.methods = methods

    def __getattr__(self, name):
        method = self.methods[name]
        return lambda **kwargs: _Call(lambda: method(**kwargs))


class _Call:
    def __init__(self, run):
        self.run = run

    def execute(self):
        return self.run()


class Student:
    def __init__(self, answer: bool):
        self.answer, self.asked = answer, []

    def __call__(self, question):
        self.asked.append(question)
        return self.answer


@pytest.fixture
def state(tmp_path):
    return tmp_path / "exam_calendar.json"


def test_no_means_nothing_is_written_at_all(state):
    api = FakeCalendarApi()
    student = Student(False)
    added = ExamCalendar(api, state).sync([exam(date(2026, 11, 30))], TODAY, confirm=student)
    assert added == []
    assert student.asked == ["Add these 1 events to your 'Exams' calendar?"]
    assert api.writes == []           # not even the calendar was created
    assert not state.exists()


def test_yes_creates_the_calendar_once_and_adds_every_new_event(state):
    api = FakeCalendarApi()
    exams = [exam(date(2026, 11, 30)), exam(date(2026, 12, 7), "10:45")]
    added = ExamCalendar(api, state).sync(exams, TODAY, confirm=Student(True))
    assert added == exams
    assert api.writes == [
        ("create calendar", "Exams"),
        ("insert event", "cal123", "ul2in010-20261130t1830@exam-agent"),
        ("insert event", "cal123", "ul2in010-20261207t1045@exam-agent"),
    ]
    assert json.loads(state.read_text()) == {"calendar_id": "cal123"}


def test_events_already_there_or_deleted_are_not_offered_again(state):
    state.write_text(json.dumps({"calendar_id": "cal123"}))
    api = FakeCalendarApi(existing_uids=["ul2in010-20261130t1830@exam-agent"])
    student = Student(True)
    added = ExamCalendar(api, state).sync(
        [exam(date(2026, 11, 30)), exam(date(2026, 12, 7), "10:45")], TODAY, confirm=student
    )
    assert [e["date"] for e in added] == [date(2026, 12, 7)]
    assert api.writes == [("insert event", "cal123", "ul2in010-20261207t1045@exam-agent")]
    assert api.list_params[0]["showDeleted"] is True  # events I deleted count as handled


def test_nothing_new_means_no_question(state):
    state.write_text(json.dumps({"calendar_id": "cal123"}))
    api = FakeCalendarApi(existing_uids=["ul2in010-20261130t1830@exam-agent"])
    student = Student(True)
    assert ExamCalendar(api, state).sync([exam(date(2026, 11, 30))], TODAY, confirm=student) == []
    assert student.asked == [] and api.writes == []


def test_calendar_deleted_by_hand_is_recreated(state):
    state.write_text(json.dumps({"calendar_id": "old"}))
    api = FakeCalendarApi(calendar_gone=True)
    ExamCalendar(api, state).sync([exam(date(2026, 11, 30))], TODAY, confirm=Student(True))
    assert api.writes[0] == ("create calendar", "Exams")
    assert json.loads(state.read_text()) == {"calendar_id": "cal123"}


def test_event_body():
    body = event_body(exam(date(2026, 11, 30)))
    assert body["summary"] == "CC1 Bases de données (UL2IN010)"
    assert body["start"] == {"dateTime": "2026-11-30T18:30:00+01:00", "timeZone": "Europe/Paris"}
    assert body["end"]["dateTime"] == "2026-11-30T20:30:00+01:00"
    assert body["reminders"] == {"useDefault": False, "overrides": [{"method": "popup", "minutes": 1440}]}
    assert "première CC1" in body["description"]

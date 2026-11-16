"""Phase 3: add exams to a dedicated "Exams" Google Calendar, after an explicit yes.

Safety, in layers:
- Permission: calendar.app.created, so this code can only touch calendars it
  created itself. Your other calendars are out of reach, whatever happens.
- Claude has no calendar tool. Only this code writes, after the agent has finished.
- Nothing is created without a "yes" typed by the student: sync() asks before
  any write, and it is the only function that writes.
"""

import json
from datetime import date, datetime, time
from pathlib import Path

from exam_agent.calendar_file import REMINDER, event_title, event_uid
from exam_agent.dates import PARIS
from exam_agent.google_auth import SECRETS, connect

SCOPES = ["https://www.googleapis.com/auth/calendar.app.created"]
TOKEN_FILE = SECRETS / "calendar_token.json"
STATE_FILE = SECRETS / "exam_calendar.json"  # the id of the calendar we created
CALENDAR_NAME = "Exams"


def ask_yes_in_terminal(question: str) -> bool:
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "o", "oui")


class ExamCalendar:
    def __init__(self, service=None, state_file: Path = STATE_FILE):
        self.service = service if service is not None else connect("calendar", "v3", SCOPES, TOKEN_FILE)
        self.state_file = state_file

    @property
    def calendar_id(self) -> str | None:
        if self.state_file.exists():
            return json.loads(self.state_file.read_text(encoding="utf-8"))["calendar_id"]
        return None

    def existing_uids(self, today: date) -> set[str]:
        """UIDs of events in the Exams calendar from today on, including ones I deleted.

        A deleted event counts as handled: if I removed it, I don't want it offered again.
        """
        from googleapiclient.errors import HttpError

        if self.calendar_id is None:
            return set()
        uids, page = set(), None
        try:
            while True:
                listing = (
                    self.service.events()
                    .list(
                        calendarId=self.calendar_id,
                        timeMin=datetime.combine(today, time(0), tzinfo=PARIS).isoformat(),
                        singleEvents=True,
                        showDeleted=True,
                        pageToken=page,
                    )
                    .execute()
                )
                uids |= {e["iCalUID"] for e in listing.get("items", []) if "iCalUID" in e}
                page = listing.get("nextPageToken")
                if not page:
                    return uids
        except HttpError as error:
            if error.resp.status in (404, 410):
                self.state_file.unlink()  # the calendar was deleted by hand: start a new one
                return set()
            raise

    def _ensure_calendar(self) -> str:
        if self.calendar_id is None:
            created = (
                self.service.calendars()
                .insert(
                    body={
                        "summary": CALENDAR_NAME,
                        "timeZone": "Europe/Paris",
                        "description": "Exams found in my email by exam-agent.",
                    }
                )
                .execute()
            )
            self.state_file.parent.mkdir(mode=0o700, exist_ok=True)
            self.state_file.write_text(json.dumps({"calendar_id": created["id"]}) + "\n", encoding="utf-8")
        return self.calendar_id

    def _insert(self, exam: dict) -> None:
        self.service.events().insert(calendarId=self._ensure_calendar(), body=event_body(exam)).execute()

    def sync(self, exams: list[dict], today: date, confirm=ask_yes_in_terminal) -> list[dict]:
        """Add the exams that aren't in the calendar yet, if the student says yes.

        `exams` must already be filtered with select_for_calendar(). Returns what was added.
        """
        existing = self.existing_uids(today)
        new = [e for e in exams if event_uid(e) not in existing]
        print(
            f"\n=== Google Calendar '{CALENDAR_NAME}': {len(new)} new, "
            f"{len(exams) - len(new)} already there or deleted by you ==="
        )
        if not new:
            return []
        for exam in new:
            print(f"  {exam['start']:%a %d %b %H:%M}-{exam['end']:%H:%M}  {exam['exam_name']}")
        # The only gate before any write. Not a prompt to the model: plain code.
        if not confirm(f"Add these {len(new)} events to your '{CALENDAR_NAME}' calendar?"):
            print("Nothing added.")
            return []
        for exam in new:
            self._insert(exam)
        print(f"Added {len(new)} events.")
        return new


def event_body(exam: dict) -> dict:
    return {
        "iCalUID": event_uid(exam),  # same id as in exams.ics: the duplicate check relies on it
        "summary": event_title(exam),
        "description": f'"{exam["quote"]}"\n\nFound by exam-agent in email {exam["email_id"]}.',
        "start": {"dateTime": exam["start"].isoformat(), "timeZone": "Europe/Paris"},
        "end": {"dateTime": exam["end"].isoformat(), "timeZone": "Europe/Paris"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": int(REMINDER.total_seconds() // 60)}],
        },
    }

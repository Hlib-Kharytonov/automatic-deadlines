"""Turn the date and time pieces Claude extracts into real dates.

Claude only reads the text ("le jeudi 28 mai", "ce soir à 18h15") and reports the
pieces it saw. All calendar arithmetic happens here, where it can be tested.
Errors are raised as ValueError with a message written for Claude, so the loop
can send it back and Claude can re-read the email.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
DEFAULT_DURATION = timedelta(hours=2)
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def resolve_date(
    email_date: date,
    *,
    day: int | None = None,
    month: int | None = None,
    year: int | None = None,
    weekday: str | None = None,
    relative: str | None = None,
) -> date:
    """Work out the exam date from what the email says.

    Absolute: day + month (+ year). A missing year is the email's year, or the next
    one if that date has already passed ("janvier" in a November email).
    Relative: "today" ("ce soir"), "tomorrow" ("demain"), "this" + weekday
    ("ce jeudi"), "next_week" + weekday ("jeudi de la semaine prochaine").
    If the email also names the weekday, it is checked against the date.
    """
    if relative is not None:
        return _resolve_relative(email_date, relative, weekday)
    if day is None or month is None:
        raise ValueError("Give either day and month, or a relative date.")
    if year is None:
        year = email_date.year
        if (month, day) < (email_date.month, email_date.day):
            year += 1
    try:
        result = date(year, month, day)
    except ValueError:
        raise ValueError(f"{day}/{month}/{year} is not a real date. Re-read the email.") from None
    if weekday is not None and WEEKDAYS[result.weekday()] != weekday:
        raise ValueError(
            f"{result.isoformat()} is a {WEEKDAYS[result.weekday()]}, "
            f"but the email says {weekday}. Re-read the email."
        )
    return result


def _resolve_relative(email_date: date, relative: str, weekday: str | None) -> date:
    if relative == "today":
        return email_date
    if relative == "tomorrow":
        return email_date + timedelta(days=1)
    if weekday not in WEEKDAYS:
        raise ValueError(f"relative={relative!r} needs a weekday, one of {WEEKDAYS}.")
    target = WEEKDAYS.index(weekday)
    if relative == "this":
        # The next such weekday, or the email's own day if it already is that weekday.
        return email_date + timedelta(days=(target - email_date.weekday()) % 7)
    if relative == "next_week":
        # That weekday in the following Monday-to-Sunday week.
        next_monday = email_date + timedelta(days=7 - email_date.weekday())
        return next_monday + timedelta(days=target)
    raise ValueError(f"Unknown relative value {relative!r}. Use today, tomorrow, this or next_week.")


def exam_times(day: date, start: str, end: str | None = None) -> tuple[datetime, datetime]:
    """Start and end in Paris time. Without an end, the exam lasts DEFAULT_DURATION."""
    start_at = datetime.combine(day, _parse_hhmm(start), tzinfo=PARIS)
    end_at = datetime.combine(day, _parse_hhmm(end), tzinfo=PARIS) if end else start_at + DEFAULT_DURATION
    if end_at <= start_at:
        raise ValueError(f"End {end} is not after start {start}. Re-read the email.")
    return start_at, end_at


def _parse_hhmm(text: str) -> time:
    try:
        return time.fromisoformat(text)
    except ValueError:
        raise ValueError(f"Time {text!r} must look like 14:00 or 08:30.") from None

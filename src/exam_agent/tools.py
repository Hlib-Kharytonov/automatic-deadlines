"""The tools Claude can call: their definitions, and the code that runs them.

TOOL_DEFINITIONS is sent to Claude with every request. Claude reads the names,
descriptions and input schemas to decide what to call. Claude never runs anything:
it only asks, and run_tool() does the work.
"""

import json
from datetime import date, timedelta

from exam_agent.dates import WEEKDAYS, exam_times, resolve_date
from exam_agent.groups import GroupMemory


def _nullable(schema: dict) -> dict:
    """Allow a value or null. Every field stays required, so Claude must write null on purpose."""
    return {"anyOf": [schema, {"type": "null"}]}


def _hhmm(description: str) -> dict:
    return {"type": "string", "description": f"{description} Format HH:MM, 24-hour: '16h30' -> '16:30', '14h' -> '14:00'."}

_EXAM_SCHEMA = {
    "type": "object",
    "properties": {
        "email_id": {"type": "string", "description": "The id of the email that announces this exam"},
        "course_code": _nullable(
            {"type": "string", "description": "Course code like UL2IN013, from the subject tag or the body"}
        ),
        "exam_name": {"type": "string", "description": "Short name, e.g. 'CC1 Cours fictif A' or 'Algorithmique 1'"},
        "date": {
            "type": "object",
            "description": (
                "The date as the email writes it. If the email gives a day and month, fill day and month. "
                "Use relative only when it gives no day and month ('ce jeudi', 'ce soir', 'demain'). "
                "Never calculate a date yourself."
            ),
            "properties": {
                "day": _nullable({"type": "integer"}),
                "month": _nullable({"type": "integer", "description": "1 to 12"}),
                "year": _nullable({"type": "integer", "description": "Only if the email writes the year"}),
                "weekday": _nullable(
                    {"type": "string", "enum": WEEKDAYS, "description": "If the email names the weekday"}
                ),
                "relative": _nullable(
                    {
                        "type": "string",
                        "enum": ["today", "tomorrow", "this", "next_week"],
                        "description": (
                            "today = 'ce soir'/'aujourd'hui', tomorrow = 'demain', "
                            "this = 'ce jeudi', next_week = 'jeudi de la semaine prochaine'"
                        ),
                    }
                ),
            },
            "required": ["day", "month", "year", "weekday", "relative"],
            "additionalProperties": False,
        },
        "start": _nullable(_hhmm("Start time; null if the email gives no precise time.")),
        "end": _nullable(_hhmm("End time, only if written.")),
        "duration_minutes": _nullable(
            {"type": "integer", "description": "Only if a length is written instead of an end time ('durée 1h30' = 90)"}
        ),
        "groups": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Groups this slot is for, short form, e.g. ['2'] or ['1', '3']. Empty if it is for everyone. "
                "Report every group's slot, not only the student's; code keeps the right one."
            ),
        },
        "quote": {"type": "string", "description": "The sentence that announces the exam, copied word for word"},
    },
    "required": [
        "email_id", "course_code", "exam_name", "date", "start", "end", "duration_minutes", "groups", "quote",
    ],
    "additionalProperties": False,
}

TOOL_DEFINITIONS = [
    {
        "name": "search_emails",
        "description": (
            "Search the student's mailbox. Returns up to 20 matching emails, newest first, "
            "each with id, sender, date, subject and a short snippet (not the full text). "
            "Words separated by spaces must all appear; put OR between alternatives, "
            "e.g. 'partiel OR examen OR CC'. Matching ignores case and accents but "
            "matches whole words only: 'CC' does not match 'CC1'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search words, e.g. 'partiel OR examen'"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "read_email",
        "description": (
            "Return the full text of one email: id, sender, date, subject and body. "
            "Use an id from search_emails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string", "description": "An id returned by search_emails"},
            },
            "required": ["email_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_my_group",
        "description": (
            "Return the student's group in one course. Call it whenever an email gives different "
            "dates or times for different groups, or says an exam is only for some groups, before "
            "calling report_exams. Never guess the group. If it isn't saved yet, the student is "
            "asked; the answer may be a group that is not among the options."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "course_code": {"type": "string", "description": "Course code like UL2XX002"},
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "The group labels the email mentions, short form, e.g. ['2', '4']",
                },
            },
            "required": ["course_code", "options"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "report_exams",
        "description": (
            "Report the exams you found. This is your final answer: call it exactly once, after "
            "reading the emails, with every exam in one list (an empty list if there are none). "
            "Report each exam with the fields as written in the email; code computes the real dates. "
            "If an exam has different dates or times per group, report one entry per group. "
            "If the call returns an error, nothing was recorded: fix the exams it names and "
            "call report_exams again with the full list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"exams": {"type": "array", "items": _EXAM_SCHEMA}},
            "required": ["exams"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

# The tool whose successful call ends the loop. Its input is the agent's result.
FINAL_TOOL = "report_exams"


def run_tool(name: str, tool_input: dict, mailbox, groups: GroupMemory | None = None) -> str:
    """Run one tool and return its result as a JSON string for Claude.

    Raises ValueError for bad input (unknown tool, unknown email id). The loop
    should catch it and send the message back to Claude as an error result.
    """
    if name == "search_emails":
        result = mailbox.search(tool_input["query"])
    elif name == "read_email":
        result = mailbox.read(tool_input["email_id"])
    elif name == "get_my_group" and groups is not None:
        course = tool_input["course_code"]
        result = {"course_code": course, "my_group": groups.get_or_ask(course, tool_input["options"])}
    else:
        raise ValueError(f"Unknown tool {name!r}.")
    return json.dumps(result, ensure_ascii=False)


def process_report(exams: list[dict], mailbox, groups: GroupMemory) -> list[dict]:
    """Turn report_exams input into exams with real dates.

    Returns every slot Claude reported, including other groups' slots; use
    GroupMemory.is_mine() to keep mine. All or nothing: if any exam fails, raise
    one ValueError listing every problem, so Claude can fix them all in one retry.
    """
    results, errors = [], []
    for number, exam in enumerate(exams, start=1):
        try:
            _check_group_known(exam, groups)
            results.append(_process_exam(exam, mailbox))
        except ValueError as error:
            errors.append(f"- Exam {number} ({exam['exam_name']!r}, email {exam['email_id']}): {error}")
    if errors:
        raise ValueError(
            "Nothing was recorded. Fix these exams and call report_exams again with the full list:\n"
            + "\n".join(errors)
        )
    return results


def _check_group_known(exam: dict, groups: GroupMemory) -> None:
    # Zero trust: code, not Claude, makes sure the group question was actually asked.
    if not exam["groups"]:
        return
    if exam["course_code"] is None:
        raise ValueError("This slot is for specific groups, so course_code is needed to look up my group.")
    if groups.get(exam["course_code"]) is None:
        raise ValueError(
            f"This slot is for groups {exam['groups']}, but my group in {exam['course_code']} is unknown. "
            "Call get_my_group first."
        )


def _process_exam(exam: dict, mailbox) -> dict:
    # The email's date comes from the mailbox, not from Claude: relative dates
    # ("ce jeudi") are counted from it, so it must be exact.
    email_date = date.fromisoformat(mailbox.read(exam["email_id"])["date"])
    day = resolve_date(email_date, **exam["date"])

    start = end = None
    if exam["start"] is not None:
        start, end = exam_times(day, exam["start"], exam["end"])
        if exam["end"] is None and exam["duration_minutes"] is not None:
            if exam["duration_minutes"] <= 0:
                raise ValueError(f"duration_minutes must be positive, got {exam['duration_minutes']}.")
            end = start + timedelta(minutes=exam["duration_minutes"])

    return {
        "email_id": exam["email_id"],
        "course_code": exam["course_code"],
        "exam_name": exam["exam_name"],
        "status": "scheduled" if start else "time_unknown",
        "date": day,
        "start": start,
        "end": end,
        "groups": exam["groups"],
        "quote": exam["quote"],
    }

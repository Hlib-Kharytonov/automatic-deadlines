import sys
from pathlib import Path

FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures" / "emails.json"


def main() -> None:
    # Imported here so that loading the package (e.g. in tests) doesn't create an API client.
    from exam_agent.loop import AgentError, run_agent
    from exam_agent.mail.fake import FakeMailbox

    mailbox = FakeMailbox(FIXTURES)
    try:
        exams = run_agent("Find the exams announced in my email.", mailbox)
    except AgentError as error:
        sys.exit(f"\nAgent failed: {error}")

    print(f"\n=== {len(exams)} exams ===")
    for exam in sorted(exams, key=lambda e: e["date"]):
        if exam["start"]:
            when = f"{exam['start']:%H:%M}-{exam['end']:%H:%M}"
        else:
            when = "time unknown"
        groups = f"  [groups {', '.join(exam['groups'])}]" if exam["groups"] else ""
        print(f"{exam['date']:%a %Y-%m-%d}  {when:<12}  {exam['course_code'] or '?':<9}  "
              f"{exam['exam_name']}{groups}")
        print(f"    \"{exam['quote']}\"")

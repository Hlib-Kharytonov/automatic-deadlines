import sys
from datetime import date
from pathlib import Path

from exam_agent.groups import GroupMemory
from exam_agent.mail.fake import FakeMailbox

PROJECT = Path(__file__).parents[2]
FIXTURES = PROJECT / "tests" / "fixtures" / "emails.json"
GROUPS_FILE = PROJECT / "groups.json"  # gitignored: personal data


def main() -> None:
    import argparse

    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="Find exam announcements in my email.")
    parser.add_argument("--fake", action="store_true", help="use the sample emails instead of Gmail")
    args = parser.parse_args()

    load_dotenv()  # before anything reads GOOGLE_* or creates the Anthropic client
    if args.fake:
        mailbox = FakeMailbox(FIXTURES)
    else:
        from exam_agent.mail.gmail import GmailMailbox

        mailbox = GmailMailbox()
    run(mailbox, GroupMemory(GROUPS_FILE), date.today())


def run(mailbox, groups: GroupMemory, today: date) -> None:
    # Imported here so that loading the package (e.g. in tests) doesn't create an API client.
    from exam_agent.loop import AgentError, run_agent

    try:
        exams = run_agent("Find the exams announced in my email.", mailbox, groups, today)
    except AgentError as error:
        sys.exit(f"\nAgent failed: {error}")

    mine = [e for e in exams if groups.is_mine(e["course_code"], e["groups"])]
    print(f"\n=== {len(mine)} exams for me ({len(exams) - len(mine)} other-group slots hidden) ===")
    for exam in sorted(mine, key=lambda e: e["date"]):
        if exam["start"]:
            when = f"{exam['start']:%H:%M}-{exam['end']:%H:%M}"
        else:
            when = "time unknown"  # shown as a notice; never becomes a calendar event
        past = "  (past)" if exam["date"] < today else ""
        print(f"{exam['date']:%a %Y-%m-%d}  {when:<12}  {exam['course_code'] or '?':<9}  "
              f"{exam['exam_name']}{past}")
        print(f"    \"{exam['quote']}\"")

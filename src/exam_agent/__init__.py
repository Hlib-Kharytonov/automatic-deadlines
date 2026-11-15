from pathlib import Path

FIXTURES = Path(__file__).parents[2] / "tests" / "fixtures" / "emails.json"


def main() -> None:
    # Imported here so that loading the package (e.g. in tests) doesn't create an API client.
    from exam_agent.loop import run_agent
    from exam_agent.mail.fake import FakeMailbox

    mailbox = FakeMailbox(FIXTURES)
    answer = run_agent("Find the exams announced in my email.", mailbox)
    print("\n=== Final answer ===")
    print(answer)

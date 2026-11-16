"""GroupMemory and the get_my_group tool. No API calls here."""

import json
from pathlib import Path

from exam_agent.groups import GroupMemory
from exam_agent.mail.fake import FakeMailbox
from exam_agent.tools import run_tool

FIXTURES = Path(__file__).parent / "fixtures" / "emails.json"


class FakeStudent:
    """Stands in for the human answering in the terminal."""

    def __init__(self, answer):
        self.answer = answer
        self.questions = []

    def __call__(self, course, options):
        self.questions.append((course, options))
        return self.answer


def test_unknown_group_asks_once_then_remembers(tmp_path):
    student = FakeStudent("2")
    path = tmp_path / "groups.json"
    memory = GroupMemory(path, ask=student)

    assert memory.get_or_ask("UL2XX002", ["2", "4"]) == "2"
    assert memory.get_or_ask("UL2XX002", ["2", "4"]) == "2"
    assert student.questions == [("UL2XX002", ["2", "4"])]

    # Saved to disk, so a new run (new GroupMemory) doesn't ask again.
    assert json.loads(path.read_text()) == {"UL2XX002": "2"}
    assert GroupMemory(path, ask=FakeStudent("never")).get("UL2XX002") == "2"


def test_groups_are_per_course(tmp_path):
    memory = GroupMemory(tmp_path / "groups.json", ask=FakeStudent("4"))
    memory.groups = {"UL2IN013": "2"}
    assert memory.get_or_ask("UL2XX002", ["2", "4"]) == "4"
    assert memory.get("UL2IN013") == "2"


def test_is_mine(tmp_path):
    memory = GroupMemory(tmp_path / "groups.json")
    memory.groups = {"UL2XX002": "Groupe 2", "UL2IN013": "2"}
    assert memory.is_mine("UL2XX002", ["2"])  # 'Groupe 2' == '2'
    assert not memory.is_mine("UL2XX002", ["4"])
    assert not memory.is_mine("UL2IN013", ["1", "3"])  # quiz for groups 1 and 3 only
    assert memory.is_mine("UL2IN009", [])  # for everyone
    assert not memory.is_mine("UL2ZZ999", ["1"])  # unknown group: not shown as mine


def test_get_my_group_tool_returns_json(tmp_path):
    memory = GroupMemory(tmp_path / "groups.json", ask=FakeStudent("4"))
    result = json.loads(
        run_tool(
            "get_my_group", {"course_code": "UL2XX002", "options": ["2", "4"]}, FakeMailbox(FIXTURES), memory
        )
    )
    assert result == {"course_code": "UL2XX002", "my_group": "4"}

"""My group in each course, saved in groups.json (gitignored).

Groups differ between courses, so the memory is keyed by course code. Claude never
guesses a group: if one isn't saved, the student is asked in the terminal once
and the answer is saved for next time.
"""

import json
from pathlib import Path


def normalize(label: str) -> str:
    """'Groupe 2', 'group 2' and '2' are the same group."""
    text = label.strip().lower()
    for prefix in ("groupe", "group", "gr."):
        text = text.removeprefix(prefix)
    return text.strip()


def ask_in_terminal(course: str, options: list[str]) -> str:
    print(f"\n  ? Which group are you in for {course}?")
    print(f"    The email mentions: {', '.join(options)}")
    while not (answer := input("    Your group: ").strip()):
        pass
    return answer


class GroupMemory:
    def __init__(self, path: Path, ask=ask_in_terminal):
        self.path = path
        self.ask = ask  # replaced in tests, and later by a notification (phase 5)
        self.groups = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def get(self, course: str) -> str | None:
        return self.groups.get(course)

    def get_or_ask(self, course: str, options: list[str]) -> str:
        if course not in self.groups:
            self.groups[course] = self.ask(course, options)
            self.path.write_text(json.dumps(self.groups, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self.groups[course]

    def is_mine(self, course: str, slot_groups: list[str]) -> bool:
        """True if the slot is for everyone, or for my saved group in that course."""
        if not slot_groups:
            return True
        mine = self.get(course)
        return mine is not None and normalize(mine) in {normalize(g) for g in slot_groups}

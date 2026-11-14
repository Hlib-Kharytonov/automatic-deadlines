"""A fake mailbox that reads tests/fixtures/emails.json.

It lets the agent run before Gmail is connected. The Gmail mailbox (phase 1b)
will have the same two methods, search() and read(), so nothing else changes.
"""

import json
import re
import unicodedata
from pathlib import Path

SNIPPET_LENGTH = 160


def _words(text: str) -> set[str]:
    """Lowercase, strip accents and split into words, so 'Contrôle' matches 'controle'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return set(re.findall(r"\w+", plain))


class FakeMailbox:
    def __init__(self, path: Path):
        emails = json.loads(path.read_text(encoding="utf-8"))
        self.emails = {email["id"]: email for email in emails}

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Rough imitation of Gmail search.

        'partiel OR examen' matches either word. Words on the same side of an OR
        must all appear. Returns short summaries, newest first, never full bodies.
        """
        alternatives = [_words(part) for part in re.split(r"\s+OR\s+", query)]
        hits = []
        for email in self.emails.values():
            words = _words(email["subject"] + " " + email["body"])
            if any(alt and alt <= words for alt in alternatives):
                hits.append(
                    {
                        "id": email["id"],
                        "from": email["from"],
                        "date": email["date"],
                        "subject": email["subject"],
                        "snippet": email["body"][:SNIPPET_LENGTH].replace("\n", " "),
                    }
                )
        hits.sort(key=lambda hit: hit["date"], reverse=True)
        return hits[:max_results]

    def read(self, email_id: str) -> dict:
        if email_id not in self.emails:
            raise ValueError(f"No email with id {email_id!r}. Use an id returned by search_emails.")
        email = self.emails[email_id]
        return {key: email[key] for key in ("id", "from", "date", "subject", "body")}

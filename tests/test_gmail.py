"""GmailMailbox with a stand-in for the Gmail API: no network, no Google account."""

import base64
from email.message import EmailMessage

import httplib2
import pytest
from googleapiclient.errors import HttpError

from exam_agent.mail.gmail import GmailMailbox, body_text, build_query, paris_date

# 2026-03-24 08:15 UTC = 09:15 Paris
TUESDAY_MORNING_MS = "1774340100000"


def mime(body: str, subtype: str = "plain") -> EmailMessage:
    message = EmailMessage()
    message["From"] = "Moodle <noreply@moodle.example.fr>"
    message["Subject"] = "[UL2IN013 - Projet de développement - S2-25] Rappel: Quizz"
    message.set_content(body, subtype=subtype)
    return message


class FakeGmailApi:
    """Mimics service.users().messages().list/get(...).execute() for two emails."""

    def __init__(self, emails: dict[str, EmailMessage]):
        self.emails = emails
        self.queries = []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, userId, q, maxResults):
        self.queries.append(q)
        return _Call({"messages": [{"id": i} for i in self.emails]})

    def get(self, userId, id, format, metadataHeaders=None):
        if id not in self.emails:
            return _Call(error=HttpError(httplib2.Response({"status": 404}), b"not found"))
        message = self.emails[id]
        if format == "raw":
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            return _Call({"id": id, "internalDate": TUESDAY_MORNING_MS, "raw": raw})
        headers = [{"name": k, "value": message[k]} for k in metadataHeaders]
        return _Call(
            {
                "id": id,
                "internalDate": TUESDAY_MORNING_MS,
                "snippet": "ce jeudi aura lieu un Quizz",
                "payload": {"headers": headers},
            }
        )


class _Call:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def mailbox():
    return GmailMailbox(service=FakeGmailApi({"m1": mime("Bonjour,\nce jeudi aura lieu un Quizz.")}))


def test_search_adds_the_date_window_and_keeps_or_together(mailbox):
    hits = mailbox.search("quizz OR partiel")
    assert mailbox.service.queries == ["(quizz OR partiel) newer_than:6m"]
    assert hits == [
        {
            "id": "m1",
            "from": "Moodle <noreply@moodle.example.fr>",
            "date": "2026-03-24",
            "subject": "[UL2IN013 - Projet de développement - S2-25] Rappel: Quizz",
            "snippet": "ce jeudi aura lieu un Quizz",
        }
    ]


def test_read_decodes_the_body(mailbox):
    result = mailbox.read("m1")
    assert result["body"] == "Bonjour,\nce jeudi aura lieu un Quizz."
    assert result["date"] == "2026-03-24"
    assert "Projet de développement" in result["subject"]  # accents survive MIME encoding


def test_read_unknown_id_is_an_error_for_claude(mailbox):
    with pytest.raises(ValueError, match="No email with id"):
        mailbox.read("nope")


def test_html_body_becomes_text():
    html = "<html><style>p{color:red}</style><p>Le partiel aura lieu le <b>12&nbsp;décembre</b></p><p>à 14h</p></html>"
    assert body_text(mime(html, "html")) == "Le partiel aura lieu le 12 décembre\nà 14h"


def test_long_body_is_truncated_with_a_visible_marker():
    text = body_text(mime("x" * 25_000))
    assert text.endswith("[... truncated, 5000 more characters]")


def test_paris_date_uses_paris_not_utc():
    # 2026-03-24 23:30 UTC is already 2026-03-25 00:30 in Paris
    assert paris_date("1774395000000") == "2026-03-25"


def test_build_query():
    assert build_query("examen") == "(examen) newer_than:6m"

"""Gmail mailbox: the same search() and read() as FakeMailbox, backed by the Gmail API.

Read-only by construction: the only permission requested is gmail.readonly, so
Google itself refuses any change, whatever the code or the model tries.

Login: OAuth in the browser on the first run (no password). The token is saved in
.secrets/gmail_token.json and refreshed automatically.
"""

import base64
import email
import email.policy
from datetime import datetime
from html.parser import HTMLParser

from exam_agent.dates import PARIS
from exam_agent.google_auth import SECRETS, connect

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = SECRETS / "gmail_token.json"

# Only recent mail: old exams are noise. Gmail syntax, added to every search.
SEARCH_WINDOW = "newer_than:6m"
# Newsletters can be huge; exam announcements are short. Truncation is marked, never silent.
MAX_BODY_CHARS = 20_000


class GmailMailbox:
    def __init__(self, service=None):
        self.service = service if service is not None else connect("gmail", "v1", SCOPES, TOKEN_FILE)

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Gmail search. 'partiel OR examen' works as in Gmail's search box. Newest first."""
        messages = self.service.users().messages()
        listing = messages.list(userId="me", q=build_query(query), maxResults=max_results).execute()
        hits = []
        for item in listing.get("messages", []):
            meta = messages.get(
                userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject"]
            ).execute()
            headers = {h["name"]: h["value"] for h in meta["payload"].get("headers", [])}
            hits.append(
                {
                    "id": meta["id"],
                    "from": headers.get("From", ""),
                    "date": paris_date(meta["internalDate"]),
                    "subject": headers.get("Subject", ""),
                    "snippet": _html_to_text(meta.get("snippet", "")),
                }
            )
        return hits

    def read(self, email_id: str) -> dict:
        from googleapiclient.errors import HttpError

        try:
            raw = self.service.users().messages().get(userId="me", id=email_id, format="raw").execute()
        except HttpError as error:
            if error.resp.status in (400, 404):
                raise ValueError(
                    f"No email with id {email_id!r}. Use an id returned by search_emails."
                ) from None
            raise
        message = email.message_from_bytes(base64.urlsafe_b64decode(raw["raw"]), policy=email.policy.default)
        return {
            "id": raw["id"],
            "from": str(message.get("From", "")),
            "date": paris_date(raw["internalDate"]),
            "subject": str(message.get("Subject", "")),
            "body": body_text(message),
        }


def build_query(query: str) -> str:
    # Parentheses keep "a OR b" together before the date filter is added.
    return f"({query}) {SEARCH_WINDOW}"


def paris_date(internal_date_ms: str) -> str:
    """Gmail's receive time (ms since 1970, UTC) as a Paris calendar date, YYYY-MM-DD.

    Relative dates ("ce jeudi", "ce soir") are counted from this, so the time zone
    matters: an email received at 00:30 in Paris is still 23:30 UTC the day before.
    """
    return datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=PARIS).date().isoformat()


def body_text(message: email.message.EmailMessage) -> str:
    """The plain-text body, or the HTML body turned into text."""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    text = _html_to_text(content) if part.get_content_type() == "text/html" else content
    text = text.strip()
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + f"\n[... truncated, {len(text) - MAX_BODY_CHARS} more characters]"
    return text


class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)

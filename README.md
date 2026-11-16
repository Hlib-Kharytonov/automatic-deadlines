# exam-agent

Finds exam announcements in your email and adds them to Google Calendar.

French universities announce exams in free text, often in Moodle forum emails:

> Bonjour les étudiants, vous allez avoir votre première CC1 le 30 Novembre à 18h30

A keyword script can't reliably turn that into a calendar event, so exam-agent uses Claude to read the emails. Plain Python code then checks the result, computes the real dates and writes the calendar.

```
$ uv run exam-agent
--- Round 1: stop_reason=tool_use, tokens in/out=2937/160
  Claude asks: search_emails({'query': 'partiel OR examen OR CC1 OR quizz OR …'})
--- Round 2: stop_reason=tool_use, tokens in/out=7327/400
  Claude asks: read_email({'email_id': '1a1e667f26db0662'})
--- Round 3: stop_reason=tool_use, tokens in/out=11383/397
  Claude asks: report_exams(1 exams)

=== 1 exams for me (0 other-group slots hidden) ===
Mon 2026-11-30  18:30-20:30   UL2IN010   CC1 Introduction aux bases de données relationnelles
    "vous allez avoir votre première CC1 le 30 Novembre à 18h30"

1 upcoming exams written to exams.ics (import it into your calendar app).

=== Google Calendar 'Exams': 1 new, 0 already there or deleted by you ===
  Mon 30 Nov 18:30-20:30  CC1 Introduction aux bases de données relationnelles
Add these 1 events to your 'Exams' calendar? [y/N] y
Added 1 events.
```

Built as a learning project: the agent loop is hand-written with the Anthropic Python SDK, without agent frameworks.

## What it does

- Searches your Gmail (read-only) for exam announcements: partiel, examen, CC, quiz, contrôle, convocation…
- Extracts the exam name, date and time, including relative dates such as "ce jeudi" or "ce soir", which are computed from the email's date.
- Asks you which group you're in when an exam has different slots per group, and remembers the answer for each course.
- Writes the upcoming exams to `exams.ics`, which any calendar app can import.
- Adds them to a separate **"Exams"** Google Calendar, but only after you type `y`. Exams already in that calendar, or ones you deleted from it, are not offered again.

**Left out on purpose:**
- **No precise time** ("dans votre créneau habituel"): the exam is printed as a notice only, with no calendar event.
- **No fixed date** ("pas avant le 30 novembre, rien n'est sûr"): not reported until an email fixes the date.
- **Rooms:** not extracted yet.

## How it works

```
uv run exam-agent
│
├─ 1. FIND       Claude + tools, in a loop (the only part that uses AI)
│                Gmail ─search/read─► Claude ─report_exams─► exams checked by code
├─ 2. FILTER     code: keep my groups' slots, drop past exams and "time unknown"
├─ 3. FILE       code: write exams.ics
└─ 4. CALENDAR   code: compare with the Exams calendar, ask y/N, add new events
```

In stage 1, Claude can call four tools:

| Tool | What it does |
|---|---|
| `search_emails(query)` | Gmail search; returns ids, subjects and snippets |
| `read_email(email_id)` | Full text of one email |
| `get_my_group(course_code, options)` | Your saved group for a course; asks you in the terminal if unknown |
| `report_exams(exams)` | The final answer, with a strict schema. Code validates it; if something is wrong (an impossible date, a bad time format, an unknown group), the error goes back to Claude to fix. A valid report ends the loop. |

Claude reports the date fields exactly as the email writes them. Code works out the year, the Paris time zone, the default length (2 hours when no end time is given) and the duplicates.

### Safety

| Risk | Protection |
|---|---|
| An email contains instructions ("delete the calendar…") | Claude has no tool that writes anything. Email text is treated as data. |
| The program changes your email | The Gmail permission is `gmail.readonly`; Google enforces it. |
| The program touches your personal calendar | The calendar permission is `calendar.app.created`: only calendars this app created are reachable. |
| An event is added without your agreement | Plain code asks `[y/N]` before any calendar write. |
| Your group is guessed | A per-group exam is rejected until you have answered the group question. |

No passwords are stored. Google login happens in the browser (OAuth), and the tokens can be revoked at any time at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

**Privacy:** the emails Claude decides to open are sent to the Anthropic API so it can read them.

## Installation

### Requirements

- Linux or macOS
- [uv](https://docs.astral.sh/uv/), which also installs the right Python version (3.14) for you
- An [Anthropic API key](https://console.anthropic.com/). One run costs well under one cent with the default model (Claude Haiku 5.5).
- A Google account whose Gmail receives your university mail. If your university uses its own mailbox (Zimbra, Outlook), turn on automatic forwarding to Gmail first.

### 1. Get the code

```sh
git clone https://github.com/Hlib-Kharytonov/automatic-deadlines.git
cd automatic-deadlines
uv sync
```

If you don't have uv yet: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.

### 2. Create the `.env` file

```sh
cp .env.example .env
```

Paste your Anthropic API key after `ANTHROPIC_API_KEY=`. The two Google values come from the next step.

`.env` is gitignored. Never commit it.

### 3. Set up Google access (once, about 15 minutes)

All of this happens in the [Google Cloud Console](https://console.cloud.google.com/), signed in with the Gmail account that receives your university mail.

1. **Create a project.** Use the project picker at the top → **New project** → any name, e.g. `exam-agent`.
2. **Enable the two APIs.** Go to **APIs & Services → Library**, search for and **Enable**:
   - **Gmail API**
   - **Google Calendar API**
3. **Configure the consent screen.** In newer consoles this is called **Google Auth Platform**.
   - User type: **External**.
   - App name: anything. Support and developer email: your own.
   - Under **Audience → Test users**: add your Gmail address.
   - Leave the publishing status on **Testing**. You don't need to publish or verify the app.
4. **Create the login credentials.** Go to **Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**.
   - Copy the **Client ID** and **Client secret** into `.env`:
     ```
     GOOGLE_CLIENT_ID=1234567890-abc….apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=GOCSPX-…
     ```

### 4. First run

```sh
uv run exam-agent
```

1. Your browser opens to allow **read-only Gmail** access. Google warns *"Google hasn't verified this app"*; that's expected for your own app in Testing mode, so click **Continue**.
2. The agent searches your mail, and may ask which group you're in for some courses.
3. If there are upcoming exams, the browser opens a second time to allow access to **calendars created by this app**.
4. Check the list and type `y` to add the events.

The new **Exams** calendar appears in [Google Calendar](https://calendar.google.com) under **My calendars**. On a phone, you may need to tick it in the app's menu, or turn on its sync under Settings.

## Usage

```sh
uv run exam-agent                 # scan Gmail, write exams.ics, offer to add events to Google Calendar
uv run exam-agent --no-calendar   # scan Gmail, print the exams and write exams.ics only
uv run exam-agent --fake          # use the 8 sample emails in tests/fixtures/ (no Google at all)
```

Run it whenever you like. Each run only offers exams that aren't in the calendar yet.

### Files it creates

All of these are gitignored and stay on your machine.

| File | Contents | Safe to delete? |
|---|---|---|
| `.env` | API key and Google client credentials | No, you'd have to fill it in again |
| `.secrets/gmail_token.json` | Gmail login (read-only) | Yes: you'll be asked to log in again |
| `.secrets/calendar_token.json` | Calendar login (Exams calendar only) | Yes: you'll be asked to log in again |
| `.secrets/exam_calendar.json` | The id of the Exams calendar | Yes: a new Exams calendar is created on the next yes |
| `groups.json` | Your group in each course | Yes: you'll be asked again |
| `exams.ics` | The latest calendar file | Yes: it's rewritten on every run |

## Tests

```sh
uv run pytest          # 59 offline tests: no network, no cost, under a second
uv run pytest -m api   # end-to-end: the real agent on the sample emails, compared with the expected exams (costs a little)
```

The sample emails in `tests/fixtures/emails.json` include traps: a scholarship email that says "examen", a copy review, a postponed exam, and an exam with no fixed date yet. Each sample lists the exams that should be found.

## Troubleshooting

| Problem | Fix |
|---|---|
| `KeyError: 'GOOGLE_CLIENT_ID'` | `.env` is missing the Google values (step 3.4). |
| Browser says `access_denied` / "app is being tested" | Add your Gmail address under **Test users** (step 3.3). |
| `HttpError 403 … API has not been used in project` | Enable the Gmail API or the Google Calendar API (step 3.2), wait a minute, then try again. |
| Browser login every few days | Expected in Testing mode: Google expires the login after about 7 days, and the program reopens the browser by itself. |
| The Exams calendar doesn't show up | Tick **Exams** under **My calendars** in Google Calendar; on Android, turn on its sync. |
| An exam is missing | Searches cover the last 6 months and return at most 20 emails each. Look at the `Claude asks:` lines to see what was searched. |
| A wrong group was saved | Edit or delete `groups.json`. |
| An exam moved and the old event stays | Delete the old event by hand; it won't be offered again. |

## Project structure

```
src/exam_agent/
├── __init__.py       main(): runs the four stages
├── loop.py           the agent loop (tool use, max 10 rounds)
├── prompts.py        system prompt
├── tools.py          tool definitions, run_tool(), process_report() checks
├── dates.py          date and time arithmetic (relative dates, Paris time zone)
├── groups.py         your group per course (groups.json)
├── calendar_file.py  exams.ics
├── gcal.py           Google Calendar sync with the y/N confirmation
├── google_auth.py    OAuth login shared by Gmail and Calendar
└── mail/
    ├── fake.py       sample-email mailbox for tests and --fake
    └── gmail.py      Gmail mailbox (same interface)
```

`CLAUDE.md` holds the design rules, and `PROGRESS.md` is the step-by-step build log with what each step taught.

## Status and roadmap

- [x] Phase 1: find exams in email (sample emails, then real Gmail)
- [x] Phase 2: `.ics` file
- [x] Phase 3: Google Calendar with confirmation and duplicate check
- [ ] Phase 4: Moodle (built-in iCal export or Web Services API)
- [ ] Phase 5: morning scan with a notification (systemd user timer); it never adds events by itself
- [ ] v2: rooms, including surname ranges ("ABC – DEF → Amphi A4")

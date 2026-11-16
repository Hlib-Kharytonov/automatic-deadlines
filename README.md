# exam-agent

An LLM agent that reads my university email, finds exam announcements, and adds them to my calendar after I confirm.

## Why

French universities announce exams in free text, usually in Moodle emails:

- "L'examen aura lieu le jeudi 28 mai de 16h30 à 18h30 (Salles: B1, B2, 34A, 34B)."
- "…l'examen d'Algorithmique qui a lieu ce soir à 18h15"
- "Vous êtes convoqué(e) à l'épreuve finale… dans votre salle et créneau habituel."

Dates are absolute, relative ("ce soir", "ce jeudi"), or missing a time. Exams sit next to copy reviews, postponements and per-group slots. A regex breaks on the next new phrasing. A language model reads these well, but I don't trust it with date arithmetic or with my calendar, so each side does the job it is good at.

## How it works

The agent is a loop of about 60 lines (`loop.py`). The model gets four tools and asks for one. My code runs it and sends the result back. This repeats until the model calls `report_exams` with a valid answer, or for at most 10 rounds.

| Tool | Purpose |
|---|---|
| `search_emails`, `read_email` | Read-only access to the mailbox |
| `get_my_group(course, options)` | Asks me once per course which group I'm in, and saves the answer |
| `report_exams(exams)` | The final answer, with a strict schema. Code validates it and sends errors back. |

After the loop, plain code filters by my groups, writes an `.ics` file, and offers to add new events to Google Calendar.

A real run on the sample mailbox (the samples are from spring 2026, so every exam is past):

```
--- Round 1: stop_reason=tool_use, tokens in/out=2958/160
  Claude asks: search_emails({'query': 'partiel OR examen OR CC OR CC1 OR CC2 OR contrôle OR quiz OR quizz OR …'})
  Claude asks: search_emails({'query': 'contrôle continu'})
--- Round 2: stop_reason=tool_use, tokens in/out=4553/387
  Claude asks: read_email({'email_id': 'e1'})   … and e2, e3, e4, e6, e7, e8
--- Round 3: stop_reason=tool_use, tokens in/out=6954/707
  Claude asks: get_my_group({'course_code': 'UL2XX002', 'options': ['2', '4']})
  ? Which group are you in for UL2XX002?  Your group: 2
  Claude asks: get_my_group({'course_code': 'UL2IN013', 'options': ['1', '3']})
  ? Which group are you in for UL2IN013?  Your group: 2
--- Round 4: stop_reason=tool_use, tokens in/out=7767/1045
  Claude asks: report_exams(5 exams)

=== 5 exams for me (0 other-group slots hidden) ===
Thu 2026-03-12  18:15-20:15   UL2IN003   Examen Algorithmique 1  (past)
Tue 2026-04-14  10:45-11:45   UL2XX002   CC2 Cours fictif B  (past)
Tue 2026-04-21  10:45-12:15   UL2XX001   CC1 Cours fictif A  (past)
Thu 2026-05-07  time unknown  LU2LVAN2   Épreuve finale d'anglais LU2LVAN2  (past)
Thu 2026-05-28  16:30-18:30   UL2IN009   Examen Introduction aux bases de données relationnelles  (past)
```

The output is right for a group 2 student. But "0 other-group slots hidden" shows a problem: the model dropped the other groups' slots itself, so my code had nothing to filter. See Results.

## Design decisions

- **No agent framework.** I wanted to understand the loop itself: `stop_reason`, why the whole history is resent every round (the API is stateless), and how parallel tool calls come back.
- **The model extracts; code computes.** The model reports dates as written, such as day and month, or "thursday" + "this". Code takes the email's date from the mailbox (not from the model) and computes the real date, year, time zone, the default 2-hour length and duplicates. It also checks that "jeudi 28 mai" really is a Thursday.
- **Errors are feedback.** If any entry is invalid (an impossible date, "16h30" instead of "16:30", a group slot before my group is known), code rejects the whole report with one message that lists every problem, and the model fixes them all in the next round.
- **Least privilege, in layers.** Gmail is read-only (`gmail.readonly`). Calendar access is limited to calendars the app created (`calendar.app.created`). The model has no write tool, so text inside an email can't trigger a write. Code asks `[y/N]` before any calendar write, and a test checks that "no" makes zero API writes.
- **A fake mailbox with the same interface as Gmail.** I built and tested the loop on 8 sample emails first. Switching to Gmail changed no loop code.
- **Stable event IDs** (course + start time): re-running never duplicates an event, and an event I deleted isn't offered again.

## Hard cases

| Case (sample email) | Handling |
|---|---|
| No time: "dans votre salle et créneau habituel" (e2) | `time_unknown`: shown as a notice, never a calendar event |
| "ce soir à 18h15", no end time (e4) | The email's date; end = start + 2 h |
| "ce jeudi" in a Tuesday email (e3) | Code resolves it to that Thursday |
| Copy review in the same email as the exam (e1) | Prompt rule; never reported in 15 runs |
| Exam postponed from 14 to 21 April (e6) | Only the new date |
| Per-group slots (e7), a quiz for groups 1 and 3 only (e3) | Asks my group; code filters. The model also filters by itself (see Results). |
| "Examen de votre dossier de bourse" (e5) | Not an exam; never reported |
| "pas avant le 20 avril… rien n'est sûr" (e8) | No fixed date: not reported |
| Rooms assigned by surname range (e4) | **Not handled yet** |

## Results

How each step changed the output. These are single development runs, so they show direction, not accuracy:

| Step | Result (one run) |
|---|---|
| Bare loop, no system prompt | 2 of 6 exams, free text |
| System prompt: one rule per mistake seen | 6 of 6 exams, free text |
| `report_exams` + checks in code | 7 of 7 entries (one exam has two group slots). "16h30" was rejected and fixed in the next round. |
| Groups + end-to-end test | Test passed |

**The current version, run 10 times** on the 8 sample emails as a group 2 student:

- 65 of 70 expected entries matched exactly; 5 of 10 runs were perfect.
- No false positives (the scholarship email, the copy review, the old postponed date, the unfixed date) and no rejected reports.
- 4–5 rounds and about 29,000 input + 2,500 output tokens per run: about $0.004 with Claude Haiku 5.5.

All 5 misses are the same: the groups 1 and 3 quiz, dropped after `get_my_group` returned group 2. The prompt says to report every slot and let code filter, but the model filters by itself. In 5 more runs as a group 1 student, the quiz appeared every time, with the right date, but as `['1']` only.

So the student saw the right exams in all 15 runs, but a rule that lives only in the prompt isn't followed reliably. The single run marked "Test passed" above hid that; running it 10 times showed it. In an earlier 10-run batch, one run also placed "ce jeudi" a week late.

On my real inbox (one run), it found the one exam with a fixed date and ignored a partiel whose date wasn't set. The broad search hit its 20-result cap, and more than half the results were unrelated.

## Limitations and next steps

- **Don't tell the model my group.** It doesn't need it. Next: remove `get_my_group` from its tools and ask in code after the report, so the model can't filter.
- **Search recall:** at most 20 results, newest first, from the last 6 months, and the model isn't told when a list was cut off.
- **A small eval** (8 emails, exact match), so `pytest -m api` fails about half the time. Next: more anonymized real emails, per-field scoring.
- **No adversarial email** in the samples yet, even though the architecture is designed against injected instructions.
- **A moved exam** gets a new event, and the old one stays until I delete it.
- **Not built:** rooms, Moodle (iCal export or Web Services API), and a morning notification that never adds events by itself.

## How this was built

This was my first experience with agents. I wanted to understand the concept by building one, and to try every tool available along the way, including Claude Code (Anthropic's coding assistant). I wrote the first version of the agent loop and the plan for how the agent would use its tools. Claude Code wrote the rest, one phase at a time: the tools, validation, date logic, Gmail and Calendar code, tests and sample emails.

I directed the work and made the call at each decision point. A few decisions were my own, such as not reporting an exam until its date is fixed. Most were choices between options Claude laid out, such as read-only Gmail instead of storing my university password, or a separate calendar with one confirmation per batch. I tested each phase on my own inbox. `PROGRESS.md` logs every step and what it taught me.

## Run it

You need [uv](https://docs.astral.sh/uv/), which installs Python 3.14, and an Anthropic API key.

```sh
git clone <repo-url> && cd automatic-deadlines
uv sync
cp .env.example .env        # add ANTHROPIC_API_KEY
uv run pytest               # 59 offline tests, free
uv run exam-agent --fake    # the agent on the sample emails, no Google needed
uv run pytest -m api        # end-to-end against the expected exams, about $0.004
```

For your own Gmail and Google Calendar, see [docs/SETUP.md](docs/SETUP.md).

## Privacy

- The only real emails in the repo are 4 university announcements, with teacher names and the surname list removed. The other 4 samples are synthetic.
- Secrets live only in `.env`. OAuth tokens and the calendar ID are in `.secrets/`; saved groups are in `groups.json`. All of these are gitignored.
- The emails the model opens are sent to the Anthropic API.

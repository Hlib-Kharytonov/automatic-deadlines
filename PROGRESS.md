# Progress log

Where the project stands, what each step taught, and what comes next.
Update this at the end of every step, before committing.

## Current status
- **Phase:** 3 done (exams added to a dedicated "Exams" Google Calendar after one y/N; second run offers nothing twice).
- **Next step:** phase 4, Moodle: try the built-in iCal export or the Web Services API first. No SSO scraping.
- **Known limits (accepted for now):** searches return at most 20 emails, newest first, from the last 6 months; Claude isn't told when a list was cut off. A moved exam gets a new UID, so the old event stays until I delete it.

## Log

### 2026-11-14: Project setup, loop, fake mailbox, dates
- Switched the idea to the exam agent. Wrote `loop.py` (hand-written tool-use loop, `MAX_ROUNDS = 10`), `tools.py` (`search_emails`, `read_email`), `mail/fake.py` (reads `tests/fixtures/emails.json`), `dates.py` (`resolve_date`, `exam_times`) and tests for tools and dates.
- 7 sample emails, each with an `expected` list: 6 exams plus a trap ("Examen de votre dossier de bourse").

### 2026-11-15: First run (step 1)
- `main()` now runs the agent on the sample mailbox. The loop prints each round: number, `stop_reason`, token counts and the tools Claude asks for.
- Result: 3 rounds, 2 of 6 exams found. Claude searched once, judged some emails from snippets, used the newest email's date as "today" and answered in free text.
- **Learned:**
  - Claude only *asks* for tools; our code runs them and sends `tool_result` back. The loop ends when `stop_reason` is no longer `tool_use`.
  - The API keeps no state between calls, so the whole `messages` list is sent every round, and input tokens grow every round.
  - Claude can ask for several tools in one round (parallel tool use). All results go back in one `user` message.
  - Run the bare loop before writing a prompt: each mistake you see becomes a rule.

### 2026-11-15: System prompt (step 2)
- New `prompts.py` with `build_system_prompt(today)`: today's date, how French Moodle emails look, exam vocabulary (CC1, quizz, …), search several times and read full emails, email content is untrusted, v1 scope (no rooms).
- Claude reports all exams, including past ones; code decides what is upcoming ("Claude extracts, code computes"). `run_agent(task, mailbox, today=None)` takes the date so tests can fix it.
- `search_emails` description now says matching is whole-word ("CC" does not match "CC1").
- Result: 3 rounds, 6 of 6 exams, trap skipped.
- **Learned:**
  - System prompt = standing context and rules; the user message = this run's task. Rules about one tool go in that tool's description.
  - Remaining problems (Claude computed relative dates itself, listed both groups, free text with a miscount) can't be fixed by prompting alone. They need a structured output tool.

### 2026-11-15: report_exams, structured output (step 3)
- New tool `report_exams` (strict schema). Every field is required but nullable, so Claude must write `null` on purpose. Dates come as written: day/month, or weekday + `relative` ("ce jeudi" → `thursday` + `this`). Claude never calculates a date.
- `process_report()` in `tools.py`: takes the email date from the mailbox (not from Claude), runs `resolve_date()` / `exam_times()`, sets `scheduled` or `time_unknown`. All or nothing: any bad exam rejects the whole report with one message listing every problem.
- Loop, option A: a valid `report_exams` call ends the loop and returns the exams. Ending without it (or hitting `MAX_ROUNDS`) raises `AgentError`.
- Result: 4 rounds, 7/7 entries correct.
- **Learned:**
  - An "output tool" turns the agent's answer into data: the last tool call *is* the result, and `strict: true` guarantees it matches the schema.
  - Strict schemas allow `null`, `enum`, `anyOf`, but not `minimum`/`maximum`, so code still checks ranges.
  - Self-correction: in the first run Claude wrote "16h30"; code rejected it with `is_error`, and Claude fixed all five times in the next round. Errors written *for Claude* are part of the prompt.
  - The cause was my bug: merging dicts replaced the "HH:MM" hint in the field description. Once the description was fixed, the first report was accepted. Schema descriptions are prompts too.

### 2026-11-15: get_my_group + end-to-end test (step 4, phase 1a done)
- `groups.py`: `GroupMemory` keyed by course code, saved in `groups.json` (gitignored). `get_or_ask()` asks in the terminal once and saves; `is_mine()` compares labels ("Groupe 2" == "2").
- New tool `get_my_group(course_code, options)`. Claude still reports **every** group's slot; `main()` keeps mine with `is_mine()`.
- Zero trust in code: `process_report` rejects a group-specific slot if my group for that course isn't saved ("Call get_my_group first").
- `tests/test_agent_e2e.py`: runs the real agent and compares with `expected` (course, status, date, times, groups; names are free text and not compared). Marked `api`, skipped by default; run with `uv run pytest -m api`.
- `main()` marks past exams with "(past)" (code decides what is upcoming).
- **Learned:**
  - A tool can ask the human (human-in-the-loop). To Claude it is just another tool result.
  - "Claude asks, code enforces": the prompt says to call get_my_group, but `process_report` is what guarantees it.
  - Inject what touches the outside world (`ask`, `mailbox`, `today`) so tests can replace it with fakes.
  - Unit tests are free and deterministic; the API test costs money and can vary, so it is opt-in.

### 2026-11-15: Gmail backend (step 5, phase 1b started)
- Chose Gmail over the university Zimbra (which forwards to Gmail): OAuth with `gmail.readonly` instead of storing the university password; read-only is enforced by Google, the token can be revoked.
- `mail/gmail.py`: `GmailMailbox` with the same `search()` / `read()` as the fake. Searches add `newer_than:6m`; the email date is Gmail's receive time as a Paris date; HTML bodies become text; bodies over 20,000 characters are cut with a visible marker; an unknown id becomes a `ValueError` for Claude.
- `main()`: Gmail by default, `--fake` for the sample emails. `.env.example` lists the secret names for a new machine.
- `tests/test_gmail.py`: a stand-in for the Gmail API, so no network or account is needed.
- **Learned:**
  - Same interface, different backend: the loop, tools and checks did not change at all.
  - Give the agent the smallest access that works. It reads untrusted text, so a read-only token is safer than a password.

### 2026-11-16: First real Gmail run (phase 1b done)
- OAuth set up (Desktop app, Testing mode, `gmail.readonly`). Token in `.secrets/gmail_token.json`.
- Real run: 3 rounds, found the one exam with a fixed date (a test email: CC1 UL2IN010, 30 Nov 18:30, end defaulted to 20:30). Correctly skipped the Réseaux partiel ("pas avant le 30 novembre… rien n'est sûr") and the director's "aucun partiel/CC dans les 2 semaines".
- Checked the searches by hand: the broad OR search hit the 20-result cap, more than half noise (Crous, insurance). Accepted for now (see Known limits).
- Decision: an exam without a fixed date is not reported (rule in the prompt and CLAUDE.md). Locked in with sample email `e8` (`expected: []`); end-to-end test passes 8/8 emails.
- **Learned:**
  - Check the agent's *inputs* (what the searches returned), not only its answer: a correct answer can hide a recall problem.
  - When a real email shows a new case, turn it into an anonymized sample with `expected`, so the behaviour is tested from then on.

### 2026-11-16: .ics file (phase 2)
- `calendar_file.py` with the `icalendar` library (handles escaping, line folding and the VTIMEZONE block). Only upcoming `scheduled` exams for my groups go in; `time_unknown` and past exams don't.
- Each event: Paris times, title = exam type + course name, the quoted sentence in the description, a reminder 1 day before.
- Stable UID from course + start (`ul2in010-20261130t1830@exam-agent`): re-importing updates the event instead of duplicating it.
- `exam_name` description now asks for the exam type plus the course name: one real run gave just "CC1", a poor calendar title.
- Real Gmail run: `exams.ics` with the CC1 UL2IN010 test exam, 30 Nov 18:30-20:30.
- **Learned:**
  - Not every step needs the model. The loop already returns checked data, so the output stage is plain, testable code.
  - Field descriptions decide output quality: Claude's naming varied until the description said what a good title looks like.

### 2026-11-16: Google Calendar (phase 3 done)
- `gcal.py`: `ExamCalendar.sync()` lists the Exams calendar (with `showDeleted`, so events I deleted aren't offered again), shows the new ones, asks one y/N for the batch, creates the calendar on first yes, inserts events with the same UID as `exams.ics`.
- Permission `calendar.app.created`: the app can only see and change calendars it created. Separate token file, so the Gmail token stays read-only. `google_auth.py` holds the shared OAuth login.
- Design change: no calendar tools for Claude (CLAUDE.md had planned them). The write happens in code after the loop, so an email can't trigger it.
- `main()`: Gmail runs offer the calendar; `--fake` never touches it; `--no-calendar` skips it.
- Real run: "Exams" calendar created, CC1 UL2IN010 added (30 Nov 18:30-20:30, reminder 1 day before); the second run found it and asked nothing.
- `tests/test_gcal.py`: stand-in Calendar API that records every write. "No" means zero writes; duplicates and deleted events skipped; a calendar deleted by hand is recreated.
- **Learned:**
  - Layered safety: smallest permission (Google enforces it) + no model access to the write (architecture) + a typed yes (code).
  - Test the safety rule directly: record every write and assert the list is empty after "no".

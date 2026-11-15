# Progress log

Where the project stands, what each step taught, and what comes next.
Update this at the end of every step, before committing.

## Current status
- **Phase:** 1a (sample emails → print exams in the terminal)
- **Works:** the tool-use loop with `search_emails` and `read_email` over the fake mailbox, plus a system prompt. It finds all 6 sample exams and skips the scholarship email.
- **Next step:** the `report_exams` tool, so Claude returns structured fields (including relative dates as weekday + "relative") instead of free text. Then `dates.py` turns them into real dates. Show the schema before writing it.
- **After that:** `get_my_group` + `groups.json`, end-to-end test against `expected` in the sample emails, then phase 1b (Gmail).

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

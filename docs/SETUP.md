# Setup

How to run exam-agent on your own Gmail and Google Calendar. For what the project does and why, see the [README](../README.md).

## Requirements

- Linux or macOS
- [uv](https://docs.astral.sh/uv/), which also installs the right Python version (3.14) for you
- An [Anthropic API key](https://console.anthropic.com/). One run costs well under one cent with the default model (Claude Haiku 5.5).
- A Google account whose Gmail receives your university mail. If your university uses its own mailbox (Zimbra, Outlook), turn on automatic forwarding to Gmail first.

## 1. Get the code

```sh
git clone <repo-url>
cd automatic-deadlines
uv sync
```

If you don't have uv yet: `curl -LsSf https://astral.sh/uv/install.sh | sh`, then open a new terminal.

## 2. Create the `.env` file

```sh
cp .env.example .env
```

Paste your Anthropic API key after `ANTHROPIC_API_KEY=`. The two Google values come from the next step.

`.env` is gitignored. Never commit it.

## 3. Set up Google access (once, about 15 minutes)

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

## 4. First run

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

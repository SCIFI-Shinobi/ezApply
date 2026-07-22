# Job/Scholarship Matching Bot

ezApply is the Telegram version of ApplyFlow. It runs without Claude: resume parsing is deterministic, matching uses local embeddings plus hardcoded keyword scoring, and channels/profile data can be managed from Telegram.

Two processes run together:

1. `bot.py` - the Telegram bot you talk to for resume upload, profile edits, and channel commands.
2. `userbot/userbot.py` - a Telethon client logged in as your own Telegram account. It reads new posts in tracked channels, matches them against your profile, and sends alerts through the bot.

## 1. Set Up Accounts And Keys

- Bot token: talk to [@BotFather](https://t.me/BotFather) on Telegram, create a bot, and copy the token.
- Your Telegram user ID: message [@userinfobot](https://t.me/userinfobot), it replies with your numeric ID.
- Telethon API ID/hash: go to https://my.telegram.org, create an app, and copy the API ID/hash.
- Database URL: your Supabase Postgres connection string.

Environment variables:

```text
BOT_TOKEN=
YOUR_TELEGRAM_USER_ID=
TG_API_ID=
TG_API_HASH=
TG_SESSION_STRING=
DATABASE_URL=
MATCH_THRESHOLD=0.55
KEYWORD_MATCH_THRESHOLD=50
APPLYFLOW_PROFILE_PATH=
```

`APPLYFLOW_PROFILE_PATH` is optional. By default ezApply looks for `../ApplyFlow/profile.json`.

## 2. Create The DB Tables

Run `db/schema.sql` once against Supabase.

```bash
psql "$DATABASE_URL" -f db/schema.sql
```

## 3. Generate Your Telethon Session

```bash
pip install -r requirements.txt
python userbot/generate_session.py
```

Copy the printed session string into `TG_SESSION_STRING`.

## 4. Join The Channels

Telethon reads channels your personal Telegram account has joined. Open Telegram and join every channel you want tracked.

Default monitored channels:

```text
@OHUB4AllET - scholarship
@Tegegnpathway - scholarship
@ethio_job_vacancy1 - job
@harmeejobs - job
@jobs_in_ethio - job
```

## 5. Run The Telegram Bot

```bash
python bot.py
```

Useful commands:

```text
/start
/channels
/syncchannels
/addchannel https://t.me/harmeejobs job
/addchannel someScholarshipChannel scholarship
/profile
/profilejson
/setprofile skills Python, FastAPI, React, PostgreSQL
/setprofile target_roles Software Engineering Intern, Backend Developer Intern
/setprofile location_preference Remote, Ethiopia, East Africa
/reloadapplyflowprofile
/companies 25
/draftcompany 10up
/draftjob Backend Intern | Paste the job description here
/draftremote 100
/findemail 10up
/findremoteemails 25
```

## 6. Upload Or Edit Your Profile

Send your `.pdf` or `.docx` resume to the bot. It extracts text locally, combines it with ApplyFlow profile defaults when available, builds the matching summary, embeds it, and stores it.

Use `/profilejson` to inspect the parsed profile and `/setprofile` to edit the most important fields without touching the database.

## 7. Run The Userbot

```bash
python userbot/userbot.py
```

Whenever a tracked channel posts something, ezApply embeds the post, applies hardcoded matching rules, compares it against your profile embedding, and sends you a Telegram alert when it passes the threshold.

## Internship Outreach Drafts

To generate polite internship inquiry drafts from ApplyFlow's remote company list:

```bash
python outreach/internship_outreach.py --limit 50
```

This creates `outreach/internship_outreach_drafts.csv` with company names, blank email fields, subjects, and message bodies. Fill in verified company email addresses and review before sending anything.

The Telegram bot can also prepare drafts:

```text
/companies 25
/draftcompany 37signals
/draftjob Python Backend Intern | Paste the full job post here
/draftremote 100
/findemail 10up
/findremoteemails 25
```

`/draftremote` sends you a CSV generated from `../ApplyFlow/remote_companies.json`. If `outreach/company_contacts.json` exists, it fills the email column with the best discovered or guessed contact for each company.

To build a company-to-email dictionary:

```bash
python outreach/company_contacts.py --limit 25
python outreach/company_contacts.py --company 10up
```

This writes `outreach/company_contacts.json`. Entries include `verified_emails` when found on company pages, `possible_emails` guessed from the domain, source URLs, and a confidence label. Use guessed emails carefully.

## Deployment Notes

Free-tier Render web services sleep after idle time, which breaks polling and the live Telethon connection. Railway or a paid background worker is better for 24/7 monitoring.

Tune `MATCH_THRESHOLD` and `KEYWORD_MATCH_THRESHOLD` after a few days of real alerts. Raise them if matches are too broad; lower them if ezApply misses good internships.

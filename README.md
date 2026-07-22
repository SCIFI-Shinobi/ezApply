# ezApply — Telegram Job & Scholarship Alert Bot

> **You join Telegram job channels. ezApply watches them for you and pings you the moment a match appears.**

ezApply runs 24/7 on a free cloud server. It reads your resume once, builds an AI profile from it, then monitors every Telegram job/scholarship channel you're in. When a new post matches your skills and target roles, it sends you a private Telegram message with a direct link so you can apply immediately.

---

## How It Works

```
Your Telegram account
    → joins job/scholarship channels
         → ezApply Userbot reads every new post
              → AI embedding + keyword rules check if it matches your profile
                   → If it matches: Bot sends you a private alert with a link
```

That's the whole point. Everything else is optional.

---

## Quick Start (5 steps)

### Step 1 — Get your Telegram Bot token
Talk to [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token.

### Step 2 — Get your Supabase database URL
1. Go to [supabase.com](https://supabase.com) → create a free project.
2. Go to **Project Settings → Database → Connection string → URI** → copy it.
3. Replace `[YOUR-PASSWORD]` with your DB password.

> **Important for Render (free tier):** Supabase's default connection string uses IPv6.
> Render's free tier only supports IPv4. In Supabase, go to
> **Project Settings → Database → Connection string** and check the
> **"Use connection pooler"** box, then copy the pooler URL (port 6543).
> That URL is IPv4-compatible and will work on Render free.

### Step 3 — Generate your Userbot session string (run this on your own PC once)
```bash
git clone https://github.com/your-username/ezApply
cd ezApply
pip install -r requirements.txt

# Set these two temporarily in your terminal:
set TG_API_ID=your_api_id        # from https://my.telegram.org
set TG_API_HASH=your_api_hash

python userbot/generate_session.py
```
Enter your phone number and the code Telegram sends you. Copy the long string it prints — that's your `TG_SESSION_STRING`.

> Get `TG_API_ID` and `TG_API_HASH` from [my.telegram.org](https://my.telegram.org) → API development tools → Create app.

### Step 4 — Deploy to Render (free)
1. Fork this repo and connect it to [render.com](https://render.com).
2. Create a new **Web Service** pointing to this repo.
3. Set the following **Environment Variables**:

| Variable | What it is |
|---|---|
| `BOT_TOKEN` | From BotFather |
| `YOUR_TELEGRAM_USER_ID` | Your numeric Telegram ID (get it from [@userinfobot](https://t.me/userinfobot)) |
| `DATABASE_URL` | Supabase pooler connection string (IPv4, port 6543) |
| `TG_API_ID` | From my.telegram.org |
| `TG_API_HASH` | From my.telegram.org |
| `TG_SESSION_STRING` | The string you generated in Step 3 |

4. Deploy. The bot and userbot start automatically.

### Step 5 — Join channels and upload your resume
1. **Join** the Telegram job/scholarship channels you want monitored from your personal account.
2. Open your bot on Telegram → send `/start`.
3. Upload your `.pdf` or `.docx` resume directly in the chat.
4. The bot parses it, builds your AI profile, and starts matching against every channel post from that moment on.

---

## Managing Channels

The userbot can only monitor channels that **your personal Telegram account is already a member of**. Join a channel first, then register it with the bot:

```
/channels                                   — list currently tracked channels
/addchannel @ethiojobs job                  — track a new job channel
/addchannel https://t.me/scholarships scholarship  — track a scholarship channel
/syncchannels                               — re-sync default + any extra channels
```

**Default channels already seeded on startup:**
- `@OHUB4AllET` (scholarships)
- `@Tegegnpathway` (scholarships)
- `@ethio_job_vacancy1` (jobs)
- `@harmeejobs` (jobs)
- `@jobs_in_ethio` (jobs)

---

## Managing Your Profile

```
(upload .pdf or .docx)    — parse resume and build/update your profile
/profile                  — view your current profile summary
/profilejson              — view the full raw profile JSON
/setprofile skills Python, FastAPI, React    — manually edit a field
/setprofile target_roles Software Engineer Intern, Backend Developer
/reloadapplyflowprofile   — reload from ApplyFlow/profile.json if you use ApplyFlow
```

---

## Tuning Match Sensitivity

Set these in your Render environment variables (defaults are fine to start):

| Variable | Default | Description |
|---|---|---|
| `MATCH_THRESHOLD` | `0.55` | Cosine similarity (0–1). Raise if getting too many false alerts. |
| `KEYWORD_MATCH_THRESHOLD` | `50` | Rule-based score bonus. Lower = more sensitive. |

---

## Email Outreach (Optional — Separate Feature)

ezApply also includes a cold email outreach module, completely independent of the channel monitoring. If you want the bot to send internship inquiry emails on your behalf:

1. Add `EMAIL_FROM` (your Gmail address) and `EMAIL_PASSWORD` (a 16-character [Google App Password](https://support.google.com/accounts/answer/185833)) to your Render environment variables.
2. Use these commands:

```
/companies [limit]             — list companies from ApplyFlow/remote_companies.json
/draftcompany <company>        — preview a cold internship email before sending
/sendemail <company>           — send an internship inquiry email to one company
/sendremoteemails [limit]      — bulk-send to all companies with a known email
/draftjob <company> | <job>    — draft a tailored application email from a job posting
/findemail <company>           — discover possible contact emails for a company
/findremoteemails [limit]      — build a company → email contact list
/draftremote [limit]           — export a CSV of outreach drafts
```

> This feature reads from `ApplyFlow/remote_companies.json` and `ApplyFlow/company_contacts.json`.
> It works independently and does not affect channel monitoring.

---

## Architecture

```
bot.py (entry point)
├── bot/bot.py          — Telegram Bot (commands, resume upload, profile management)
├── userbot/userbot.py  — Telethon Userbot (channel listener, match engine, alerts)
├── db/db.py            — PostgreSQL (Supabase) — profiles, channels, posts, matches
├── matcher/matcher.py  — Sentence-Transformers embeddings + keyword rules
├── parser/             — Resume PDF/DOCX text extraction + LLM profile parsing
├── config/defaults.py  — Default channels, default profile, normalization helpers
└── outreach/           — (Optional) Cold email drafting and sending
```

---

## Troubleshooting

**Bot crashes with `psycopg2.OperationalError: Network is unreachable`**
→ Your `DATABASE_URL` is using an IPv6 address that Render free tier can't reach.
→ In Supabase: Project Settings → Database → enable **Connection pooler** → copy the pooler URL (port 6543). Use that as your `DATABASE_URL`.

**Userbot starts but I'm not getting any alerts**
→ Make sure your personal Telegram account (the one you used for `generate_session.py`) is actually **joined** to the channels you added with `/addchannel`.
→ Check that `TG_SESSION_STRING` is set correctly in Render — it should be a very long string.
→ Verify your profile is saved: send `/profile` to your bot.

**`No TG_SESSION_STRING set` in logs**
→ Run `python userbot/generate_session.py` on your local machine and add the output to Render's environment variables.

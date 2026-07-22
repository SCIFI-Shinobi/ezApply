import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import telebot

from config.defaults import DEFAULT_CHANNELS, load_applyflow_channels, load_applyflow_profile, normalize_profile, parse_channel_username
from db.db import (
    add_channel,
    ensure_channels,
    get_latest_profile,
    list_channels,
    save_profile,
    update_latest_profile,
    init_db,
)
from matcher.matcher import embed
from outreach.company_contacts import (
    DEFAULT_CONTACTS_PATH,
    best_email_for_company,
    discover_company_contact,
    discover_contacts,
    load_contacts,
    save_contacts,
)
from outreach.internship_outreach import (
    DEFAULT_COMPANIES_PATH,
    DEFAULT_OUTPUT_PATH,
    build_email,
    build_job_email,
    bulk_send_outreach,
    generate_company_drafts,
    load_companies,
    send_company_outreach,
    smtp_configured,
)
from parser.resume_parser import extract_text_from_file, parse_resume_to_profile

BOT_TOKEN = os.environ.get("BOT_TOKEN")
YOUR_ID = os.environ.get("YOUR_TELEGRAM_USER_ID")

bot = telebot.TeleBot(BOT_TOKEN)


def is_owner(message) -> bool:
    """Only you can set your profile / manage channels."""
    return YOUR_ID and str(message.from_user.id) == str(YOUR_ID)


@bot.message_handler(commands=["start"])
def send_welcome(message):
    _seed_channels()
    bot.reply_to(
        message,
        "Hey! I'm your job/scholarship matching bot.\n\n"
        "📄 Resume\n"
        "- Send me your .pdf or .docx resume to build/update your profile\n"
        "- /profile - see your current profile summary\n"
        "- /profilejson - see the raw profile JSON\n"
        "- /setprofile <field> <value> - edit name, skills, target_roles, location_preference, summary_for_matching\n"
        "- /reloadapplyflowprofile - reload profile from ApplyFlow/profile.json\n\n"
        "📡 Channels\n"
        "- /channels - list tracked channels\n"
        "- /addchannel <username-or-link> [job|scholarship] - track a new channel\n"
        "- /syncchannels - restore default channels + ApplyFlow channels\n\n"
        "📧 Email Outreach\n"
        "- /companies [limit] - list remote companies from ApplyFlow\n"
        "- /draftcompany <company> - preview a cold internship email\n"
        "- /sendemail <company> - actually SEND the internship email to a company\n"
        "- /sendremoteemails [limit] - bulk-send emails to all companies with a known address\n"
        "- /draftjob <company-or-role> | <job text> - draft a tailored application email\n"
        "- /draftremote [limit] - create a CSV of outreach drafts\n"
        "- /findemail <company> - discover possible company emails\n"
        "- /findremoteemails [limit] - build company_contacts.json",
    )


def _seed_channels():
    """Seed both hardcoded defaults and any ApplyFlow-defined channels."""
    init_db()
    ensure_channels(DEFAULT_CHANNELS)
    extra = load_applyflow_channels()
    if extra:
        ensure_channels(extra)


@bot.message_handler(content_types=["document"])
def handle_resume(message):
    if not is_owner(message):
        bot.reply_to(message, "This bot is configured for a specific user only.")
        return

    doc = message.document
    file_name = doc.file_name.lower()
    if not (file_name.endswith(".pdf") or file_name.endswith(".docx")):
        bot.reply_to(message, "Please send a .pdf or .docx resume.")
        return

    bot.reply_to(message, "Got it - reading your resume...")

    file_info = bot.get_file(doc.file_id)
    downloaded = bot.download_file(file_info.file_path)

    suffix = ".pdf" if file_name.endswith(".pdf") else ".docx"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(downloaded)
        tmp_path = tmp.name

    try:
        resume_text = extract_text_from_file(tmp_path)
        if not resume_text.strip():
            bot.reply_to(message, "Couldn't extract any text. Is the PDF scanned/image-based?")
            return

        bot.send_message(message.chat.id, "Extracting structured profile locally...")
        profile_json = parse_resume_to_profile(resume_text)

        bot.send_message(message.chat.id, "Building matching embedding...")
        profile_embedding = embed(profile_json["summary_for_matching"])

        save_profile(resume_text, profile_json, profile_embedding)

        roles = ", ".join(profile_json.get("target_roles", []))
        bot.send_message(
            message.chat.id,
            f"Profile saved.\nTarget roles: {roles}\n\n"
            "I'll now match new channel posts against this profile.",
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"Something went wrong parsing that resume: {e}")
    finally:
        os.remove(tmp_path)


@bot.message_handler(commands=["addchannel"])
def handle_addchannel(message):
    if not is_owner(message):
        return
    parts = message.text.split()
    if len(parts) not in (2, 3):
        bot.reply_to(message, "Usage: /addchannel <channel_username_or_link> [job|scholarship]")
        return
    kind = parts[2] if len(parts) == 3 else "job"
    if kind not in ("job", "scholarship"):
        bot.reply_to(message, "Kind must be job or scholarship.")
        return
    username = parse_channel_username(parts[1])
    if not username:
        bot.reply_to(message, "I couldn't understand that channel. Try a @username or https://t.me/name link.")
        return
    add_channel(username, kind)
    bot.reply_to(
        message,
        f"Added @{username} as a '{kind}' channel.\n"
        "Remember: your Telethon userbot account must also JOIN this channel "
        "from your own Telegram account so it can read new posts.",
    )


@bot.message_handler(commands=["channels"])
def handle_list_channels(message):
    if not is_owner(message):
        return
    _seed_channels()
    channels = list_channels()
    if not channels:
        bot.reply_to(message, "No channels tracked yet. Use /addchannel <username> job|scholarship")
        return
    lines = [f"@{c['username']} - {c['kind']}" for c in channels]
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["syncchannels"])
def handle_syncchannels(message):
    if not is_owner(message):
        return
    _seed_channels()
    channels = list_channels()
    lines = [f"@{c['username']} - {c['kind']}" for c in channels]
    bot.reply_to(message, "Synced default + ApplyFlow channels:\n" + "\n".join(lines))


@bot.message_handler(commands=["profile"])
def handle_profile(message):
    if not is_owner(message):
        return

    p = get_latest_profile()
    if not p:
        bot.reply_to(message, "No profile saved yet. Send me your resume first or use /reloadapplyflowprofile.")
        return
    ej = _profile_from_row(p)
    bot.reply_to(
        message,
        f"Name: {ej.get('name', '')}\n"
        f"Target roles: {', '.join(ej.get('target_roles', []))}\n"
        f"Skills: {', '.join(ej.get('skills', [])[:12])}\n"
        f"Location pref: {', '.join(ej.get('location_preference', []))}",
    )


@bot.message_handler(commands=["profilejson"])
def handle_profile_json(message):
    if not is_owner(message):
        return
    p = get_latest_profile()
    if not p:
        bot.reply_to(message, "No profile saved yet. Send a resume or use /reloadapplyflowprofile.")
        return
    payload = json.dumps(_profile_from_row(p), indent=2, ensure_ascii=True)
    for chunk in _telegram_chunks(payload):
        bot.send_message(message.chat.id, f"```json\n{chunk}\n```", parse_mode="Markdown")


@bot.message_handler(commands=["setprofile"])
def handle_setprofile(message):
    if not is_owner(message):
        return
    _, _, rest = message.text.partition(" ")
    field, _, value = rest.partition(" ")
    field = field.strip()
    value = value.strip()
    editable_fields = {"name", "skills", "target_roles", "location_preference", "summary_for_matching"}
    if field not in editable_fields or not value:
        bot.reply_to(
            message,
            "Usage: /setprofile <field> <value>\n"
            "Fields: name, skills, target_roles, location_preference, summary_for_matching\n"
            "For list fields, separate values with commas.",
        )
        return

    profile = _latest_or_default_profile()
    if field in {"skills", "target_roles", "location_preference"}:
        profile[field] = [item.strip() for item in value.split(",") if item.strip()]
    else:
        profile[field] = value
    profile = normalize_profile(profile)
    profile_embedding = embed(profile["summary_for_matching"])
    update_latest_profile(profile, profile_embedding)
    bot.reply_to(message, f"Updated {field} and rebuilt the matching embedding.")


@bot.message_handler(commands=["reloadapplyflowprofile"])
def handle_reload_applyflow_profile(message):
    if not is_owner(message):
        return
    profile = load_applyflow_profile()
    if not profile:
        bot.reply_to(message, "I couldn't find ApplyFlow/profile.json. Send a resume or edit with /setprofile.")
        return
    profile_embedding = embed(profile["summary_for_matching"])
    update_latest_profile(profile, profile_embedding)
    bot.reply_to(message, "Reloaded profile from ApplyFlow/profile.json and rebuilt the matching embedding.")


@bot.message_handler(commands=["companies"])
def handle_companies(message):
    if not is_owner(message):
        return
    limit = _parse_limit(message.text, default=25, maximum=100)
    try:
        companies = load_companies(DEFAULT_COMPANIES_PATH)
    except Exception as e:
        bot.reply_to(message, f"I couldn't read ApplyFlow remote_companies.json: {e}")
        return
    shown = companies[:limit]
    bot.reply_to(message, f"Showing {len(shown)} of {len(companies)} companies:\n" + "\n".join(shown))


@bot.message_handler(commands=["draftcompany"])
def handle_draft_company(message):
    if not is_owner(message):
        return
    _, _, company = message.text.partition(" ")
    company = company.strip()
    if not company:
        bot.reply_to(message, "Usage: /draftcompany <company name>")
        return
    profile = _latest_or_default_profile()
    subject = "Internship inquiry - Computer Engineering graduate"
    best_email = best_email_for_company(company)
    body = build_email(company, profile)
    prefix = f"Best email: {best_email or 'not found yet'}\n\n"
    _send_draft(message.chat.id, subject, prefix + body)


@bot.message_handler(commands=["draftjob"])
def handle_draft_job(message):
    if not is_owner(message):
        return
    _, _, payload = message.text.partition(" ")
    company_or_role, sep, job_text = payload.partition("|")
    if not sep or not job_text.strip():
        bot.reply_to(
            message,
            "Usage: /draftjob <company-or-role> | <paste job description or Telegram post text>",
        )
        return
    profile = _latest_or_default_profile()
    subject, body = build_job_email(company_or_role.strip(), job_text.strip(), profile)
    _send_draft(message.chat.id, subject, body)


@bot.message_handler(commands=["draftremote"])
def handle_draft_remote(message):
    if not is_owner(message):
        return
    limit = _parse_limit(message.text, default=50, maximum=500)
    output = DEFAULT_OUTPUT_PATH
    try:
        generate_company_drafts(limit=limit, output_path=output)
    except Exception as e:
        bot.reply_to(message, f"I couldn't generate the outreach CSV: {e}")
        return
    with output.open("rb") as f:
        bot.send_document(
            message.chat.id,
            f,
            visible_file_name=Path(output).name,
            caption=(
                f"Prepared {limit} outreach drafts from ApplyFlow companies.\n"
                "Email fields use discovered or guessed contacts when available. Review before sending."
            ),
        )


@bot.message_handler(commands=["sendemail"])
def handle_send_email(message):
    if not is_owner(message):
        return
    _, _, company = message.text.partition(" ")
    company = company.strip()
    if not company:
        bot.reply_to(
            message,
            "Usage: /sendemail <company name>\n"
            "Example: /sendemail Andela\n\n"
            "Tip: run /findemail <company> first to make sure an email address is known.",
        )
        return
    if not smtp_configured():
        bot.reply_to(
            message,
            "⚠️ Email sending is not configured.\n\n"
            "Add these to your Render environment variables:\n"
            "  EMAIL_FROM=your_gmail@gmail.com\n"
            "  EMAIL_PASSWORD=your_gmail_app_password\n\n"
            "(Use a Gmail App Password, not your main password.)\n\n"
            "Then try again. Falling back to showing the draft:",
        )
        profile = _latest_or_default_profile()
        from outreach.internship_outreach import SUBJECT
        body = build_email(company, profile)
        _send_draft(message.chat.id, SUBJECT, body)
        return
    bot.reply_to(message, f"Sending internship inquiry to {company}...")
    ok, email_used, err = send_company_outreach(company)
    if ok:
        bot.send_message(
            message.chat.id,
            f"✅ Email sent to {company} at {email_used}\n\n"
            "I politely asked if they have an internship, trainee, or unpaid internship opportunity.",
        )
    else:
        bot.send_message(
            message.chat.id,
            f"❌ Failed to send email to {company}.\n\nReason: {err}\n\n"
            "Tip: if no email was found, run /findemail <company> first.",
        )


@bot.message_handler(commands=["sendremoteemails"])
def handle_send_remote_emails(message):
    if not is_owner(message):
        return
    limit = _parse_limit(message.text, default=50, maximum=500)
    if not smtp_configured():
        bot.reply_to(
            message,
            "⚠️ Email sending is not configured.\n\n"
            "Add these to your Render environment variables:\n"
            "  EMAIL_FROM=your_gmail@gmail.com\n"
            "  EMAIL_PASSWORD=your_gmail_app_password\n\n"
            "Use /draftremote to get a CSV of drafts you can send manually instead.",
        )
        return
    bot.reply_to(
        message,
        f"📧 Sending internship inquiry emails to up to {limit} companies that have a known email address.\n"
        "This may take a few minutes — I'll report back when done.",
    )
    sent_ok = 0
    sent_fail = 0
    fail_lines = []

    def _progress(i, total, company, ok, email_used, err):
        nonlocal sent_ok, sent_fail
        if ok:
            sent_ok += 1
        else:
            sent_fail += 1
            fail_lines.append(f"{company}: {err}")
        # Send a progress update every 10 companies
        if i % 10 == 0 or i == total:
            bot.send_message(
                message.chat.id,
                f"Progress: {i}/{total} — ✅ {sent_ok} sent, ❌ {sent_fail} failed",
            )

    try:
        bulk_send_outreach(limit=limit, progress_callback=_progress)
    except Exception as e:
        bot.send_message(message.chat.id, f"Bulk send stopped early: {e}")
        return
    summary = (
        f"📬 Done! Sent {sent_ok} emails, {sent_fail} failed.\n"
    )
    if fail_lines:
        summary += "\nFailed:\n" + "\n".join(fail_lines[:20])
    bot.send_message(message.chat.id, summary)


@bot.message_handler(commands=["findemail"])
def handle_find_email(message):
    if not is_owner(message):
        return
    _, _, company = message.text.partition(" ")
    company = company.strip()
    if not company:
        bot.reply_to(message, "Usage: /findemail <company name>")
        return
    bot.reply_to(message, f"Searching possible emails for {company}...")
    try:
        result = discover_company_contact(company)
        contacts = load_contacts()
        contacts[company] = {
            "company": result.company,
            "domain": result.domain,
            "verified_emails": result.verified_emails,
            "possible_emails": result.possible_emails,
            "sources": result.sources,
            "confidence": result.confidence,
            "notes": result.notes,
        }
        save_contacts(contacts)
    except Exception as e:
        bot.reply_to(message, f"I couldn't search contacts for {company}: {e}")
        return
    bot.reply_to(message, _format_contact_result(contacts[company]))


@bot.message_handler(commands=["findremoteemails"])
def handle_find_remote_emails(message):
    if not is_owner(message):
        return
    limit = _parse_limit(message.text, default=25, maximum=300)
    bot.reply_to(message, f"Searching contacts for the first {limit} ApplyFlow companies. This can take a bit.")
    try:
        output = discover_contacts(limit=limit, output_path=DEFAULT_CONTACTS_PATH)
    except Exception as e:
        bot.reply_to(message, f"I couldn't build the contact dictionary: {e}")
        return
    with output.open("rb") as f:
        bot.send_document(
            message.chat.id,
            f,
            visible_file_name=Path(output).name,
            caption="Built company-to-email contact dictionary. Treat guessed emails as unverified.",
        )


def _profile_from_row(row) -> dict:
    extracted = row["extracted_json"]
    return extracted if isinstance(extracted, dict) else json.loads(extracted)


def _latest_or_default_profile() -> dict:
    p = get_latest_profile()
    if p:
        return dict(_profile_from_row(p))
    return load_applyflow_profile() or normalize_profile({})


def _telegram_chunks(text: str, limit: int = 3500):
    for start in range(0, len(text), limit):
        yield text[start : start + limit]


def _send_draft(chat_id, subject: str, body: str):
    message = f"Subject: {subject}\n\n{body}"
    for chunk in _telegram_chunks(message):
        bot.send_message(chat_id, chunk)


def _parse_limit(text: str, default: int, maximum: int) -> int:
    parts = text.split()
    if len(parts) < 2:
        return default
    try:
        return max(1, min(maximum, int(parts[1])))
    except ValueError:
        return default


def _format_contact_result(result: dict) -> str:
    verified = result.get("verified_emails") or []
    possible = result.get("possible_emails") or []
    sources = result.get("sources") or []
    lines = [
        f"Company: {result.get('company', '')}",
        f"Domain: {result.get('domain') or 'unknown'}",
        f"Confidence: {result.get('confidence', 'unknown')}",
        f"Verified emails: {', '.join(verified) if verified else 'none found'}",
        f"Possible emails: {', '.join(possible[:6]) if possible else 'none'}",
    ]
    if sources:
        lines.append("Sources: " + ", ".join(sources[:3]))
    lines.append(result.get("notes", ""))
    return "\n".join(lines)


def notify(chat_id: str, text: str):
    """Called by the userbot process to push a match alert through this bot."""
    bot.send_message(chat_id, text)


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    _seed_channels()
    bot.infinity_polling()

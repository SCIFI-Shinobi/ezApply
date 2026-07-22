import json
import os
import sys
import requests
from datetime import datetime, timezone

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config.defaults import DEFAULT_CHANNELS
from db.db import list_channels, get_latest_profile, save_post, save_match, mark_notified, ensure_channels
from matcher.matcher import embed, combined_match

API_ID = os.environ.get("TG_API_ID")
API_HASH = os.environ.get("TG_API_HASH")
SESSION_STRING = os.environ.get("TG_SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
YOUR_ID = os.environ.get("YOUR_TELEGRAM_USER_ID")

if not API_ID or not API_HASH:
    print("[USERBOT] TG_API_ID or TG_API_HASH not set. Userbot will not start.")
    sys.exit(1)

client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)


def send_alert(text: str):
    """Push a match alert through the Telegram Bot API (no telebot dependency here)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": YOUR_ID, "text": text, "disable_web_page_preview": False})


def get_channel_usernames():
    """Return a dict of {username: channel_row} for all tracked channels."""
    try:
        ensure_channels(DEFAULT_CHANNELS)
        return {c["username"]: c for c in list_channels()}
    except Exception as exc:
        print(f"[USERBOT WARNING] Could not load channels from DB: {exc}")
        return {}


@client.on(events.NewMessage())
async def handle_new_message(event):
    chat = await event.get_chat()
    username = getattr(chat, "username", None)
    if not username:
        return

    tracked = get_channel_usernames()
    if username not in tracked:
        return  # not one of your tracked channels

    channel_info = tracked[username]
    text = event.raw_text or ""
    if len(text.strip()) < 30:
        return  # skip near-empty posts

    profile = get_latest_profile()
    if not profile:
        return  # no resume uploaded yet, nothing to match against

    post_embedding = embed(text)
    post_id = save_post(
        channel_id=channel_info["id"],
        message_id=event.message.id,
        text=text,
        embedding=post_embedding,
        posted_at=datetime.now(timezone.utc),
    )
    if post_id is None:
        return  # already seen (duplicate)

    profile_json = profile["extracted_json"]
    if isinstance(profile_json, str):
        profile_json = json.loads(profile_json)
    profile_embedding = json.loads(profile["embedding_json"])
    matched, score, rules_score = combined_match(text, post_embedding, profile_embedding, profile_json)

    if matched:
        save_match(post_id, score)
        kind = channel_info["kind"]
        preview = text[:400] + ("..." if len(text) > 400 else "")
        link = f"https://t.me/{username}/{event.message.id}"
        send_alert(
            f"🎯 New {kind} match ({score:.0%}, rules {rules_score}/100) in @{username}\n\n{preview}\n\n{link}"
        )
        mark_notified(post_id)


if __name__ == "__main__":
    if not SESSION_STRING:
        print(
            "[USERBOT] No TG_SESSION_STRING set. Run userbot/generate_session.py first to log in "
            "with your personal Telegram account and get a session string."
        )
        sys.exit(1)
    try:
        ensure_channels(DEFAULT_CHANNELS)
    except Exception as exc:
        print(f"[USERBOT WARNING] Could not seed channels at startup: {exc}")
        print("[USERBOT] Will retry seeding on each incoming message.")
    print("[USERBOT] Listening for new posts in tracked channels...")
    client.start()
    client.run_until_disconnected()

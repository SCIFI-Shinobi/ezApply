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

API_ID = int(os.environ.get("TG_API_ID"))
API_HASH = os.environ.get("TG_API_HASH")
SESSION_STRING = os.environ.get("TG_SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
YOUR_ID = os.environ.get("YOUR_TELEGRAM_USER_ID")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def send_alert(text: str):
    """Push a message through the bot (simple HTTP call, no telebot dependency here)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": YOUR_ID, "text": text, "disable_web_page_preview": False})


def get_channel_usernames():
    ensure_channels(DEFAULT_CHANNELS)
    return {c["username"]: c for c in list_channels()}


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

    import json

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
            f"New {kind} match ({score:.0%}, rules {rules_score}/100) in @{username}\n\n{preview}\n\n{link}"
        )
        mark_notified(post_id)


if __name__ == "__main__":
    if not SESSION_STRING:
        print(
            "No TG_SESSION_STRING set. Run generate_session.py first to log in "
            "with your personal Telegram account and get a session string."
        )
        sys.exit(1)
    ensure_channels(DEFAULT_CHANNELS)
    print("Userbot listening for new posts in tracked channels...")
    client.start()
    client.run_until_disconnected()

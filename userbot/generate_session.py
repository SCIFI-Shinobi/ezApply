"""
Run this ONCE, locally on your own machine (not on the server), to log in with
your personal Telegram account and generate a session string.

It will ask for your phone number, then the login code Telegram sends you.

Paste the resulting string into TG_SESSION_STRING in your .env / hosting env vars.
Keep it secret — it's equivalent to your Telegram login.
"""
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("TG_API_ID"))
API_HASH = os.environ.get("TG_API_HASH")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\nSession string (save this as TG_SESSION_STRING):\n")
    print(client.session.save())
    print("\nDone. Don't share this string with anyone.")

import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Your session string (keep this SECRET, treat like a password):")
    print(client.session.save())
Save and exit.
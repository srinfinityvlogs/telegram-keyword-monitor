import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
session = os.getenv("TELEGRAM_SESSION")

with TelegramClient(StringSession(session), api_id, api_hash) as client:
    print(f"{'Chat ID':<15} {'Type':<12} Name")
    print("-" * 60)
    for dialog in client.iter_dialogs():
        chat_type = "Group" if dialog.is_group else ("Channel" if dialog.is_channel else "User/DM")
        print(f"{dialog.id:<15} {chat_type:<12} {dialog.name}")

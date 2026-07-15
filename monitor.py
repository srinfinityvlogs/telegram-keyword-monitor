import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

from matcher import check_message, load_keywords

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION = os.getenv("TELEGRAM_SESSION")

# --- CONFIGURE THESE ---
SOURCE_CHAT_IDS = [-1001412868909]   # DealBee Deals
NOTIFY_CHAT_ID = -5121609042         # Deals Notification
# ------------------------

DEDUP_FILE = Path("seen_messages.json")
MAX_DEDUP_ENTRIES = 5000  # cap file size; oldest entries dropped beyond this

client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)


def load_seen():
    if DEDUP_FILE.exists():
        try:
            with open(DEDUP_FILE, "r") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def save_seen(seen_set):
    # Keep the file bounded in size
    trimmed = list(seen_set)[-MAX_DEDUP_ENTRIES:]
    with open(DEDUP_FILE, "w") as f:
        json.dump(trimmed, f)


seen_messages = load_seen()


def build_message_link(chat_id, message_id):
    internal_id = str(chat_id).replace("-100", "")
    return f"https://t.me/c/{internal_id}/{message_id}"


@client.on(events.NewMessage(chats=SOURCE_CHAT_IDS))
async def handler(event):
    text = event.raw_text or ""
    if not text.strip():
        return  # skip messages with no text (e.g. media with no caption) for now

    result = check_message(text, keywords=load_keywords())

    if result["excluded_by"]:
        return  # suppressed by an exclusion keyword

    if not result["matched"]:
        return  # no keyword matched

    key = (event.chat_id, event.id)
    if key in seen_messages:
        return  # already forwarded (e.g. duplicate event)
    seen_messages.add(key)

    notification = (
        f"---\n"
        f"{text}\n"
        f"---"
    )

    if event.media:
        await client.send_file(NOTIFY_CHAT_ID, event.media, caption=notification)
    else:
        await client.send_message(NOTIFY_CHAT_ID, notification)

    matched_labels = ", ".join(f"{m['pattern']} ({m['category']})" for m in result["matched"])
    print(f"[FORWARDED] {matched_labels}")


async def send_with_retry(notification, media=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            if media:
                await client.send_file(NOTIFY_CHAT_ID, media, caption=notification)
            else:
                await client.send_message(NOTIFY_CHAT_ID, notification)
            return
        except FloodWaitError as e:
            print(f"[FLOOD WAIT] Sleeping {e.seconds}s before retry ({attempt+1}/{max_retries})")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"[SEND ERROR] {e} (attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(5)
    print("[SEND FAILED] Gave up after max retries")


async def main():
    while True:
        try:
            await client.start()
            print("Listening for messages... (Ctrl+C to stop)")
            await client.run_until_disconnected()
        except (ConnectionError, OSError) as e:
            print(f"[DISCONNECTED] {e} — reconnecting in 10s...")
            await asyncio.sleep(10)
        except KeyboardInterrupt:
            print("Stopped by user.")
            break


if __name__ == "__main__":
    asyncio.run(main())
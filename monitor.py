import os
import re
import json
import asyncio
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.types import MessageMediaWebPage

from matcher import check_message, load_keywords

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION = os.getenv("TELEGRAM_SESSION")

# --- CONFIGURE THESE ---
SOURCE_CHAT_IDS = [-1001412868909, -1001596448068]   # DealBee Deals and DealBee Tips, Tricks and Loots
NOTIFY_CHAT_ID = -5121609042         # Deals Notification
# ------------------------

DEDUP_FILE = Path("seen_messages.json")
CONTENT_DEDUP_FILE = Path("seen_content.json")
MAX_DEDUP_ENTRIES = 5000
CONTENT_DEDUP_TTL_SECONDS = 24 * 60 * 60  # 24 hours

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
    trimmed = list(seen_set)[-MAX_DEDUP_ENTRIES:]
    with open(DEDUP_FILE, "w") as f:
        json.dump(trimmed, f)


def load_seen_content():
    if CONTENT_DEDUP_FILE.exists():
        try:
            with open(CONTENT_DEDUP_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_seen_content(content_dict):
    import time
    now = time.time()
    pruned = {h: ts for h, ts in content_dict.items() if now - ts < CONTENT_DEDUP_TTL_SECONDS}
    with open(CONTENT_DEDUP_FILE, "w") as f:
        json.dump(pruned, f)


def normalize_text(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def content_hash(text):
    import hashlib
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


seen_messages = load_seen()
seen_content = load_seen_content()


@client.on(events.NewMessage(chats=SOURCE_CHAT_IDS))
async def handler(event):
    text = event.raw_text or ""
    if not text.strip():
        return

    result = check_message(text, keywords=load_keywords())

    if result["excluded_by"] or not result["matched"]:
        return

    key = f"{event.chat_id}:{event.id}"
    if key in seen_messages:
        return
    seen_messages.add(key)
    save_seen(seen_messages)

    chash = content_hash(text)
    import time
    now = time.time()
    if chash in seen_content and (now - seen_content[chash]) < CONTENT_DEDUP_TTL_SECONDS:
        print(f"[SKIPPED - DUPLICATE CONTENT] chat={event.chat_id}")
        return
    seen_content[chash] = now
    save_seen_content(seen_content)

    notification = (
        f"---\n"
        f"{text}\n"
        f"---"
    )

    real_media = event.media if event.media and not isinstance(event.media, MessageMediaWebPage) else None
    await send_with_retry(notification, real_media)

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

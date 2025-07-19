from flask import Flask, request
import requests
import feedparser
import os
import threading
import time

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "Friend")
    message_id = message.get("message_id")

    if not chat_id or not text:
        return {"ok": True}

    # 🔴 Start background cleanup of old messages
    threading.Thread(target=delete_old_messages, args=(chat_id,)).start()

    # 🔗 Block links
    if any(link in text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
        warning = f"⚠️ {first_name}, sharing links is not allowed in this group."

        resp = requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": warning,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_to_message_id": message_id
        })

        # Delete user's message
        delete_message(chat_id, message_id)

        # Delete warning after 20 seconds
        if resp.status_code == 200:
            result = resp.json()
            warning_msg_id = result.get("result", {}).get("message_id")
            if warning_msg_id:
                threading.Timer(20.0, delete_message, args=(chat_id, warning_msg_id)).start()

        return {"ok": True}

    # 🤖 Handle /start command
    if text.lower() == "/start":
        reply = (
            f"🎬 Welcome {first_name}!\n"
            "Use the following commands to search:\n\n"
            "<code>#movie Animal</code> - for movies\n"
            "<code>#tv Breaking Bad</code> - for TV shows\n"
            "<code>#series Loki</code> - for series"
        )
        send_message(chat_id, reply)
        return {"ok": True}

    # 🔍 Handle search commands
    lower_text = text.lower()

    if lower_text.startswith("#movie "):
        query = text[7:].strip()
        if query:
            reply = search_movie(query, first_name, category="Movie")
        else:
            reply = "❌ Please provide a movie name after #movie."
        send_message(chat_id, reply)

    elif lower_text.startswith("#tv "):
        query = text[4:].strip()
        if query:
            reply = search_movie(query, first_name, category="TV Show")
        else:
            reply = "❌ Please provide a TV show name after #tv."
        send_message(chat_id, reply)

    elif lower_text.startswith("#series "):
        query = text[8:].strip()
        if query:
            reply = search_movie(query, first_name, category="Series")
        else:
            reply = "❌ Please provide a series name after #series."
        send_message(chat_id, reply)

    return {"ok": True}


def send_message(chat_id, text, reply_to=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to

    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)


def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    })


def search_movie(query, first_name, category="Movie"):
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        feed = feedparser.parse(feed_url)
        matches = []

        for entry in feed.entries:
            title = entry.title.lower()
            if query.lower() in title:
                matches.append(f"🎬 {entry.title}\n🔗 {entry.link}")

        if matches:
            return "\n\n".join(matches[:5])
        else:
            return f"❌ Sorry {first_name}, no {category.lower()} found for: <b>{query}</b>"
    except Exception as e:
        return f"⚠️ Error while searching: {e}"


def delete_old_messages(chat_id):
    try:
        # Fetch recent 100 messages
        resp = requests.get(f"{TELEGRAM_API}/getChatHistory", params={
            "chat_id": chat_id,
            "limit": 100
        })

        # Fallback if getChatHistory is not available, use getUpdates
        if resp.status_code != 200 or not resp.json().get("ok"):
            return

        now_ts = int(time.time())

        messages = resp.json().get("result", [])
        for msg in messages:
            msg_id = msg.get("message_id")
            msg_date = msg.get("date")

            if msg_date and (now_ts - msg_date > 30):  # older than 30 seconds
                delete_message(chat_id, msg_id)

    except Exception as e:
        print("❌ Error deleting old messages:", e)

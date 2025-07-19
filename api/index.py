from flask import Flask, request
import requests
import feedparser
import os

app = Flask(__name__)

# Environment variables for security
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "Friend")
    message_id = message.get("message_id")

    # If message is missing required data
    if not chat_id or not text:
        return {"ok": True}

    # 🔗 Delete message if it contains a link
    if "http://" in text.lower() or "https://" in text.lower() or "t.me" in text.lower() or "telegram.me" in text.lower():
        delete_message(chat_id, message_id)
        return {"ok": True}

    # 🤖 Handle commands and queries
    if text.lower() == "/start":
        reply = f"🎬 Welcome {first_name}! Send any movie name to search."
    else:
        reply = search_movie(text.lower(), first_name)

    send_message(chat_id, reply)
    return {"ok": True}

def search_movie(query, first_name):
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        feed = feedparser.parse(feed_url)
        matches = []

        for entry in feed.entries:
            title = entry.title.lower()
            if query in title:
                matches.append(f"🎬 {entry.title}\n🔗 {entry.link}")

        if matches:
            return "\n\n".join(matches[:5])
        else:
            return f"❌ Sorry {first_name}, no movies found for: <b>{query}</b>"

    except Exception as e:
        return f"⚠️ Error while searching: {e}"

def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(TELEGRAM_API, json=payload)

def delete_message(chat_id, message_id):
    delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    requests.post(delete_url, json=payload)


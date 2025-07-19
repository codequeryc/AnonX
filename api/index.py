from flask import Flask, request
import requests
import feedparser
import os

app = Flask(__name__)

# Environment Variables
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
    user_id = message.get("from", {}).get("id")
    message_id = message.get("message_id")

    if not chat_id or not text:
        return {"ok": True}

    # 🔗 Detect and block links
    if any(link in text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
        delete_message(chat_id, message_id)
        warn_message(chat_id, user_id, first_name)
        return {"ok": True}

    # 🤖 Command or search
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
            if query in entry.title.lower():
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
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def delete_message(chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    requests.post(f"{TELEGRAM_API}/deleteMessage", json=payload)

def warn_message(chat_id, user_id, first_name):
    warning = f"⚠️ {first_name}, sending links is not allowed in this group. Please follow the rules."
    payload = {
        "chat_id": chat_id,
        "text": warning,
        "reply_to_message_id": user_id,
        "disable_web_page_preview": True
    }
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

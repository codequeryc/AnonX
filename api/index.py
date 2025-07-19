from flask import Flask, request
import requests
import feedparser
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    first_name = chat.get("first_name", "User")
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return {"ok": True}

    if text.lower() == "/start":
        reply = f"🎬 Welcome, {first_name}!\nSend any movie name to search."
    else:
        reply = search_movie(text, first_name)

    send_message(chat_id, reply)
    return {"ok": True}

def search_movie(query, user_name):
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        feed = feedparser.parse(feed_url)
        matches = []

        for entry in feed.entries:
            title = entry.title.lower()
            if query.lower() in title:
                matches.append(f"🎬 <b>{entry.title}</b>\n🔗 {entry.link}")

        if matches:
            return f"<b>Results for:</b> <i>{query}</i>\n\n" + "\n\n".join(matches[:5])
        else:
            return f"❌ Sorry <b>{user_name}</b>, no movies found for:\n<i>{query}</i>"

    except Exception as e:
        return f"⚠️ Error searching movies: {e}"

def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(TELEGRAM_API, json=payload)

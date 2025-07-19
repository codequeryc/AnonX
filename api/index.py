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
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip().lower()

    if not chat_id or not text:
        return {"ok": True}

    if text == "/start":
        reply = "🎬 Welcome to Movie Bot! Send any movie name to search."
    else:
        reply = search_movie(text)

    send_message(chat_id, reply)
    return {"ok": True}

def search_movie(query):
    try:
        # Use feedparser to parse Blogger RSS feed
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        feed = feedparser.parse(feed_url)
        matches = []

        for entry in feed.entries:
            title = entry.title.lower()
            if query in title:
                matches.append(f"🎬 {entry.title}\n🔗 {entry.link}")

        if matches:
            return "\n\n".join(matches[:5])  # max 5 results
        else:
            return "❌ No movies found matching your query."

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

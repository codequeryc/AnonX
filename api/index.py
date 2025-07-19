from flask import Flask, request
import requests
from fetch import search_blogger  # Import from fetch.py

app = Flask(__name__)

BOT_TOKEN = "your_bot_token"  # Already set on Vercel
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

BLOG_URL = "https://yourblog.blogspot.com"  # Replace with your Blogger blog URL

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").strip()

        reply = None

        if text.lower().startswith("#request"):
            movie = text[8:].strip()
            if movie:
                reply = search_blogger(BLOG_URL, movie)
            else:
                reply = "⚠️ Please provide a movie name after #request"

        elif text.lower() == "/help":
            reply = (
                "📌 *Movie Request Bot Help*\n\n"
                "🎬 To request a movie, type:\n"
                "#request Movie Name\n\n"
                "Example:\n`#request Inception`\n\n"
                "ℹ️ You can also use `/help` to view this message."
            )

        if reply:
            requests.post(TELEGRAM_API, json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown"
            })

    return "ok", 200

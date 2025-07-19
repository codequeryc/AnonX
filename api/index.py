from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN") or "YOUR_BOT_TOKEN"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot is running on Vercel!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            reply = "🎬 Welcome to Movie Bot!\nSend movie name to get a link."
        else:
            reply = search_movie(text)

        requests.post(TELEGRAM_API, json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}

def search_movie(query):
    movies = {
        "animal": "https://example.com/animal-2023.mp4",
        "kgf 2": "https://example.com/kgf2-1080p.mp4"
    }

    for title, link in movies.items():
        if query.lower() in title.lower():
            return f"🎥 Found: {title}\n🔗 {link}"

    return "❌ Movie not found!"

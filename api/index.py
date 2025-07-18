from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

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
                reply = f"✅ Your request for *{movie}* has been noted."
            else:
                reply = "⚠️ Please provide a movie name after #request"

        elif text.lower() == "/help":
reply = (
    "📌 *Movie Request Bot Help*\n\n"
    "🎬 To request a movie, type:\n"
    "`#request Movie Name`\n\n"
    "Example:\n`#request Inception`\n\n"
    "ℹ️ Type ` /help ` to show this help again."
)


        if reply:
            requests.post(TELEGRAM_API, json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown"
            })

    return "ok", 200

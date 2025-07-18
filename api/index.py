from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN") or "your_bot_token_here"
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
        print("Received message:", text)

        reply = None

        if text.lower().startswith("#request"):
            parts = text.split(maxsplit=1)
            movie = parts[1].strip() if len(parts) > 1 else ""

            username = (
                data["message"]["from"].get("username")
                or data["message"]["from"].get("first_name")
                or "User"
            )

            if movie:
                reply = f"✅ @{username}, your request for *{movie}* has been noted."
            else:
                reply = "⚠️ Please provide a movie name after #request"

        elif text.lower() == "/help":
            reply = (
                "📌 *Movie Request Bot Help*\n\n"
                "🎬 To request a movie, type:\n"
                "`#request Movie Name`\n\n"
                "Example:\n`#request Inception`\n\n"
                "ℹ️ You can also use /help to view this message."
            )

        if reply:
            requests.post(TELEGRAM_API, json={
                "chat_id": chat_id,
                "text": reply,
                "parse_mode": "Markdown"
            })

    return "ok", 200

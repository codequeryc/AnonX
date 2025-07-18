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
    data = request.json

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})
        username = user.get("username")
        first_name = user.get("first_name", "User")

        mention = f"@{username}" if username else first_name

        # Help menu
        if text.lower() in ["/start", "/help"]:
            reply = (
                f"👋 Hello {mention}!\n\n"
                "📌 *Commands:*\n"
                "`#request Movie Name` — to request a movie\n"
                "`/help` — to show this menu"
            )
        elif text.lower().startswith("#request"):
            movie = text[8:].strip()
            if movie:
                reply = f"✅ {mention}, your request for *{movie}* has been noted."
            else:
                reply = f"⚠️ {mention}, please provide a movie name after `#request`."
        else:
            return "ok"

        requests.post(TELEGRAM_API, json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        })

    return "ok"

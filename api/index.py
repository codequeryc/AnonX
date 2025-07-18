from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = "123456789:ABCDEF"  # Replace with your actual token
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("Received data:", data)

    message = data.get("message") or data.get("edited_message")
    if not message:
        return "no message", 200

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip().lower()

    reply = None

    if text.startswith("#request"):
        movie = text[8:].strip()
        reply = f"✅ Your request for *{movie}* has been noted." if movie else "⚠️ Please provide a movie name after #request"

    elif text == "/help":
        reply = (
            "📌 *Movie Request Bot Help*\n\n"
            "🎬 To request a movie, type:\n"
            "`#request Movie Name`\n\n"
            "Example:\n`#request Inception`\n\n"
            "ℹ️ Type ` /help ` to view this message again."
        )

    if reply:
        r = requests.post(TELEGRAM_API, json={
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        })
        print("Sent:", r.status_code, r.text)

    return "ok", 200

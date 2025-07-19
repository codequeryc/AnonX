from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
BLOG_URL = os.environ.get("BLOG_URL")
VERCEL_URL = os.environ.get("VERCEL_URL")

if not VERCEL_URL.startswith("http"):
    VERCEL_URL = "https://" + VERCEL_URL

FIND_URL = f"{VERCEL_URL}/api/find"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot is running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data or "message" not in data:
        return {"status": "ignored"}, 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        send_message(chat_id, "🎬 Welcome to Movie Bot! Send any movie name to search.")
    else:
        # Search movie from find endpoint
        try:
            res = requests.post(FIND_URL, json={"query": text})
            result = res.json()

            if result.get("success") and result.get("movies"):
                reply = "\n\n".join(
                    [f"🎬 <b>{m['title']}</b>\n🔗 <a href='{m['url']}'>Watch Now</a>" for m in result["movies"]]
                )
                send_message(chat_id, reply, parse_mode="HTML")
            else:
                send_message(chat_id, "❌ Movie not found.")
        except Exception as e:
            send_message(chat_id, f"⚠️ Error while searching: {str(e)}")

    return {"status": "ok"}, 200

def send_message(chat_id, text, parse_mode=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    requests.post(TELEGRAM_API, json=payload)

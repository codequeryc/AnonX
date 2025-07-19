from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")  # Must be a public Blogger feed URL
VERCEL_URL = os.environ.get("VERCEL_URL", "https://anonx-chi.vercel.app")
FIND_URL = f"{VERCEL_URL}/api/find"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if text.startswith("/start"):
        reply = "🎬 Welcome to MovieBot!\nSend any movie name to search."
    elif text:
        try:
            search = requests.get(FIND_URL, params={"q": text}, timeout=10).json()
            results = search.get("results", [])
            if results:
                reply = "\n\n".join(
                    [f"🎬 <b>{r['title']}</b>\n<a href='{r['link']}'>Watch Now</a>" for r in results]
                )
            else:
                reply = "❌ No results found."
        except Exception as e:
            reply = f"⚠️ Error while searching: {e}"
    else:
        reply = "❓ Unknown command."

    requests.post(TELEGRAM_API, json={
        "chat_id": chat_id,
        "text": reply,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    })

    return {"ok": True}

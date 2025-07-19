from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_API_URL = os.environ.get("BLOG_URL") or "https://yourblog.blogspot.com"

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Telegram Movie Bot is live on Vercel!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            reply = "🎬 Welcome to Movie Bot!\nSend a movie name to get the download link."
        else:
            reply = search_movie(text)

        requests.post(TELEGRAM_API, json={
            "chat_id": chat_id,
            "text": reply
        })

    return {"ok": True}

def search_movie(query):
    try:
        find_url = "https://{your-vercel-domain}.vercel.app/api/find"  # update this later
        response = requests.post(find_url, json={"query": query})
        result = response.json()

        if result.get("found"):
            return f"🎬 Found: {result['title']}\n🔗 {result['link']}"
        else:
            return "❌ Movie not found in blog."
    except Exception as e:
        return f"⚠️ Error while searching: {e}"

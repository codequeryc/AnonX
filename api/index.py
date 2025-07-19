from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

BLOG_URL = os.environ.get("BLOG_URL")

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live with Blogger Feed Search!"

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
                feed_url = f"{BLOG_URL}/feeds/posts/default?q={movie}&alt=json"
                response = requests.get(feed_url)

                if response.status_code == 200:
                    result = response.json()
                    entries = result.get("feed", {}).get("entry", [])
                    
                    if entries:
                        reply = f"🎬 *Search Results for:* `{movie}`\n\n"
                        for entry in entries[:5]:  # Top 5 results
                            title = entry.get("title", {}).get("$t", "No Title")
                            link = next((l["href"] for l in entry["link"] if l["rel"] == "alternate"), "#")
                            reply += f"🔗 [{title}]({link})\n"
                    else:
                        reply = f"❌ No results found for `{movie}`"
                else:
                    reply = "⚠️ Failed to fetch data from Blogger Feed."
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
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            })

    return "ok", 200

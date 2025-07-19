from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def search_posts(query, max_results=5):
    if not query:
        return []

    feed_url = f"{BLOG_URL}/feeds/posts/default?q={query}&alt=json"
    response = requests.get(feed_url)

    if response.status_code != 200:
        return None

    try:
        data = response.json()
        entries = data.get("feed", {}).get("entry", [])
        results = []

        for entry in entries[:max_results]:
            title = entry.get("title", {}).get("$t", "No Title")
            link = next((l["href"] for l in entry["link"] if l["rel"] == "alternate"), "#")
            results.append({"title": title, "link": link})

        return results
    except Exception as e:
        print("Error parsing Blogger feed:", e)
        return None

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("Webhook received:", data)

    if data and "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").strip()

        reply = None

        if text.lower().startswith("#request"):
            movie = text[8:].strip()

            if movie:
                results = search_posts(movie)
                if results is None:
                    reply = "⚠️ Failed to fetch data from Blogger Feed."
                elif not results:
                    reply = f"❌ No results found for `{movie}`"
                else:
                    reply = f"🎬 *Search Results for:* `{movie}`\n\n"
                    for r in results:
                        reply += f"🔗 [{r['title']}]({r['link']})\n"
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

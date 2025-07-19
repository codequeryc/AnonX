from flask import Flask, request
import feedparser
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live!"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if not data or "message" not in data:
        return {"status": "ignored"}

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip().lower()
    first_name = message["from"].get("first_name", "User")

    if not text:
        return {"status": "no text"}

    if text == "/help":
        help_text = (
            "📽️ *Movie Request Bot Help*\n\n"
            "👉 Just send the name of a movie or show and I'll try to find it.\n"
            "✅ Example: `Animal`, `Pathaan`, `KGF`\n\n"
            "ℹ️ I search based on latest blog posts."
        )
        send_message(chat_id, help_text, parse_mode="Markdown")
        return {"status": "help sent"}

    result = search_movie(text, first_name)
    send_message(chat_id, result, parse_mode="HTML")
    return {"status": "done"}


def search_movie(query, first_name):
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        feed = feedparser.parse(feed_url)
        matches = []

        for entry in feed.entries:
            title = entry.title.lower()
            if query in title:
                matches.append(f"🎬 <b>{entry.title}</b>\n🔗 <a href='{entry.link}'>Watch Now</a>")

        if matches:
            return "\n\n".join(matches[:5])
        else:
            return (
                f"👤 <b>{first_name} said:</b> <code>{query}</code>\n"
                f"❌ Sorry <b>{first_name}</b>, no movies found for: <b>{query}</b>"
            )

    except Exception as e:
        return f"⚠️ Error while searching: <code>{e}</code>"


def send_message(chat_id, text, parse_mode=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode or "HTML",
        "disable_web_page_preview": False
    }
    requests.post(TELEGRAM_API, json=payload)


if __name__ == "__main__":
    app.run(debug=True)

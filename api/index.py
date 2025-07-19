from flask import Flask, request
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Util: Send message
def send_message(chat_id, text, reply_to=None, buttons=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": buttons
        }
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

# Fake movie search function (replace this with real scraping/search)
def search_movie(query):
    results = []
    for i in range(3):
        title = f"{query} Result {i+1}"
        link = f"https://example.com/{query.lower()}-{i+1}"
        results.append([{
            "text": title,
            "callback_data": f"copylink:{link}"
        }])
    return results

# Main webhook
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    # Handle callback button click
    if "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        msg_id = query["message"]["message_id"]
        cb_data = query["data"]

        if cb_data.startswith("copylink:"):
            link = cb_data.replace("copylink:", "")
            send_message(chat_id, f"🔗 Here is your link:\n<code>{link}</code>", reply_to=msg_id)
        return {"ok": True}

    # Handle normal messages
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if text.lower() == "/start":
        send_message(chat_id, "👋 Welcome! Send me a hashtag like #movie Animal to search.")
    elif "#movie" in text.lower():
        movie_name = text.split("#movie", 1)[1].strip()
        if movie_name:
            buttons = search_movie(movie_name)
            send_message(chat_id, f"🎬 Results for <b>{movie_name}</b>:", buttons=buttons)
        else:
            send_message(chat_id, "❌ Please provide a movie name after #movie.")
    else:
        send_message(chat_id, "🤖 Unknown command. Try /start or #movie Pushpa.")

    return {"ok": True}

# Home route
@app.route("/", methods=["GET"])
def home():
    return "🤖 Telegram Movie Bot Running!"


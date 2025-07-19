from flask import Flask, request
import requests
import os
import threading
import logging
from bs4 import BeautifulSoup

app = Flask(__name__)

# ✅ Enable logging for debugging
logging.basicConfig(level=logging.DEBUG)

# ✅ Telegram Bot Token & API URL
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    logging.debug(f"Received data: {data}")

    # ✅ Handle callback query for "Copy Link"
    if "callback_query" in data:
        query = data["callback_query"]
        chat_id = query["message"]["chat"]["id"]
        msg_id = query["message"]["message_id"]
        link = query["data"]

        send_message(chat_id, f"🔗 Copy this link:\n<code>{link}</code>", reply_to=msg_id)
        return {"ok": True}

    # ✅ Handle regular user message
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_text = msg.get("text", "").strip()
    user_name = msg.get("from", {}).get("first_name", "Friend")
    msg_id = msg.get("message_id")

    logging.debug(f"Message from {user_name}: {user_text}")

    if not chat_id or not user_text:
        return {"ok": True}

    # 🚫 Block links
    if any(link in user_text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
        warning = f"⚠️ {user_name}, sharing links is not allowed in this group."
        warn_msg = send_message(chat_id, warning, reply_to=msg_id)
        delete_message(chat_id, msg_id)

        if warn_msg:
            warn_id = warn_msg.get("result", {}).get("message_id")
            threading.Timer(10, delete_message, args=(chat_id, warn_id)).start()
        return {"ok": True}

    # 👋 Start message
    if user_text.lower() == "/start":
        welcome = (
            f"🎬 Welcome {user_name}!\n"
            "Search with:\n"
            "<code>#movie Animal</code>\n"
            "<code>#tv Breaking Bad</code>\n"
            "<code>#series Loki</code>"
        )
        send_message(chat_id, welcome)
        return {"ok": True}

    # 🔍 Handle search commands
    if user_text.lower().startswith("#movie "):
        return handle_search(chat_id, user_text[7:], user_name, "Movie")

    if user_text.lower().startswith("#tv "):
        return handle_search(chat_id, user_text[4:], user_name, "TV Show")

    if user_text.lower().startswith("#series "):
        return handle_search(chat_id, user_text[8:], user_name, "Series")

    return {"ok": True}

# 🔍 Search handler
def handle_search(chat_id, query, user_name, category):
    query = query.strip()
    logging.debug(f"Handling search for {category}: {query}")

    if not query:
        send_message(chat_id, f"❌ Please provide a {category.lower()} name.")
        return {"ok": True}

    text, buttons = search_filmyfly(query, user_name, category)
    logging.debug(f"Search results text: {text}")
    logging.debug(f"Inline buttons: {buttons}")

    send_message(chat_id, text, buttons=buttons)
    return {"ok": True}

# ✅ Send message to Telegram
def send_message(chat_id, text, reply_to=None, buttons=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}

    res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    if res.ok:
        return res.json()
    else:
        logging.error(f"Failed to send message: {res.text}")
        return None

# ✅ Delete message
def delete_message(chat_id, message_id):
    res = requests.post(f"{TELEGRAM_API}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    })
    if not res.ok:
        logging.error(f"Failed to delete message: {res.text}")

# 🔍 Scrape from filmyfly.party
def search_filmyfly(query, user_name, category):
    try:
        url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for item in soup.select("div.A2"):
            a_tag = item.find("a", href=True)
            b_tag = item.find("b")
            if a_tag and b_tag:
                title = b_tag.text.strip()
                link = "https://filmyfly.party" + a_tag["href"]
                results.append([{"text": title, "url": link}])
            if len(results) >= 5:
                break

        if results:
            return f"🔍 {category} results for <b>{query}</b>:", results
        else:
            return f"❌ Sorry {user_name}, no {category.lower()} found for <b>{query}</b>.", []

    except Exception as e:
        logging.exception("Error during scraping")
        return f"⚠️ Error: {e}", []

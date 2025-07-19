from flask import Flask, request
import requests
import os
import threading
from bs4 import BeautifulSoup

app = Flask(__name__)

# Bot credentials
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()
    first_name = message.get("from", {}).get("first_name", "Friend")
    message_id = message.get("message_id")

    if not chat_id or not text:
        return {"ok": True}

    # 🔗 Block links
    if any(link in text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
        warning = f"⚠️ {first_name}, sharing links is not allowed in this group."

        # Send warning message
        resp = requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": warning,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_to_message_id": message_id
        })

        # Delete the user's message
        delete_message(chat_id, message_id)

        # Delete the warning after 10 seconds (non-blocking)
        if resp.status_code == 200:
            result = resp.json()
            warning_msg_id = result.get("result", {}).get("message_id")
            if warning_msg_id:
                threading.Timer(10.0, delete_message, args=(chat_id, warning_msg_id)).start()

        return {"ok": True}

    # 🤖 Handle /start command
    if text.lower() == "/start":
        reply = (
            f"🎬 Welcome {first_name}!\n"
            "Use the following commands to search:\n\n"
            "<code>#movie Animal</code> - for movies\n"
            "<code>#tv Breaking Bad</code> - for TV shows\n"
            "<code>#series Loki</code> - for series"
        )
        send_message(chat_id, reply)
        return {"ok": True}

    # 🔍 Handle search commands
    lower_text = text.lower()

    if lower_text.startswith("#movie "):
        query = text[7:].strip()
        if query:
            msg, buttons = search_movie(query, first_name, category="Movie")
        else:
            msg, buttons = "❌ Please provide a movie name after #movie.", []
        send_message(chat_id, msg, buttons=buttons)

    elif lower_text.startswith("#tv "):
        query = text[4:].strip()
        if query:
            msg, buttons = search_movie(query, first_name, category="TV Show")
        else:
            msg, buttons = "❌ Please provide a TV show name after #tv.", []
        send_message(chat_id, msg, buttons=buttons)

    elif lower_text.startswith("#series "):
        query = text[8:].strip()
        if query:
            msg, buttons = search_movie(query, first_name, category="Series")
        else:
            msg, buttons = "❌ Please provide a series name after #series.", []
        send_message(chat_id, msg, buttons=buttons)

    return {"ok": True}


# ✅ Send message (supporting inline buttons)
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
        payload["reply_markup"] = {
            "inline_keyboard": buttons
        }

    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)


# ✅ Delete message
def delete_message(chat_id, message_id):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    requests.post(f"{TELEGRAM_API}/deleteMessage", json=payload)


# ✅ Scrape results from filmyfly.party
def search_movie(query, first_name, category="Movie"):
    try:
        search_url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        buttons = []

        for item in soup.select("div.A2"):
            link_tag = item.find("a", href=True)
            title_tag = item.find("b")
            if link_tag and title_tag:
                url = "https://filmyfly.party" + link_tag['href']
                title = title_tag.get_text(strip=True)
                results.append(f"🎬 {title}")
                buttons.append([
                    {"text": title, "url": url}
                ])
            if len(results) >= 5:
                break

        if results:
            text = f"🔍 Found the following {category.lower()} results:"
            return text, buttons
        else:
            return f"❌ Sorry {first_name}, no {category.lower()} found for: <b>{query}</b>", []

    except Exception as e:
        return f"⚠️ Error while searching: {e}", []


from flask import Flask, request
import requests
import os
import threading
from bs4 import BeautifulSoup

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Set this as an environment variable
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    # ✅ Handle callback_query (button click)
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        message_id = callback["message"]["message_id"]
        user_name = callback["from"].get("first_name", "Friend")
        data_url = callback.get("data")

        content, poster_url = fetch_filmyfly_post(data_url)

        if poster_url:
            send_photo(chat_id, poster_url, content)
        else:
            send_message(chat_id, content, reply_to=message_id)
        return {"ok": True}

    # ✅ Handle regular message
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_text = msg.get("text", "").strip()
    user_name = msg.get("from", {}).get("first_name", "Friend")
    msg_id = msg.get("message_id")

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

    # 🟢 Start command
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


# 🔍 Search and respond
def handle_search(chat_id, query, user_name, category):
    query = query.strip()
    if not query:
        send_message(chat_id, f"❌ Please provide a {category.lower()} name.")
        return {"ok": True}

    text, buttons = search_filmyfly(query, user_name, category)
    send_message(chat_id, text, buttons=buttons)
    return {"ok": True}


# ✅ Send text message
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
    if not res.ok:
        print("Send Message Error:", res.text)
    return res.json() if res.ok else None


# ✅ Send photo with caption
def send_photo(chat_id, image_url, caption=None):
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    res = requests.post(f"{TELEGRAM_API}/sendPhoto", json=payload)
    if not res.ok:
        print("Send Photo Error:", res.text)


# 🗑️ Delete message
def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    })


# 🔍 Search results from filmyfly
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
                results.append([{"text": title, "callback_data": link}])
            if len(results) >= 5:
                break

        if results:
            return f"🔍 {category} results for <b>{query}</b>:", results
        else:
            return f"❌ Sorry {user_name}, no {category.lower()} found for <b>{query}</b>.", []

    except Exception as e:
        return f"⚠️ Error: {e}", []


# 📥 Scrape full post
def fetch_filmyfly_post(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        # Title
        title_tag = soup.find("h2")
        title = title_tag.text.strip() if title_tag else "🎬 Movie Info"

        # Poster
        poster_tag = soup.select_one(".movie-thumb img")
        poster_url = poster_tag["src"] if poster_tag else None

        # Screenshot
        screenshot_tag = soup.select_one(".ss img")
        screenshot_url = screenshot_tag["src"] if screenshot_tag else None

        # Download link
        download_tag = soup.select_one(".dlbtn a")
        download_url = download_tag["href"] if download_tag else None
        download_text = download_tag.text.strip() if download_tag else "Download"

        # Build message
        message = f"<b>{title}</b>\n\n"
        if screenshot_url:
            message += f"<a href='{screenshot_url}'>🖼️ Screenshot</a>\n"
        if download_url:
            message += f"\n👉 <a href='{download_url}'>{download_text}</a>"

        return message, poster_url
    except Exception as e:
        return f"⚠️ Failed to fetch post: {e}", None

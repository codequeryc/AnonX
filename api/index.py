from flask import Flask, request
import requests
from bs4 import BeautifulSoup
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
SITE_URL = "https://filmyfly.party"

def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)

def search_amazing_movies(query):
    url = f"{SITE_URL}/?s={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    posts = soup.select("div#archive-content article")

    buttons = []
    for post in posts[:5]:
        title = post.select_one(".post-title").text.strip()
        post_url = post.select_one("a")["href"]
        buttons.append([{
            "text": title,
            "callback_data": post_url[:64]  # callback_data max 64 chars
        }])

    return {
        "inline_keyboard": buttons
    } if buttons else None

def handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    post_url = callback["data"]

    # Remove loading indicator
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        "callback_query_id": callback["id"]
    })

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(post_url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Post Details"
        links = [
            a['href'] for a in soup.select("a[href]")
            if any(x in a['href'] for x in [".mkv", ".mp4", "drive.google", "mediafire"])
        ]
        text = f"<b>{title}</b>\n\n"
        if links:
            for link in links[:5]:
                text += f"🔗 <code>{link}</code>\n"
        else:
            text += "⚠️ No links found."
        send_message(chat_id, text)
    except Exception as e:
        send_message(chat_id, f"❌ Error fetching post:\n<code>{e}</code>")

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    if "callback_query" in data:
        handle_callback(data["callback_query"])
        return {"ok": True}

    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text.lower().startswith("#amazing"):
            query = text.replace("#amazing", "").strip()
            if not query:
                send_message(chat_id, "❗ Please enter something after #amazing")
                return {"ok": True}
            keyboard = search_amazing_movies(query)
            if keyboard:
                send_message(chat_id, f"🔍 Results for: <b>{query}</b>", reply_markup={"inline_keyboard": keyboard["inline_keyboard"]})
            else:
                send_message(chat_id, "⚠️ No results found.")
        else:
            send_message(chat_id, "Send #amazing followed by your search term.")

    return {"ok": True}

@app.route("/", methods=["GET"])
def home():
    return "🤖 Amazing Bot Running!"

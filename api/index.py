from flask import Flask, request
import requests
import os
from bs4 import BeautifulSoup
import threading

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Set this in your environment
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
movie_links = {}  # callback_data -> actual movie link (GLOBAL STORE)

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    message = data.get("message")
    callback = data.get("callback_query")

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text.startswith("#movie"):
            query = text.replace("#movie", "").strip()
            threading.Thread(target=handle_search, args=(chat_id, query, "Movie")).start()
        elif text.startswith("#series"):
            query = text.replace("#series", "").strip()
            threading.Thread(target=handle_search, args=(chat_id, query, "Series")).start()
        else:
            send_message(chat_id, "❓ Send query using #movie or #series")

    elif callback:
        chat_id = callback["message"]["chat"]["id"]
        callback_id = callback["data"]
        message_id = callback["message"]["message_id"]

        link = movie_links.get(callback_id)
        if link:
            preview = scrape_preview(link)
            edit_message(chat_id, message_id, preview)
        else:
            edit_message(chat_id, message_id, "⚠️ Link expired or not found.")

    return "OK", 200

def handle_search(chat_id, query, category):
    text, buttons = search_filmyfly(query, category)
    send_inline_keyboard(chat_id, text, buttons)

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

def send_inline_keyboard(chat_id, text, buttons):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons}
    })

def edit_message(chat_id, message_id, text):
    requests.post(f"{TELEGRAM_API}/editMessageText", json={
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    })

def search_filmyfly(query, category):
    try:
        url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for item in soup.select("div.A2"):
            a_tag = item.find("a", href=True)
            b_tag = item.find("b")
            if a_tag and b_tag:
                title = b_tag.text.strip()
                link = "https://filmyfly.party" + a_tag["href"]
                callback_id = f"movie_{abs(hash(title + link))}"
                movie_links[callback_id] = link
                results.append([{"text": title, "callback_data": callback_id}])
            if len(results) >= 10:
                break

        if results:
            return f"🔍 {category} results for <b>{query}</b>:", results
        return f"❌ No {category.lower()} found for <b>{query}</b>.", []
    except Exception as e:
        print(f"[Search Error] {e}")
        return f"⚠️ Error searching for {category.lower()}. Try again later.", []

def scrape_preview(link):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(link, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.text.strip() if soup.title else "Preview"
        img = soup.select_one("div.A1 img")
        img_url = img["src"] if img else ""
        if img_url:
            return f"<b>{title}</b>\n<a href='{img_url}'>📥 Download</a>"
        else:
            return f"<b>{title}</b>\n🔗 <a href='{link}'>Visit Page</a>"
    except Exception as e:
        print(f"[Preview Error] {e}")
        return "⚠️ Failed to load preview."

if __name__ == "__main__":
    app.run()

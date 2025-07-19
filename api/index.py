from flask import Flask, request
import requests, os, threading
from bs4 import BeautifulSoup

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
movie_links = {}

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        # Callback button
        if "callback_query" in data:
            return handle_callback(data["callback_query"])

        # New message
        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        msg_text = msg.get("text", "").strip()
        msg_id = msg.get("message_id")
        user_name = msg.get("from", {}).get("first_name", "Friend")

        if not chat_id or not msg_text:
            return {"ok": True}

        # Block links
        if any(x in msg_text.lower() for x in ["http://", "https://", "t.me", "telegram.me"]):
            warning = f"⚠️ {user_name}, sharing links is not allowed."
            warn_msg = send_message(chat_id, warning, reply_to=msg_id)
            delete_message(chat_id, msg_id)
            if warn_msg:
                warn_id = warn_msg.get("result", {}).get("message_id")
                threading.Timer(10, delete_message, args=(chat_id, warn_id)).start()
            return {"ok": True}

        # Start
        if msg_text.lower() == "/start":
            welcome = (
                f"🎬 Welcome {user_name}!\n"
                "Search with:\n"
                "<code>#movie Animal</code>\n"
                "<code>#tv Breaking Bad</code>\n"
                "<code>#series Loki</code>"
            )
            send_message(chat_id, welcome)
            return {"ok": True}

        # Search commands
        if msg_text.lower().startswith("#movie "):
            return handle_search(chat_id, msg_text[7:], user_name, "Movie")
        if msg_text.lower().startswith("#tv "):
            return handle_search(chat_id, msg_text[4:], user_name, "TV Show")
        if msg_text.lower().startswith("#series "):
            return handle_search(chat_id, msg_text[8:], user_name, "Series")

        return {"ok": True}
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return {"ok": False}

def handle_callback(query):
    try:
        chat_id = query["message"]["chat"]["id"]
        callback_data = query["data"]

        if callback_data.startswith("movie_"):
            movie_id = callback_data
            link = movie_links.get(movie_id)

            if not link:
                send_message(chat_id, "⚠️ Link expired or not found")
                return {"ok": True}

            # Scrape movie page
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(link, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")

            # Find poster image
            poster_tag = soup.select_one("div.movie-thumb img")
            poster_url = poster_tag["src"] if poster_tag else None

            # Send poster + link
            if poster_url:
                response = requests.post(f"{TELEGRAM_API}/sendPhoto", json={
                    "chat_id": chat_id,
                    "photo": poster_url,
                    "caption": f"🎬 <b>Download Link</b>:\n<a href='{link}'>{link}</a>",
                    "parse_mode": "HTML"
                }, timeout=10)
            else:
                send_message(chat_id, f"📥 <b>Download Link</b>:\n<a href='{link}'>{link}</a>")

        return {"ok": True}
    except Exception as e:
        print(f"[Callback Error] {e}")
        send_message(chat_id, "⚠️ Error fetching movie poster.")
        return {"ok": False}

def handle_search(chat_id, query, user_name, category):
    query = query.strip()
    if not query:
        return send_message(chat_id, f"❌ Please provide a {category.lower()} name.")
    text, buttons = search_filmyfly(query, category)
    return send_message(chat_id, text, buttons=buttons)

def send_message(chat_id, text, reply_to=None, buttons=None):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
        return res.json() if res.ok else None
    except Exception as e:
        print(f"[Send Message Error] {e}")
        return None

def delete_message(chat_id, message_id):
    try:
        requests.post(f"{TELEGRAM_API}/deleteMessage", json={
            "chat_id": chat_id,
            "message_id": message_id
        }, timeout=5)
    except Exception as e:
        print(f"[Delete Message Error] {e}")

def search_filmyfly(query, category):
    global movie_links
    movie_links.clear()
    try:
        url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for idx, item in enumerate(soup.select("div.A2")):
            a_tag = item.find("a", href=True)
            b_tag = item.find("b")
            if a_tag and b_tag:
                title = b_tag.text.strip()
                link = "https://filmyfly.party" + a_tag["href"]
                callback_id = f"movie_{idx}"
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

from flask import Flask, request
import requests
import os
import threading
from bs4 import BeautifulSoup

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        # Handle callback button press
        if "callback_query" in data:
            query = data["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            msg_id = query["message"]["message_id"]
            movie_url = query["data"]
            user_name = query["from"]["first_name"]

            text = f"📥 <b>Download Link</b>:\n<a href='{movie_url}'>{movie_url}</a>"
            send_message(chat_id, text)
            return {"ok": True}

        # Handle new messages
        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        user_text = msg.get("text", "").strip()
        user_name = msg.get("from", {}).get("first_name", "Friend")
        msg_id = msg.get("message_id")

        if not chat_id or not user_text:
            return {"ok": True}

        # Block external links
        if any(link in user_text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
            warning = f"⚠️ {user_name}, sharing links is not allowed."
            warn_msg = send_message(chat_id, warning, reply_to=msg_id)
            delete_message(chat_id, msg_id)

            if warn_msg:
                warn_id = warn_msg.get("result", {}).get("message_id")
                threading.Timer(10, delete_message, args=(chat_id, warn_id)).start()
            return {"ok": True}

        # Start command
        if user_text.lower() == "/start":
            welcome = (
                f"🎬 Welcome {user_name}!\n"
                "Search using:\n"
                "<code>#movie Animal</code>\n"
                "<code>#tv Breaking Bad</code>\n"
                "<code>#series Loki</code>"
            )
            send_message(chat_id, welcome)
            return {"ok": True}

        # Handle search queries
        if user_text.lower().startswith("#movie "):
            return handle_search(chat_id, user_text[7:], user_name, "Movie")
        if user_text.lower().startswith("#tv "):
            return handle_search(chat_id, user_text[4:], user_name, "TV Show")
        if user_text.lower().startswith("#series "):
            return handle_search(chat_id, user_text[8:], user_name, "Series")

        return {"ok": True}
    except Exception as e:
        print(f"Error in webhook: {e}")
        return {"ok": False}

def handle_search(chat_id, query, user_name, category):
    try:
        query = query.strip()
        if not query:
            send_message(chat_id, f"❌ Please provide a {category.lower()} name.")
            return {"ok": True}

        text, buttons = search_filmyfly(query, user_name, category)
        send_message(chat_id, text, buttons=buttons)
        return {"ok": True}
    except Exception as e:
        send_message(chat_id, f"⚠️ Error processing your request: {str(e)}")
        return {"ok": False}

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
        print(f"Error sending message: {e}")
        return None

def delete_message(chat_id, message_id):
    try:
        requests.post(f"{TELEGRAM_API}/deleteMessage", json={
            "chat_id": chat_id,
            "message_id": message_id
        }, timeout=5)
    except Exception as e:
        print(f"Error deleting message: {e}")

def search_filmyfly(query, user_name, category):
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
                results.append([{
                    "text": title,
                    "url": link  # Direct URL as callback data
                }])

            if len(results) >= 5:
                break

        if results:
            return f"🔍 {category} results for <b>{query}</b>:", results
        return f"❌ Sorry {user_name}, no {category.lower()} found for <b>{query}</b>.", []
    except Exception as e:
        print(f"Error searching FilmyFly: {e}")
        return f"⚠️ Error searching for {category.lower()}. Please try again later.", []

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

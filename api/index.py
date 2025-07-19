from flask import Flask, request
import requests, os, threading
from bs4 import BeautifulSoup

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
movie_links = {}  # callback_id → {link, title}


@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"


@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    if "callback_query" in data:
        return handle_callback(data["callback_query"])

    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_text = msg.get("text", "").strip()
    msg_id = msg.get("message_id")
    user_name = msg.get("from", {}).get("first_name", "Friend")

    if not chat_id or not msg_text:
        return {"ok": True}

    # 🚫 Block links
    if any(x in msg_text.lower() for x in ["http://", "https://", "t.me", "telegram.me"]):
        warn = f"⚠️ {user_name}, sharing links is not allowed."
        warn_msg = send_message(chat_id, warn, reply_to=msg_id)
        delete_message(chat_id, msg_id)
        if warn_msg:
            warn_id = warn_msg.get("result", {}).get("message_id")
            threading.Timer(10, delete_message, args=(chat_id, warn_id)).start()
        return {"ok": True}

    if msg_text.lower() == "/start":
        return send_message(chat_id,
            f"🎬 Welcome {user_name}!\n"
            "Search using:\n"
            "<code>#movie Animal</code>\n"
            "<code>#tv Breaking Bad</code>\n"
            "<code>#series Loki</code>"
        )

    if msg_text.lower().startswith("#movie "):
        return handle_search(chat_id, msg_text[7:], "Movie")
    if msg_text.lower().startswith("#tv "):
        return handle_search(chat_id, msg_text[4:], "TV Show")
    if msg_text.lower().startswith("#series "):
        return handle_search(chat_id, msg_text[8:], "Series")

    return {"ok": True}


def handle_callback(query):
    chat_id = query["message"]["chat"]["id"]
    callback_data = query["data"]

    movie = movie_links.get(callback_data)
    if not movie:
        send_message(chat_id, "⚠️ Link expired or not found.")
        return {"ok": True}

    link, title = movie["link"], movie["title"]
    soup = BeautifulSoup(requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).text, "html.parser")

    # 🎞️ Images
    poster_tag = soup.select_one("div.movie-thumb img")
    poster_url = poster_tag["src"] if poster_tag else None

    ss_tag = soup.select_one("div.ss img")
    ss_url = ss_tag["src"] if ss_tag else None

    # 📂 Extract Info
    def get_value(label):
        for block in soup.select("div.fname"):
            if block.contents and label.lower() in block.contents[0].lower():
                return block.select_one("div").get_text(strip=True)
        return "N/A"

    size = get_value("Size")
    language = get_value("Language")
    genre = get_value("Genre")

    # 🔗 Extract Download Link
    download_link = None
    dl_a = soup.select_one("div.dlbtn a")
    if dl_a and dl_a.get("href"):
        download_link = dl_a["href"]
    else:
        dll = soup.select_one("a > div.dll")
        if dll and dll.parent.get("href"):
            download_link = dll.parent["href"]

    caption = (
        f"<b>🎬 {title}</b>\n\n"
        f"<b>📁 Size:</b> {size}\n"
        f"<b>🈯 Language:</b> {language}\n"
        f"<b>🎭 Genre:</b> {genre}\n\n"
    )

    if download_link:
        caption += f"<a href='{download_link}'>📥 Download</a>"
    else:
        caption += f"<a href='{link}'>📥 Original Page</a>"

    # 📸 Media Group
    media = []
    if poster_url:
        media.append({
            "type": "photo",
            "media": poster_url,
            "caption": caption,
            "parse_mode": "HTML"
        })
    if ss_url:
        media.append({
            "type": "photo",
            "media": ss_url
        })

    if media:
        requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={
            "chat_id": chat_id,
            "media": media
        }, timeout=10)
    else:
        send_message(chat_id, caption)

    return {"ok": True}


def handle_search(chat_id, query, category):
    query = query.strip()
    if not query:
        return send_message(chat_id, f"❌ Please provide a {category.lower()} name.")

    url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
    soup = BeautifulSoup(requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).text, "html.parser")

    buttons = []
    for item in soup.select("div.A2"):
        a = item.find("a", href=True)
        b = item.find("b")
        if a and b:
            title = b.text.strip()
            link = "https://filmyfly.party" + a["href"]
            callback_id = f"movie_{abs(hash(title + link))}"
            movie_links[callback_id] = {"title": title, "link": link}
            buttons.append([{"text": title, "callback_data": callback_id}])
        if len(buttons) >= 10:
            break

    if buttons:
        return send_message(chat_id, f"🔍 {category} results for <b>{query}</b>:", buttons=buttons)
    return send_message(chat_id, f"❌ No {category.lower()} found for <b>{query}</b>.")


def send_message(chat_id, text, reply_to=None, buttons=None):
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


def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    }, timeout=5)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

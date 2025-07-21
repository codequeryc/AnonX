from flask import Flask, request
import requests, os, random, json, threading, base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote

app = Flask(__name__)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
XATA_API_KEY = os.getenv("XATA_API_KEY")
XATA_BASE_URL = os.getenv("XATA_BASE_URL")
BLOG_URL = os.getenv("BLOG_URL")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Configurations
MOVIE_LINK_EXPIRY = timedelta(minutes=60)
movie_links = {}


# Helpers
def btoa(s): return base64.b64encode(s.encode()).decode()
def now(): return datetime.now()

# Flask Routes
@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    if "callback_query" in data:
        return handle_callback(data["callback_query"])

    msg = data.get("message", {})
    chat_id, text, msg_id = msg.get("chat", {}).get("id"), msg.get("text", "").strip(), msg.get("message_id")
    user = msg.get("from", {}).get("first_name", "Friend")

    if "new_chat_members" in msg:
        for m in msg["new_chat_members"]:
            send_help(chat_id, m.get("first_name", "Friend"))
        return {"ok": True}

    if not chat_id or not text:
        return {"ok": True}

    if any(x in text.lower() for x in ["http://", "https://", "t.me", "telegram.me"]):
        reply = send_message(chat_id, f"⚠️ {user}, sharing links is not allowed.", reply_to=msg_id)
        delete_message(chat_id, msg_id)
        if reply:
            threading.Timer(10, delete_message, args=(chat_id, reply["result"]["message_id"])).start()
        return {"ok": True}

    if text.lower() in ["/start", "/help", "help"]:
        return send_help(chat_id, user)

    for prefix, label in [("#movie ", "Movie"), ("#tv ", "TV Show"), ("#series ", "Series")]:
        if text.lower().startswith(prefix):
            return handle_search(chat_id, text[len(prefix):], label, msg_id)

    return {"ok": True}

# Core Handlers
def send_help(chat_id, name):
    return send_message(chat_id, f"""👋 <b>Welcome, {name}!</b>

🎬 <b>Search Movies & Series:</b>
🎥 <code>#movie Animal</code>
📺 <code>#tv Breaking Bad</code>
🎝️ <code>#series Loki</code>

✨ I'll find HD download links for you!
    """)

def handle_search(chat_id, query, label, user_msg_id):
    query, base_url = query.strip(), get_base_url()
    if not query or not base_url:
        return send_message(chat_id, f"❌ Provide a {label.lower()} name or base URL not found.", reply_to=user_msg_id)

    try:
        url = f"{base_url}/site-1.html?to-search={quote(query)}"
        soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=10).text, "html.parser")
    except:
        return send_message(chat_id, "❌ Failed to search. Try again later.", reply_to=user_msg_id)

    buttons = []
    for item in soup.select("div.A2")[:10]:
        a, b = item.find("a", href=True), item.find("b")
        if a and b:
            title, link = b.text.strip(), base_url + a["href"]
            cid = f"movie_{abs(hash(title + link))}"
            movie_links[cid] = {"title": title, "link": link, "timestamp": now(), "disabled": False}
            buttons.append([{"text": title, "callback_data": cid}])

    msg = f"🔎 <b>{label}</b> results for <code>{query}</code>:" if buttons else f"🚫 <b>No {label.lower()} found</b> for <code>{query}</code>.\n📝 Please check your spelling or try a different keyword."
    result = send_message(chat_id, msg + "\n\n⌛ <i><b>Note:</b> This message will auto-delete in 1 hour.</i>", buttons=buttons, reply_to=user_msg_id)

    if result and "result" in result:
        schedule_deletion(chat_id, user_msg_id, result["result"]["message_id"])

    return result

# Utilities
def schedule_deletion(chat_id, user_msg_id, bot_msg_id, delay=3600):
    def delete():
        delete_message(chat_id, user_msg_id)
        delete_message(chat_id, bot_msg_id)
    threading.Timer(delay, delete).start()

def handle_callback(query):
    chat_id, message_id, data = query["message"]["chat"]["id"], query["message"]["message_id"], query["data"]
    if data.startswith("disabled_"):
        return answer_callback(query["id"], "⚠️ This link has been already sent.")

    movie = movie_links.get(data)
    if not movie or now() - movie["timestamp"] > MOVIE_LINK_EXPIRY or movie["disabled"]:
        edit_button_to_disabled(chat_id, message_id, data)
        movie_links.pop(data, None)
        return answer_callback(query["id"], "⚠️ This link has been already sent.")

    movie["disabled"] = True
    edit_button_to_disabled(chat_id, message_id, data)
    try:
        soup = BeautifulSoup(requests.get(movie["link"], headers=HEADERS, timeout=10).text, "html.parser")
        poster = soup.select_one("div.movie-thumb img")
        ss = soup.select_one("div.ss img")
        size = get_info(soup, "Size")
        lang = get_info(soup, "Language")
        genre = get_info(soup, "Genre")
        download = soup.select_one("div.dlbtn a") or soup.select_one("a > div.dll")
        download_link = download.get("href") if download else movie["link"]

        final_url = f"{get_random_blogger_post()}?id={btoa(download_link)}" if get_random_blogger_post() else download_link
        caption = f"""🎬 <b>{movie['title']}</b>
━━━━━━━━━━━━━━━━━━━
<b>📁 Size:</b> <code>{size}</code>
<b>🇨 Language:</b> <code>{lang}</code>
<b>🎭 Genre:</b> <code>{genre}</code>
━━━━━━━━━━━━━━━━━━━
🔗 <a href='{final_url}'><b>👅 Download Now</b></a>
"""

        media = []
        if poster: media.append({"type": "photo", "media": poster["src"], "caption": caption, "parse_mode": "HTML"})
        if ss: media.append({"type": "photo", "media": ss["src"]})

        if media:
            requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={"chat_id": chat_id, "media": media}, timeout=10)
        else:
            send_message(chat_id, caption)

        return answer_callback(query["id"])
    except:
        return answer_callback(query["id"], "❌ Failed to process request.")

def get_info(soup, label):
    for div in soup.select("div.fname"):
        if div.contents and label.lower() in div.contents[0].lower():
            return div.select_one("div").get_text(strip=True)
    return "N/A"

def get_base_url():
    try:
        url = f"{XATA_BASE_URL}/tables/domains/query"
        headers = {
            "Authorization": f"Bearer {XATA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"filter": {"uid": "abc12"}, "columns": ["url"]}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status()

        records = res.json().get("records", [])
        if not records:
            return None

        original_url = records[0]["url"].rstrip("/")
        record_id = records[0]["id"]

        try:
            final_url = requests.get(original_url, headers=HEADERS, timeout=10).url.rstrip("/")
        except:
            final_url = original_url

        if final_url != original_url:
            patch_url = f"{XATA_BASE_URL}/tables/domains/data/{record_id}"
            requests.patch(patch_url, headers=headers, json={"url": final_url}, timeout=10)

        return final_url
    except:
        return None

def get_random_blogger_post():
    if not BLOG_URL:
        return None
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=json"
        res = requests.get(feed_url, headers=HEADERS, timeout=10)
        data = res.json()

        entries = data.get("feed", {}).get("entry", [])
        links = [
            link.get("href")
            for entry in entries
            for link in entry.get("link", [])
            if link.get("rel") == "alternate" and link.get("href")
        ]

        return random.choice(links) if links else None
    except:
        return None

def send_message(chat_id, text, reply_to=None, buttons=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    if reply_to: payload["reply_to_message_id"] = reply_to
    if buttons: payload["reply_markup"] = {"inline_keyboard": buttons}
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
    return r.json() if r.ok else None

def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=5)

def edit_button_to_disabled(chat_id, message_id, callback_data):
    try:
        markup = {"inline_keyboard": [[{**btn, "text": "❌ " + btn["text"], "callback_data": "disabled_" + callback_data}
                                         if btn.get("callback_data") == callback_data else btn for btn in row]
                                        for row in requests.post(f"{TELEGRAM_API}/getChatMessage",
                                        json={"chat_id": chat_id, "message_id": message_id}, timeout=5).json()
                                        ["result"].get("reply_markup", {}).get("inline_keyboard", [])]}
        requests.post(f"{TELEGRAM_API}/editMessageReplyMarkup",
                      json={"chat_id": chat_id, "message_id": message_id, "reply_markup": markup}, timeout=5)
    except: pass

def answer_callback(callback_id, text=None):
    payload = {"callback_query_id": callback_id}
    if text: payload.update({"text": text, "show_alert": True})
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json=payload, timeout=5)
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

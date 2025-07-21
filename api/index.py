from flask import Flask, request
import requests, os, random, json, threading, base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse
import hashlib

app = Flask(__name__)

# Env vars
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")
BLOG_URL = os.environ.get("BLOG_URL")
MAX_RESULTS = 10
CALLBACK_DATA_MAX_SIZE = 64

blogger_cache = {
    'last_fetched': None,
    'posts': [],
    'expiry': timedelta(hours=1)
}

def btoa(string):
    return base64.urlsafe_b64encode(string.encode()).decode().rstrip("=")

def atob(string):
    padding = len(string) % 4
    if padding:
        string += "=" * (4 - padding)
    return base64.urlsafe_b64decode(string).decode()

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)

        if "callback_query" in data:
            return handle_callback(data["callback_query"])

        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()
        msg_id = msg.get("message_id")
        user = msg.get("from", {}).get("first_name", "Friend")

        if "new_chat_members" in msg:
            for m in msg["new_chat_members"]:
                send_help(chat_id, m.get("first_name", "Friend"))
            return {"ok": True}

        if not chat_id or not text:
            return {"ok": True}

        if any(x in text.lower() for x in ["http://", "https://", "t.me", "telegram.me"]):
            warn = f"⚠️ {user}, sharing links is not allowed."
            reply = send_message(chat_id, warn, reply_to=msg_id)
            delete_message(chat_id, msg_id)
            if reply:
                threading.Timer(10, delete_message, args=(chat_id, reply["result"]["message_id"])).start()
            return {"ok": True}

        if text.lower() in ["/start", "/help", "help"]:
            return send_help(chat_id, user)

        if text.lower().startswith("#movie "):
            return handle_search(chat_id, text[7:], "Movie")
        if text.lower().startswith("#tv "):
            return handle_search(chat_id, text[4:], "TV Show")
        if text.lower().startswith("#series "):
            return handle_search(chat_id, text[8:], "Series")

        return {"ok": True}

    except Exception as e:
        print(f"[ERROR webhook] {e}")
        return {"ok": False, "error": str(e)}, 500

def send_help(chat_id, name):
    return send_message(chat_id,
        f"👋 <b>Welcome, {name}!</b>\n\n"
        "🎬 <b>Search Movies & Series:</b>\n"
        "🎥 <code>#movie Animal</code>\n"
        "📺 <code>#tv Breaking Bad</code>\n"
        "📽️ <code>#series Loki</code>\n\n"
        "✨ I'll find HD download links for you!"
    )

def get_random_blogger_post():
    global blogger_cache
    if not BLOG_URL:
        return None
    try:
        if blogger_cache['last_fetched'] and datetime.now() - blogger_cache['last_fetched'] < blogger_cache['expiry']:
            return random.choice(blogger_cache['posts'])

        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=json"
        data = requests.get(feed_url, headers=HEADERS, timeout=10).json()
        posts = [l["href"] for e in data['feed'].get('entry', []) for l in e.get("link", []) if l["rel"] == "alternate"]
        blogger_cache.update({"posts": posts, "last_fetched": datetime.now()})
        return random.choice(posts) if posts else None
    except Exception as e:
        print(f"[ERROR blogger] {e}")
        return None

def get_base_url():
    try:
        url = f"{XATA_BASE_URL}/tables/domains/query"
        headers = {
            "Authorization": f"Bearer {XATA_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {"filter": {"uid": "abc12"}, "columns": ["url"]}
        res = requests.post(url, headers=headers, json=payload, timeout=10).json()
        if not res.get("records"):
            return None
        record = res["records"][0]
        original_url = record["url"].rstrip("/")
        final_url = requests.get(original_url, headers=HEADERS, timeout=10).url.rstrip("/")
        if final_url != original_url:
            patch_url = f"{XATA_BASE_URL}/tables/domains/data/{record['id']}"
            requests.patch(patch_url, headers=headers, json={"url": final_url}, timeout=10)
        return final_url
    except Exception as e:
        print(f"[ERROR get_base_url] {e}")
        return None

def validate_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def handle_search(chat_id, query, label):
    try:
        query = query.strip()
        if not query:
            return send_message(chat_id, f"❌ Provide a {label.lower()} name.")

        base_url = get_base_url()
        if not base_url:
            return send_message(chat_id, "❌ Service unavailable. Please try again later.")

        search_url = f"{base_url}/site-1.html?to-search={quote(query)}"
        soup = BeautifulSoup(requests.get(search_url, headers=HEADERS, timeout=15).text, "html.parser")

        buttons = []
        for item in soup.select("div.A2")[:MAX_RESULTS]:
            a = item.find("a", href=True)
            b = item.find("b")
            if a and b:
                title = b.text.strip()[:50]
                link = base_url + a["href"]
                callback_data = btoa(json.dumps({"t": title, "u": link[len(base_url):]}))
                if len(callback_data) > CALLBACK_DATA_MAX_SIZE:
                    callback_data = btoa(json.dumps({"t": title, "h": hashlib.md5(link.encode()).hexdigest()}))
                buttons.append([{"text": title, "callback_data": callback_data}])

        msg = f"🔍 {label} results for <b>{query}</b>:" if buttons else f"❌ No {label.lower()} found."
        return send_message(chat_id, msg, buttons=buttons)

    except Exception as e:
        print(f"[ERROR search] {e}")
        return send_message(chat_id, "❌ An error occurred. Please try again.")

def handle_callback(query):
    try:
        chat_id = query["message"]["chat"]["id"]
        encoded = query["data"]
        data = json.loads(atob(encoded))

        base_url = get_base_url()
        if not base_url:
            return send_message(chat_id, "❌ Service unavailable. Try again later.")

        if "u" in data:
            title = data["t"]
            link = base_url + data["u"]
        else:
            return send_message(chat_id, "⚠️ Link expired or unavailable.")

        if not validate_url(link):
            return send_message(chat_id, "⚠️ Invalid URL detected.")

        soup = BeautifulSoup(requests.get(link, headers=HEADERS, timeout=15).text, "html.parser")
        poster = soup.select_one("div.movie-thumb img[src]")
        ss = soup.select_one("div.ss img[src]")
        size = get_info(soup, "Size")
        lang = get_info(soup, "Language")
        genre = get_info(soup, "Genre")

        download = soup.select_one("div.dlbtn a[href]") or soup.select_one("a[href] > div.dll")
        download_link = download["href"] if download else link
        if not validate_url(download_link):
            download_link = link

        blog_post = get_random_blogger_post()
        if blog_post:
            encoded_url = btoa(download_link)
            final_url = f"{blog_post}?url={encoded_url}"
        else:
            final_url = download_link

        caption = (
            f"🎬 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>📁 Size:</b> <code>{size}</code>\n"
            f"<b>🈯 Language:</b> <code>{lang}</code>\n"
            f"<b>🎭 Genre:</b> <code>{genre}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='{final_url}'><b>📥 Download Now</b></a>"
        )

        media = []
        if poster:
            media.append({"type": "photo", "media": poster["src"], "caption": caption, "parse_mode": "HTML"})
        if ss:
            media.append({"type": "photo", "media": ss["src"]})

        if media:
            requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={"chat_id": chat_id, "media": media}, timeout=15)
        else:
            send_message(chat_id, caption)

        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={"callback_query_id": query["id"]}, timeout=5)
        return {"ok": True}

    except Exception as e:
        print(f"[ERROR callback] {e}")
        return send_message(chat_id, "⚠️ Error processing request.")

def get_info(soup, label):
    try:
        for div in soup.select("div.fname"):
            if div.contents and label.lower() in div.contents[0].lower():
                return div.select_one("div").get_text(strip=True)
    except:
        return "N/A"
    return "N/A"

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
        print(f"[ERROR send_message] {e}")
        return None

def delete_message(chat_id, msg_id):
    try:
        requests.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": msg_id}, timeout=5)
    except Exception as e:
        print(f"[ERROR delete_message] {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

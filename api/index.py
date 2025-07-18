from flask import Flask, request
import requests, os, random, json, threading, base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote

app = Flask(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")
BLOG_URL = os.environ.get("BLOG_URL")

# Global variables
movie_links = {}
blogger_cache = {
    'last_fetched': None,
    'posts': [],
    'expiry': timedelta(hours=1)
}

# Base64 encode (btoa equivalent)
def btoa(string):
    return base64.b64encode(string.encode()).decode()

def get_random_blogger_post():
    global blogger_cache
    if not BLOG_URL:
        return None
    try:
        if (
            blogger_cache['last_fetched'] and
            datetime.now() - blogger_cache['last_fetched'] < blogger_cache['expiry'] and
            blogger_cache['posts']
        ):
            return random.choice(blogger_cache['posts'])

        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=json"
        response = requests.get(feed_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()

        posts = []
        for entry in data['feed'].get('entry', []):
            for link in entry.get('link', []):
                if link.get('rel') == 'alternate' and link.get('type') == 'text/html':
                    posts.append(link['href'])
                    break

        blogger_cache['posts'] = posts
        blogger_cache['last_fetched'] = datetime.now()

        return random.choice(posts) if posts else None
    except Exception as e:
        print(f"Error fetching Blogger JSON feed: {e}")
        return None

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

@app.route("/", methods=["GET"])
def home():
    return f"🤖 Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
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

def send_help(chat_id, name):
    return send_message(chat_id,
        f"👋 <b>Welcome, {name}!</b>\n\n"
        "🎬 <b>Search Movies & Series:</b>\n"
        "🎥 <code>#movie Animal</code>\n"
        "📺 <code>#tv Breaking Bad</code>\n"
        "📽️ <code>#series Loki</code>\n\n"
        "✨ I'll find HD download links for you!"
    )

def handle_search(chat_id, query, label):
    query = query.strip()
    if not query:
        return send_message(chat_id, f"❌ Provide a {label.lower()} name.")

    base_url = get_base_url()
    if not base_url:
        return send_message(chat_id, "❌ Base URL not found.")

    url = f"{base_url}/site-1.html?to-search={query.replace(' ', '+')}"
    soup = BeautifulSoup(requests.get(url, headers=HEADERS, timeout=10).text, "html.parser")

    buttons = []
    for item in soup.select("div.A2"):
        a, b = item.find("a", href=True), item.find("b")
        if a and b:
            title = b.text.strip()
            link = base_url + a["href"]
            cid = f"movie_{abs(hash(title + link))}"
            movie_links[cid] = {"title": title, "link": link}
            buttons.append([{"text": title, "callback_data": cid}])
        if len(buttons) >= 10:
            break

    msg = f"🔍 {label} results for <b>{query}</b>:" if buttons else f"❌ No {label.lower()} found."
    return send_message(chat_id, msg, buttons=buttons)

def handle_callback(query):
    chat_id = query["message"]["chat"]["id"]
    data = query["data"]
    movie = movie_links.get(data)

    if not movie:
        return send_message(chat_id, "⚠️ Link expired or not found.")

    link, title = movie["link"], movie["title"]
    soup = BeautifulSoup(requests.get(link, headers=HEADERS, timeout=10).text, "html.parser")

    poster = soup.select_one("div.movie-thumb img")
    ss = soup.select_one("div.ss img")
    size = get_info(soup, "Size")
    lang = get_info(soup, "Language")
    genre = get_info(soup, "Genre")

    download = soup.select_one("div.dlbtn a") or soup.select_one("a > div.dll")
    download_link = download["href"] if download and download.get("href") else link

    blog_post = get_random_blogger_post()
    if blog_post:
        encoded = btoa(download_link)
        final_url = f"{blog_post}?url={encoded}"
    else:
        final_url = download_link

    caption = (
        f"🎬 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📁 Size:</b> <code>{size}</code>\n"
        f"<b>🈯 Language:</b> <code>{lang}</code>\n"
        f"<b>🎭 Genre:</b> <code>{genre}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href='{final_url}'><b>📥 Download Now</b></a>\n"
    )

    media = []
    if poster:
        media.append({"type": "photo", "media": poster["src"], "caption": caption, "parse_mode": "HTML"})
    if ss:
        media.append({"type": "photo", "media": ss["src"]})

    if media:
        requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={"chat_id": chat_id, "media": media}, timeout=10)
    else:
        send_message(chat_id, caption)

    return {"ok": True}

def get_info(soup, label):
    for div in soup.select("div.fname"):
        if div.contents and label.lower() in div.contents[0].lower():
            return div.select_one("div").get_text(strip=True)
    return "N/A"

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
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
    return r.json() if r.ok else None

def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=5)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

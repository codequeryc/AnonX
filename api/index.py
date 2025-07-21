from flask import Flask, request
import requests, os, random, json, threading, base64
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse
import hashlib

app = Flask(__name__)

# Environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")
BLOG_URL = os.environ.get("BLOG_URL")
MAX_RESULTS = 10  # Maximum number of results to show
CALLBACK_DATA_MAX_SIZE = 64  # Telegram's callback_data size limit

# Global variables
blogger_cache = {
    'last_fetched': None,
    'posts': [],
    'expiry': timedelta(hours=1)
}

def btoa(string):
    """Base64 encode (btoa equivalent) with URL-safe encoding"""
    return base64.urlsafe_b64encode(string.encode()).decode().rstrip("=")

def atob(string):
    """Base64 decode (atob equivalent) with URL-safe encoding"""
    padding = len(string) % 4
    if padding:
        string += "=" * (4 - padding)
    return base64.urlsafe_b64decode(string).decode()

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
    except Exception as e:
        print(f"Error getting base URL: {e}")
        return None

def validate_url(url):
    """Validate and sanitize URLs"""
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            return url
        return None
    except:
        return None

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

        # Check for links in message
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
        print(f"Error in webhook: {e}")
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

def handle_search(chat_id, query, label):
    try:
        query = query.strip()
        if not query:
            return send_message(chat_id, f"❌ Provide a {label.lower()} name.")

        base_url = get_base_url()
        if not base_url:
            return send_message(chat_id, "❌ Service unavailable. Please try again later.")

        search_url = f"{base_url}/site-1.html?to-search={quote(query)}"
        try:
            response = requests.get(search_url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            print(f"Error fetching search results: {e}")
            return send_message(chat_id, "❌ Error fetching results. Please try again.")

        buttons = []
        for item in soup.select("div.A2")[:MAX_RESULTS]:  # Limit to MAX_RESULTS
            a = item.find("a", href=True)
            b = item.find("b")
            
            if a and b:
                title = b.text.strip()[:50]  # Limit title length
                link = base_url + a["href"]
                
                # Create compact callback data
                callback_data = {
                    "t": title,
                    "u": link[len(base_url):]  # Store relative URL to save space
                }
                
                # Convert to JSON and base64
                json_data = json.dumps(callback_data)
                encoded_data = btoa(json_data)
                
                # Check if it fits Telegram's callback_data limit
                if len(encoded_data) <= CALLBACK_DATA_MAX_SIZE:
                    buttons.append([{"text": title, "callback_data": encoded_data}])
                else:
                    # Fallback for long URLs - use hash instead
                    url_hash = hashlib.md5(link.encode()).hexdigest()
                    callback_data = {"h": url_hash, "t": title}
                    encoded_data = btoa(json.dumps(callback_data))
                    buttons.append([{"text": title, "callback_data": encoded_data}])

        msg = f"🔍 {label} results for <b>{query}</b>:" if buttons else f"❌ No {label.lower()} found."
        return send_message(chat_id, msg, buttons=buttons)
    except Exception as e:
        print(f"Error in handle_search: {e}")
        return send_message(chat_id, "❌ An error occurred. Please try again.")

def handle_callback(query):
    try:
        chat_id = query["message"]["chat"]["id"]
        message_id = query["message"]["message_id"]
        encoded_data = query["data"]
        
        try:
            # Decode the callback data
            decoded_data = json.loads(atob(encoded_data))
            
            base_url = get_base_url()
            if not base_url:
                return send_message(chat_id, "❌ Service unavailable. Please try again later.")
            
            if "u" in decoded_data:  # Normal case with relative URL
                relative_url = decoded_data["u"]
                title = decoded_data["t"]
                link = base_url + relative_url
            elif "h" in decoded_data:  # Fallback case with hash
                title = decoded_data["t"]
                # In a real implementation, you'd need to store these hashes
                return send_message(chat_id, "⚠️ This result is no longer available. Please search again.")
            else:
                return send_message(chat_id, "⚠️ Invalid data format.")
            
            # Validate the URL before processing
            if not validate_url(link):
                return send_message(chat_id, "⚠️ Invalid URL detected.")
            
            try:
                response = requests.get(link, headers=HEADERS, timeout=15)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            except Exception as e:
                print(f"Error fetching movie page: {e}")
                return send_message(chat_id, "❌ Error loading content. Please try again.")

            # Extract movie details
            poster = soup.select_one("div.movie-thumb img[src]")
            ss = soup.select_one("div.ss img[src]")
            size = get_info(soup, "Size") or "N/A"
            lang = get_info(soup, "Language") or "N/A"
            genre = get_info(soup, "Genre") or "N/A"

            # Find download link
            download = (soup.select_one("div.dlbtn a[href]") or 
                        soup.select_one("a[href] > div.dll"))
            download_link = download["href"] if download else link
            
            # Validate download link
            if not validate_url(download_link):
                download_link = link

            # Use blogger post if available
            blog_post = get_random_blogger_post()
            if blog_post:
                encoded_url = btoa(download_link)
                final_url = f"{blog_post}?url={encoded_url}"
            else:
                final_url = download_link

            # Prepare caption
            caption = (
                f"🎬 <b>{title}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<b>📁 Size:</b> <code>{size}</code>\n"
                f"<b>🈯 Language:</b> <code>{lang}</code>\n"
                f"<b>🎭 Genre:</b> <code>{genre}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🔗 <a href='{final_url}'><b>📥 Download Now</b></a>\n"
            )

            # Prepare media
            media = []
            if poster:
                media.append({
                    "type": "photo", 
                    "media": poster["src"], 
                    "caption": caption, 
                    "parse_mode": "HTML"
                })
            if ss:
                media.append({
                    "type": "photo", 
                    "media": ss["src"]
                })

            if media:
                # Send media group
                requests.post(
                    f"{TELEGRAM_API}/sendMediaGroup",
                    json={"chat_id": chat_id, "media": media},
                    timeout=15
                )
            else:
                # Fallback to text message
                send_message(chat_id, caption)

            # Answer the callback query to remove loading indicator
            requests.post(
                f"{TELEGRAM_API}/answerCallbackQuery",
                json={"callback_query_id": query["id"]},
                timeout=5
            )

            return {"ok": True}
        except Exception as e:
            print(f"Error decoding callback data: {e}")
            return send_message(chat_id, "⚠️ Invalid or expired link.")
    except Exception as e:
        print(f"Error in handle_callback: {e}")
        return {"ok": False, "error": str(e)}, 500

def get_info(soup, label):
    try:
        for div in soup.select("div.fname"):
            if div.contents and label.lower() in div.contents[0].lower():
                info_div = div.select_one("div")
                return info_div.get_text(strip=True) if info_div else "N/A"
        return "N/A"
    except:
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
        
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

def delete_message(chat_id, message_id):
    try:
        requests.post(
            f"{TELEGRAM_API}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
            timeout=5
        )
    except Exception as e:
        print(f"Error deleting message: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

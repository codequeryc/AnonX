from flask import Flask, request, abort
import requests, os, random, json, threading, base64, logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import quote
from functools import wraps
from typing import Optional, Dict, List, Tuple, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
CONFIG = {
    "BOT_TOKEN": os.environ.get("BOT_TOKEN"),
    "XATA_API_KEY": os.environ.get("XATA_API_KEY"),
    "XATA_BASE_URL": os.environ.get("XATA_BASE_URL"),
    "BLOG_URL": os.environ.get("BLOG_URL"),
    "TELEGRAM_API": f"https://api.telegram.org/bot{os.environ.get('BOT_TOKEN')}",
    "HEADERS": {"User-Agent": "Mozilla/5.0"},
    "MOVIE_LINK_EXPIRY": timedelta(minutes=60),
    "BLOGGER_CACHE_EXPIRY": timedelta(hours=1),
    "MESSAGE_DELETE_DELAY": 3600,  # 1 hour in seconds
    "MAX_SEARCH_RESULTS": 10,
    "REQUEST_TIMEOUT": 15,
}

# Global state
state = {
    "movie_links": {},
    "blogger_cache": {'last_fetched': None, 'posts': []},
}

def rate_limited(max_per_minute: int = 30):
    """Simple rate limiting decorator"""
    last_called = []
    
    @wraps(rate_limited)
    def wrapper(f):
        def inner(*args, **kwargs):
            now = datetime.now()
            # Remove calls older than 1 minute
            last_called[:] = [call for call in last_called if now - call < timedelta(minutes=1)]
            
            if len(last_called) >= max_per_minute:
                logger.warning(f"Rate limit exceeded ({max_per_minute} calls/minute)")
                abort(429, "Too many requests")
                
            last_called.append(now)
            return f(*args, **kwargs)
        return inner
    return wrapper

def btoa(string: str) -> str:
    """Base64 encode a string"""
    return base64.b64encode(string.encode()).decode()

def make_telegram_request(method: str, payload: Dict) -> Optional[Dict]:
    """Make a request to Telegram API with error handling"""
    try:
        response = requests.post(
            f"{CONFIG['TELEGRAM_API']}/{method}",
            json=payload,
            timeout=CONFIG['REQUEST_TIMEOUT']
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram API request failed: {e}")
        return None

def schedule_deletion(chat_id: int, message_ids: List[int], delay: int = CONFIG['MESSAGE_DELETE_DELAY']) -> None:
    """Schedule message deletion after a delay"""
    def delete():
        for msg_id in message_ids:
            try:
                delete_message(chat_id, msg_id)
            except Exception as e:
                logger.error(f"Failed to delete message {msg_id}: {e}")
    
    threading.Timer(delay, delete).start()

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Running!"

@app.route("/", methods=["POST"])
@rate_limited()
def webhook():
    try:
        data = request.get_json(force=True)
        logger.debug(f"Received update: {json.dumps(data, indent=2)}")

        if "callback_query" in data:
            return handle_callback(data["callback_query"])

        msg = data.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "").strip()
        msg_id = msg.get("message_id")
        user = msg.get("from", {}).get("first_name", "Friend")

        if not chat_id or not text:
            return {"ok": True}

        if "new_chat_members" in msg:
            for member in msg["new_chat_members"]:
                send_help(chat_id, member.get("first_name", "Friend"))
            return {"ok": True}

        if any(domain in text.lower() for domain in ["http://", "https://", "t.me", "telegram.me"]):
            warn = f"⚠️ {user}, sharing links is not allowed."
            reply = send_message(chat_id, warn, reply_to=msg_id)
            delete_message(chat_id, msg_id)
            if reply:
                schedule_deletion(chat_id, [reply["result"]["message_id"]], delay=10)
            return {"ok": True}

        text_lower = text.lower()
        if text_lower in ["/start", "/help", "help"]:
            return send_help(chat_id, user)
        elif text_lower.startswith("#movie "):
            return handle_search(chat_id, text[7:], "Movie", msg_id)
        elif text_lower.startswith("#tv "):
            return handle_search(chat_id, text[4:], "TV Show", msg_id)
        elif text_lower.startswith("#series "):
            return handle_search(chat_id, text[8:], "Series", msg_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"ok": False, "error": str(e)}, 500

def send_help(chat_id: int, name: str) -> Dict:
    """Send help message with usage instructions"""
    help_text = (
        f"👋 <b>Welcome, {name}!</b>\n\n"
        "🎬 <b>Search Movies & Series:</b>\n"
        "🎥 <code>#movie Animal</code>\n"
        "📺 <code>#tv Breaking Bad</code>\n"
        "📽️ <code>#series Loki</code>\n\n"
        "✨ I'll find HD download links for you!"
    )
    return send_message(chat_id, help_text)

def handle_search(chat_id: int, query: str, label: str, user_msg_id: int) -> Dict:
    """Handle search requests for movies/TV shows"""
    query = query.strip()
    if not query:
        return send_message(chat_id, f"❌ Provide a {label.lower()} name.")

    base_url = get_base_url()
    if not base_url:
        return send_message(chat_id, "❌ Service temporarily unavailable. Please try again later.")

    try:
        url = f"{base_url}/site-1.html?to-search={quote(query)}"
        response = requests.get(url, headers=CONFIG['HEADERS'], timeout=CONFIG['REQUEST_TIMEOUT'])
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        buttons = []
        for idx, item in enumerate(soup.select("div.A2")):
            if idx >= CONFIG['MAX_SEARCH_RESULTS']:
                break
                
            a, b = item.find("a", href=True), item.find("b")
            if a and b:
                title = b.text.strip()
                link = base_url + a["href"]
                cid = f"movie_{abs(hash(title + link))}"
                
                state["movie_links"][cid] = {
                    "title": title,
                    "link": link,
                    "timestamp": datetime.now(),
                    "type": label.lower()
                }
                
                buttons.append([{"text": title, "callback_data": cid}])

        if not buttons:
            return send_message(chat_id, f"❌ No {label.lower()} found for '{query}'.")

        msg = f"🔍 {label} results for <b>{query}</b>:\n🕒 <i>This results will auto-delete in 1 hour</i>"
        result = send_message(chat_id, msg, buttons=buttons)

        if result and "result" in result:
            schedule_deletion(chat_id, [user_msg_id, result["result"]["message_id"]])

        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Search request failed: {e}")
        return send_message(chat_id, "❌ Service temporarily unavailable. Please try again later.")

def handle_callback(query: Dict) -> Dict:
    """Handle callback queries from inline buttons"""
    chat_id = query["message"]["chat"]["id"]
    data = query["data"]
    message_id = query["message"]["message_id"]
    movie = state["movie_links"].get(data)

    # Check for expiry
    if not movie or datetime.now() - movie.get("timestamp", datetime.min) > CONFIG['MOVIE_LINK_EXPIRY']:
        state["movie_links"].pop(data, None)
        return send_message(chat_id, "⚠️ This link has expired. Please search again.")

    try:
        response = requests.get(
            movie["link"], 
            headers=CONFIG['HEADERS'], 
            timeout=CONFIG['REQUEST_TIMEOUT']
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract metadata
        poster = soup.select_one("div.movie-thumb img")
        ss = soup.select_one("div.ss img")
        size = get_info(soup, "Size")
        lang = get_info(soup, "Language")
        genre = get_info(soup, "Genre")
        quality = get_info(soup, "Quality") or "HD"

        # Find download link
        download = soup.select_one("div.dlbtn a") or soup.select_one("a > div.dll")
        download_link = download["href"] if download and download.get("href") else movie["link"]

        # Use blog URL if available
        blog_post = get_random_blogger_post()
        if blog_post:
            encoded = btoa(download_link)
            final_url = f"{blog_post}?url={encoded}"
        else:
            final_url = download_link

        # Prepare caption
        caption = (
            f"🎬 <b>{movie['title']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"<b>📁 Size:</b> <code>{size}</code>\n"
            f"<b>🈯 Language:</b> <code>{lang}</code>\n"
            f"<b>🎭 Genre:</b> <code>{genre}</code>\n"
            f"<b>📺 Quality:</b> <code>{quality}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='{final_url}'><b>📥 Download Now</b></a>\n"
        )

        # Send media group if we have images
        media = []
        if poster:
            media.append({
                "type": "photo", 
                "media": poster["src"], 
                "caption": caption, 
                "parse_mode": "HTML"
            })
        if ss:
            media.append({"type": "photo", "media": ss["src"]})

        if media:
            requests.post(
                f"{CONFIG['TELEGRAM_API']}/sendMediaGroup",
                json={"chat_id": chat_id, "media": media},
                timeout=CONFIG['REQUEST_TIMEOUT']
            )
        else:
            send_message(chat_id, caption)

        # Delete the original results message
        delete_message(chat_id, message_id)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        return send_message(chat_id, "❌ Failed to fetch details. Please try again.")

def get_info(soup: BeautifulSoup, label: str) -> str:
    """Extract information from the soup based on label"""
    for div in soup.select("div.fname"):
        if div.contents and label.lower() in div.contents[0].lower():
            value = div.select_one("div").get_text(strip=True)
            return value if value else "N/A"
    return "N/A"

def get_random_blogger_post() -> Optional[str]:
    """Get a random post from Blogger cache"""
    if not CONFIG['BLOG_URL']:
        return None

    try:
        cache = state["blogger_cache"]
        
        # Return cached posts if still valid
        if (cache['last_fetched'] and 
            datetime.now() - cache['last_fetched'] < CONFIG['BLOGGER_CACHE_EXPIRY'] and 
            cache['posts']):
            return random.choice(cache['posts'])

        # Fetch fresh posts
        feed_url = f"{CONFIG['BLOG_URL']}/feeds/posts/default?alt=json&max-results=50"
        response = requests.get(feed_url, headers=CONFIG['HEADERS'], timeout=CONFIG['REQUEST_TIMEOUT'])
        response.raise_for_status()
        data = response.json()

        posts = []
        for entry in data['feed'].get('entry', []):
            for link in entry.get('link', []):
                if link.get('rel') == 'alternate' and link.get('type') == 'text/html':
                    posts.append(link['href'])
                    break

        # Update cache
        state["blogger_cache"] = {
            'posts': posts,
            'last_fetched': datetime.now()
        }

        return random.choice(posts) if posts else None
    except Exception as e:
        logger.error(f"Error fetching Blogger JSON feed: {e}")
        return None

def get_base_url() -> Optional[str]:
    """Get the base URL from Xata database with caching"""
    if not CONFIG['XATA_API_KEY'] or not CONFIG['XATA_BASE_URL']:
        return None

    try:
        url = f"{CONFIG['XATA_BASE_URL']}/tables/domains/query"
        headers = {
            "Authorization": f"Bearer {CONFIG['XATA_API_KEY']}",
            "Content-Type": "application/json"
        }
        payload = {"filter": {"uid": "abc12"}, "columns": ["url", "id"]}
        
        response = requests.post(url, headers=headers, json=payload, timeout=CONFIG['REQUEST_TIMEOUT'])
        response.raise_for_status()
        
        records = response.json().get("records", [])
        if not records:
            return None

        record = records[0]
        original_url = record["url"].rstrip("/")
        record_id = record["id"]

        # Try to resolve final URL
        try:
            final_url = requests.get(
                original_url, 
                headers=CONFIG['HEADERS'], 
                timeout=CONFIG['REQUEST_TIMEOUT'],
                allow_redirects=True
            ).url.rstrip("/")
        except:
            final_url = original_url

        # Update Xata if URL changed
        if final_url != original_url:
            patch_url = f"{CONFIG['XATA_BASE_URL']}/tables/domains/data/{record_id}"
            requests.patch(
                patch_url, 
                headers=headers, 
                json={"url": final_url}, 
                timeout=CONFIG['REQUEST_TIMEOUT']
            )

        return final_url
    except Exception as e:
        logger.error(f"Error getting base URL: {e}")
        return None

def send_message(chat_id: int, text: str, reply_to: Optional[int] = None, buttons: Optional[List] = None) -> Optional[Dict]:
    """Send a message to Telegram with error handling"""
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
    
    return make_telegram_request("sendMessage", payload)

def delete_message(chat_id: int, message_id: int) -> None:
    """Delete a message in Telegram"""
    make_telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        threaded=True
    )

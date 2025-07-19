from flask import Flask, request, abort
import requests
import feedparser
import os
import logging
from urllib.parse import quote_plus
from functools import wraps

# Initialize Flask app
app = Flask(__name__)

# Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BLOG_URL = os.environ.get("BLOG_URL", "").rstrip('/')
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
MAX_RESULTS = 5  # Maximum number of results to return
CACHE_DURATION = 300  # 5 minutes cache for RSS feed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for caching
feed_cache = None
last_fetch_time = 0

def telegram_webhook(f):
    """Decorator to validate Telegram webhook requests."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            data = request.get_json(force=True)
            message = data.get("message") or data.get("edited_message")
            if not message:
                abort(400, "Invalid message format")
            return f(message, *args, **kwargs)
        abort(405, "Method Not Allowed")
    return wrapper

@app.route("/", methods=["GET"])
def home():
    """Health check endpoint."""
    return "🤖 Movie Bot is Running! 🎬"

@app.route("/", methods=["POST"])
@telegram_webhook
def webhook(message):
    """Handle Telegram bot webhook."""
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip().lower()
    first_name = message.get("from", {}).get("first_name", "Friend")

    if not chat_id:
        logger.error("No chat_id in message")
        return {"ok": False, "error": "No chat_id provided"}, 400

    if not text:
        logger.info("Empty message received")
        return {"ok": True}

    try:
        if text.startswith("/start"):
            reply = (
                f"🎬 Welcome {first_name} to Movie Search Bot!\n\n"
                "🔍 Send me any movie name and I'll search our database for you.\n"
                "💡 Try sending just part of a movie name if you're not sure.\n\n"
                "Example: Try 'matrix' or 'dark knight'"
            )
        else:
            reply = search_movie(text, first_name)

        send_message(chat_id, reply)
        return {"ok": True}

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        send_message(chat_id, "⚠️ Sorry, something went wrong. Please try again later.")
        return {"ok": False, "error": str(e)}, 500

def get_rss_feed():
    """Fetch and cache the RSS feed with timeout handling."""
    global feed_cache, last_fetch_time
    
    # Return cached feed if it's fresh enough
    if feed_cache and (time.time() - last_fetch_time) < CACHE_DURATION:
        return feed_cache
        
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        response = requests.get(feed_url, timeout=10)
        response.raise_for_status()
        
        feed = feedparser.parse(response.content)
        feed_cache = feed
        last_fetch_time = time.time()
        return feed
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching RSS feed: {e}")
        if feed_cache:  # Return stale cache if available
            return feed_cache
        raise Exception("Could not fetch movie data. Please try again later.")

def search_movie(query, first_name):
    """Search for movies in the RSS feed."""
    try:
        feed = get_rss_feed()
        matches = []
        query = query.lower()
        
        for entry in feed.entries:
            title = entry.title.lower()
            if query in title:
                matches.append({
                    "title": entry.title,
                    "link": entry.link
                })

        if matches:
            # Sort by title length (shorter titles are usually more relevant)
            matches.sort(key=lambda x: len(x["title"]))
            
            results = []
            for i, movie in enumerate(matches[:MAX_RESULTS], 1):
                results.append(
                    f"{i}. 🎬 <b>{movie['title']}</b>\n"
                    f"   🔗 <a href='{movie['link']}'>View Details</a>"
                )
            
            more_results = len(matches) - MAX_RESULTS
            if more_results > 0:
                search_url = f"{BLOG_URL}/search?q={quote_plus(query)}"
                results.append(
                    f"\n🔍 <a href='{search_url}'>View {more_results} more results</a>"
                )
                
            return "\n\n".join(results)
            
        else:
            search_url = f"{BLOG_URL}/search?q={quote_plus(query)}"
            return (
                f"❌ Sorry {first_name}, no movies found for <b>{query}</b>\n\n"
                f"🔍 Try <a href='{search_url}'>searching on our website</a> "
                "or use different keywords."
            )

    except Exception as e:
        logger.error(f"Search error: {e}")
        return f"⚠️ Error searching for movies: {str(e)}"

def send_message(chat_id, text):
    """Send message to Telegram with error handling."""
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": False
        }
        
        response = requests.post(TELEGRAM_API, json=payload, timeout=5)
        response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

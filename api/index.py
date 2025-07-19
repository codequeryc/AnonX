from flask import Flask, request, jsonify
import requests
import feedparser
import os
import logging
import time  # ✅ Missing import added

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache the RSS feed to reduce calls
cached_feed = None
last_fetched = 0
FEED_CACHE_TTL = 60 * 5  # 5 minutes

# Get BLOG_URL from environment variable
BLOG_URL = os.environ.get("BLOG_URL", "https://yourblog.blogspot.com")

def get_rss_feed():
    global cached_feed, last_fetched
    current_time = time.time()

    if cached_feed is None or current_time - last_fetched > FEED_CACHE_TTL:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        logger.info(f"Fetching RSS feed from: {feed_url}")

        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.text)

            if not feed.entries:
                logger.warning("No entries found in the feed.")

            cached_feed = feed
            last_fetched = current_time
        except Exception as e:
            logger.error("Failed to fetch or parse RSS feed: %s", e)
            return None

    return cached_feed

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Request Bot is live!"

@app.route("/search", methods=["GET"])
def search_movie():
    query = request.args.get("query", "").lower().strip()
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    feed = get_rss_feed()
    if not feed:
        return jsonify({"error": "Unable to fetch feed"}), 500

    results = []
    logger.info(f"Searching for query: {query}")

    for entry in feed.entries:
        title = entry.title.lower()
        if query in title:
            message = f"🎬 <b>{entry.title}</b>\n\n🔗 <a href='{entry.link}'>Watch Now</a>"
            results.append(message)

    if not results:
        return jsonify({"results": [], "message": "No matches found."})

    return jsonify({"results": results})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    if not data or "message" not in data:
        return jsonify({"status": "ignored"})

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if not text:
        return jsonify({"status": "ignored"})

    if text.startswith("/start"):
        reply = "👋 Welcome! Send me a movie name and I'll fetch the link for you!"
    elif text.startswith("/help"):
        reply = "📖 Send a movie name to get download/watch links from the blog."
    else:
        search_results = search_movie_from_bot(text)
        reply = "\n\n".join(search_results) if search_results else "❌ No matching movies found."

    send_message(chat_id, reply)
    return jsonify({"status": "ok"})

def search_movie_from_bot(query):
    query = query.lower().strip()
    feed = get_rss_feed()
    if not feed:
        return []

    results = []

    for entry in feed.entries:
        title = entry.title.lower()
        if query in title:
            message = f"🎬 <b>{entry.title}</b>\n\n🔗 <a href='{entry.link}'>Watch Now</a>"
            results.append(message)

    return results

def send_message(chat_id, text):
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error("Failed to send message: %s", e)

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request
import requests
import os
import threading
from bs4 import BeautifulSoup
import json

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route("/", methods=["GET"])
def home():
    return "🤖 Movie Bot Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    
    # Handle inline queries
    if "inline_query" in data:
        handle_inline_query(data["inline_query"])
        return {"ok": True}
    
    # Handle callback queries (button clicks)
    if "callback_query" in data:
        handle_callback_query(data["callback_query"])
        return {"ok": True}
    
    # Normal message handling
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    user_text = msg.get("text", "").strip()
    user_name = msg.get("from", {}).get("first_name", "Friend")
    msg_id = msg.get("message_id")

    if not chat_id or not user_text:
        return {"ok": True}

    # Block links
    if any(link in user_text.lower() for link in ["http://", "https://", "t.me", "telegram.me"]):
        warning = f"⚠️ {user_name}, sharing links is not allowed in this group."
        warn_msg = send_message(chat_id, warning, reply_to=msg_id)
        delete_message(chat_id, msg_id)

        if warn_msg:
            warn_id = warn_msg.get("result", {}).get("message_id")
            threading.Timer(10, delete_message, args=(chat_id, warn_id)).start()
        return {"ok": True}

    # Start message
    if user_text.lower() == "/start":
        welcome = (
            f"🎬 Welcome {user_name}!\n"
            "Search with:\n"
            "<code>#movie Animal</code>\n"
            "<code>#tv Breaking Bad</code>\n"
            "<code>#series Loki</code>\n\n"
            "Or type <code>@{YOUR_BOT_USERNAME}</code> in any chat to search inline!"
        )
        send_message(chat_id, welcome)
        return {"ok": True}

    # Handle search
    if user_text.lower().startswith("#movie "):
        return handle_search(chat_id, user_text[7:], user_name, "Movie")

    if user_text.lower().startswith("#tv "):
        return handle_search(chat_id, user_text[4:], user_name, "TV Show")

    if user_text.lower().startswith("#series "):
        return handle_search(chat_id, user_text[8:], user_name, "Series")

    return {"ok": True}

def handle_inline_query(inline_query):
    query = inline_query.get("query", "").strip()
    user_id = inline_query["from"]["id"]
    
    if not query:
        return
    
    try:
        # Search for movies/TV shows
        results = []
        url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        for idx, item in enumerate(soup.select("div.A2")[:10]):
            a_tag = item.find("a", href=True)
            b_tag = item.find("b")
            if a_tag and b_tag:
                title = b_tag.text.strip()
                link = "https://filmyfly.party" + a_tag["href"]
                
                results.append({
                    "type": "article",
                    "id": str(idx),
                    "title": title,
                    "input_message_content": {
                        "message_text": f"🎬 <b>{title}</b>\n🔗 {link}",
                        "parse_mode": "HTML"
                    },
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "📜 View Details", "callback_data": f"fetch_details|{link}"}],
                            [{"text": "🔍 Search Again", "switch_inline_query_current_chat": query}]
                        ]
                    },
                    "description": "Click 'View Details' for more information"
                })
        
        if not results:
            results.append({
                "type": "article",
                "id": "0",
                "title": "No results found",
                "input_message_content": {
                    "message_text": f"❌ No results found for '{query}'",
                    "parse_mode": "HTML"
                }
            })
        
        requests.post(f"{TELEGRAM_API}/answerInlineQuery", json={
            "inline_query_id": inline_query["id"],
            "results": results,
            "cache_time": 300
        })
    except Exception as e:
        print(f"Error handling inline query: {e}")

def handle_callback_query(callback_query):
    data = callback_query["data"]
    message = callback_query["message"]
    chat_id = message["chat"]["id"]
    message_id = message["message_id"]
    user_id = callback_query["from"]["id"]
    
    if data.startswith("fetch_details|"):
        # Extract the URL from callback data
        url = data.split("|")[1]
        
        # Show "Fetching details..." message
        answer_callback_query(callback_query["id"], "⏳ Fetching details...")
        
        # Fetch and parse the movie details
        details = fetch_movie_details(url)
        
        if details:
            # Edit the original message with the details
            edit_message(chat_id, message_id, details["text"], details["buttons"])
        else:
            answer_callback_query(callback_query["id"], "❌ Failed to fetch details")
    else:
        # Default action - just answer the callback
        answer_callback_query(callback_query["id"])

def fetch_movie_details(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Extract movie thumbnail
        thumb_div = soup.find("div", class_="movie-thumb")
        image_url = thumb_div.find("img")["src"] if thumb_div else None
        
        # Extract movie title
        title_div = soup.find("div", align="center")
        title = title_div.find("h2").text.strip() if title_div else "No title found"
        
        # Extract other details (you can customize this based on the page structure)
        details_div = soup.find("div", class_="movie-details")
        details = []
        if details_div:
            for p in details_div.find_all("p"):
                details.append(p.text.strip())
        
        # Prepare the message text
        text = f"🎬 <b>{title}</b>\n\n"
        text += "\n".join(f"• {detail}" for detail in details)
        
        # Prepare buttons (you can add download links etc.)
        buttons = [
            [{"text": "🔗 View Original Page", "url": url}],
            [{"text": "🔍 Search Again", "switch_inline_query_current_chat": ""}]
        ]
        
        # If we have an image, send it as a photo with caption
        if image_url:
            return {
                "type": "photo",
                "image_url": image_url,
                "text": text,
                "buttons": buttons
            }
        else:
            return {
                "text": text,
                "buttons": buttons
            }
            
    except Exception as e:
        print(f"Error fetching movie details: {e}")
        return None

def edit_message(chat_id, message_id, text, buttons=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False  # Enable preview for details
    }
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    
    requests.post(f"{TELEGRAM_API}/editMessageText", json=payload)

def answer_callback_query(callback_query_id, text=None):
    payload = {
        "callback_query_id": callback_query_id
    }
    if text:
        payload["text"] = text
    requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json=payload)

# 🔍 Search and respond
def handle_search(chat_id, query, user_name, category):
    query = query.strip()
    if not query:
        send_message(chat_id, f"❌ Please provide a {category.lower()} name.")
        return {"ok": True}

    text, buttons = search_filmyfly(query, user_name, category)
    send_message(chat_id, text, buttons=buttons)
    return {"ok": True}

# ✅ Send message
def send_message(chat_id, text, reply_to=None, buttons=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}

    res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return res.json() if res.ok else None

# ✅ Delete message
def delete_message(chat_id, message_id):
    requests.post(f"{TELEGRAM_API}/deleteMessage", json={
        "chat_id": chat_id,
        "message_id": message_id
    })

# ✅ Scrape from filmyfly.party
def search_filmyfly(query, user_name, category):
    try:
        url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for item in soup.select("div.A2"):
            a_tag = item.find("a", href=True)
            b_tag = item.find("b")
            if a_tag and b_tag:
                title = b_tag.text.strip()
                link = "https://filmyfly.party" + a_tag["href"]
                results.append([{"text": title, "url": link}])
            if len(results) >= 5:
                break

        if results:
            return f"🔍 {category} results for <b>{query}</b>:", results
        else:
            return f"❌ Sorry {user_name}, no {category.lower()} found for <b>{query}</b>.", []

    except Exception as e:
        return f"⚠️ Error: {e}", []

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

from flask import Flask, request
import requests
import os
from bs4 import BeautifulSoup

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Simple storage for movie links (for demo only - use DB in production)
links_cache = {}

@app.route("/", methods=["POST"])
def handle_updates():
    data = request.get_json()
    
    # Handle callback queries
    if "callback_query" in data:
        return handle_callback(data["callback_query"])
    
    # Handle regular messages
    message = data.get("message", {})
    text = message.get("text", "").strip().lower()
    chat_id = message.get("chat", {}).get("id")
    
    if not chat_id or not text:
        return {"ok": True}
    
    if text == "/start":
        return send_welcome(chat_id)
    
    if text.startswith(("#movie ", "#tv ", "#series ")):
        query_type = text.split()[0][1:]  # Remove #
        search_query = text[len(query_type)+2:]  # Get the rest
        return search_movies(chat_id, search_query, query_type)
    
    return {"ok": True}

def handle_callback(callback):
    chat_id = callback["message"]["chat"]["id"]
    link_id = callback["data"]
    
    if link_id in links_cache:
        send_message(chat_id, f"🔗 Download:\n{links_cache[link_id]}")
    else:
        send_message(chat_id, "⚠️ Link expired")
    
    return {"ok": True}

def send_welcome(chat_id):
    welcome = (
        "🎬 Welcome to Movie Bot!\n\n"
        "Search using:\n"
        "#movie <name>\n"
        "#tv <name>\n"
        "#series <name>"
    )
    return send_message(chat_id, welcome)

def search_movies(chat_id, query, query_type):
    if not query:
        return send_message(chat_id, "❌ Please enter a search term")
    
    try:
        results = scrape_movies(query)
        if not results:
            return send_message(chat_id, f"❌ No {query_type} found for '{query}'")
        
        buttons = []
        for idx, (title, url) in enumerate(results.items()):
            link_id = f"link_{idx}"
            links_cache[link_id] = url
            buttons.append([{"text": title, "callback_data": link_id}])
        
        send_message(chat_id, f"🔍 Results for '{query}':", buttons)
    except Exception as e:
        send_message(chat_id, f"⚠️ Error: {str(e)}")
    
    return {"ok": True}

def scrape_movies(query):
    url = f"https://filmyfly.party/site-1.html?to-search={query.replace(' ', '+')}"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.text, "html.parser")
    
    results = {}
    for item in soup.select("div.A2")[:5]:  # Limit to 5 results
        if (a := item.find("a")) and (b := item.find("b")):
            title = b.text.strip()
            results[title] = "https://filmyfly.party" + a["href"]
    
    return results

def send_message(chat_id, text, buttons=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons} if buttons else None
    }
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

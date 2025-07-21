import os
from datetime import timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

XATA_API_KEY = os.getenv("XATA_API_KEY")
XATA_BASE_URL = os.getenv("XATA_BASE_URL")
BLOG_URL = os.getenv("BLOG_URL")

BLOGGER_CACHE = {
    'last_fetched': None,
    'posts': [],
    'expiry': timedelta(hours=1)
}

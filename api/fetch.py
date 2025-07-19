import requests
import os
from bs4 import BeautifulSoup

BLOG_URL = os.environ["BLOG_URL"]

def search_blogger(query):
    try:
        feed_url = f"{BLOG_URL}/feeds/posts/default?alt=rss"
        res = requests.get(feed_url, timeout=10)
        soup = BeautifulSoup(res.content, "xml")

        items = soup.find_all("item")
        results = []

        for item in items:
            title = item.title.text
            link = item.link.text

            if query.lower() in title.lower():
                results.append(f"🔹 [{title}]({link})")

        return results[:5]  # Limit to top 5 results

    except Exception as e:
        print(f"Error in search_blogger: {e}")
        return []

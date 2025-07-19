import requests
import os

BLOG_URL = os.environ.get("BLOG_URL")  # set in Vercel environment

def search_posts(query, max_results=5):
    if not query:
        return []

    feed_url = f"{BLOG_URL}/feeds/posts/default?q={query}&alt=json"
    response = requests.get(feed_url)

    if response.status_code != 200:
        return None

    try:
        data = response.json()
        entries = data.get("feed", {}).get("entry", [])
        results = []

        for entry in entries[:max_results]:
            title = entry.get("title", {}).get("$t", "No Title")
            link = next((l["href"] for l in entry["link"] if l["rel"] == "alternate"), "#")
            results.append({"title": title, "link": link})

        return results
    except Exception as e:
        print("Error parsing Blogger feed:", e)
        return None

import requests

def search_blogger(blog_url, query):
    feed_url = f"{blog_url}/feeds/posts/default?q={query}&alt=json"
    try:
        res = requests.get(feed_url)
        data = res.json()
        entries = data.get("feed", {}).get("entry", [])

        if not entries:
            return "❌ No matching posts found."

        results = []
        for entry in entries[:3]:  # Limit to top 3 results
            title = entry.get("title", {}).get("$t", "No Title")
            link = next((l["href"] for l in entry.get("link", []) if l["rel"] == "alternate"), "#")
            results.append(f"🔗 [{title}]({link})")

        return "\n\n".join(results)

    except Exception as e:
        return f"⚠️ Error fetching from Blogger: {str(e)}"

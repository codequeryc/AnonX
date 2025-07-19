from flask import Flask, request, jsonify
import feedparser
import os

app = Flask(__name__)
BLOG_URL = os.environ.get("BLOG_URL")

@app.route("/api/find")
def find_movies():
    query = request.args.get("q", "")
    if not query or not BLOG_URL:
        return jsonify({"results": []})

    try:
        feed = feedparser.parse(f"{BLOG_URL}/feeds/posts/default?q={query}&alt=rss")
        results = []
        for entry in feed.entries[:5]:
            results.append({
                "title": entry.title,
                "link": entry.link
            })
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e), "results": []})

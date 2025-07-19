from flask import Flask, request, jsonify
import feedparser
import os

app = Flask(__name__)
BLOG_URL = os.environ.get("BLOG_URL")

@app.route("/api/find", methods=["POST"])
def find_movie():
    data = request.get_json()
    query = data.get("query", "").lower()

    if not query:
        return jsonify({"success": False, "error": "No query provided"})

    feed = feedparser.parse(BLOG_URL)
    results = []

    for entry in feed.entries:
        if query in entry.title.lower():
            results.append({
                "title": entry.title,
                "url": entry.link
            })

    return jsonify({"success": True, "movies": results})

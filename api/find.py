from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

@app.route("/find", methods=["POST"])
def find_movie():
    data = request.get_json()
    query = data.get("query", "").lower()
    
    blog_url = os.environ.get("BLOG_URL")
    if not blog_url:
        return jsonify({"found": False, "error": "BLOG_URL not set"})

    feed_url = f"{blog_url}/feeds/posts/default?alt=json"
    try:
        res = requests.get(feed_url)
        res.raise_for_status()
        feed = res.json()
        
        entries = feed.get("feed", {}).get("entry", [])

        for entry in entries:
            title = entry.get("title", {}).get("$t", "").lower()
            link = ""
            for l in entry.get("link", []):
                if l.get("rel") == "alternate":
                    link = l.get("href")
            if query in title:
                return jsonify({
                    "found": True,
                    "title": title,
                    "link": link
                })

        return jsonify({"found": False})
    
    except Exception as e:
        return jsonify({"found": False, "error": str(e)})

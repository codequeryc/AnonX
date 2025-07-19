import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")  # should end with /tables/domains/data

@app.route("/config")
def get_and_update_url():
    uid = "abc12"
    query_url = XATA_BASE_URL.replace("/data", "/query")

    headers = {
        "Authorization": f"Bearer {XATA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "filter": {
            "uid": {"$equals": uid}
        }
    }

    # Step 1: Get record from Xata
    res = requests.post(query_url, headers=headers, json=payload)
    data = res.json()
    records = data.get("records", [])

    if not records:
        return jsonify({"error": "UID not found"}), 404

    record = records[0]
    record_id = record["id"]
    original_url = record["url"]

    # Step 2: Follow redirect
    try:
        r = requests.head(original_url, allow_redirects=True, timeout=5)
        final_url = r.url
    except:
        final_url = original_url  # fallback if error

    # Step 3: Update in Xata if redirected
    if final_url != original_url:
        update_url = f"{XATA_BASE_URL}/{record_id}"
        update_payload = { "url": final_url }
        requests.patch(update_url, headers=headers, json=update_payload)

    # Step 4: Return final URL to index.py
    return jsonify({ "url": final_url })

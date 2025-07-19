import os
import requests

XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")

def get_and_update_url(uid):
    headers = {
        "Authorization": f"Bearer {XATA_API_KEY}",
        "Content-Type": "application/json"
    }

    # Search record by UID
    query_url = f"{XATA_BASE_URL}/query"
    payload = {
        "filter": {
            "uid": {
                "$equals": uid
            }
        }
    }
    res = requests.post(query_url, headers=headers, json=payload)
    data = res.json()
    records = data.get("records", [])
    if not records:
        return None

    record = records[0]
    old_url = record.get("url")
    record_id = record.get("id")

    try:
        response = requests.get(old_url, allow_redirects=True, timeout=5)
        new_url = response.url
    except:
        new_url = old_url

    # Update DB if changed
    if old_url != new_url:
        update_url = f"{XATA_BASE_URL}/data/{record_id}"
        update_payload = {"url": new_url}
        requests.patch(update_url, headers=headers, json=update_payload)

    return new_url

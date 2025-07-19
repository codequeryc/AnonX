import os
import requests

XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")  # Example: https://your-xata-url/xata/your-workspace:main/tables/domains/data

def get_url_by_uid(uid):
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

    try:
        response = requests.post(query_url, headers=headers, json=payload, timeout=10)
        data = response.json()
        records = data.get("records", [])

        if records:
            return records[0].get("url")
        else:
            print(f"❌ No record found for uid: {uid}")
            return None

    except Exception as e:
        print(f"🔥 Error: {e}")
        return None

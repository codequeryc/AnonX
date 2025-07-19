import os
import requests

XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL") 
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_url_by_uid(uid):
    headers = {
        "Authorization": f"Bearer {XATA_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.get(XATA_BASE_URL, headers=headers, timeout=10)
        if not res.ok:
            print(f"[Xata ERROR] {res.text}")
            return None

        records = res.json().get("records", [])
        for record in records:
            if record.get("uid") == uid:
                record_id = record.get("id")
                saved_url = record.get("url")

                try:
                    r = requests.get(saved_url, headers=HEADERS, timeout=10, allow_redirects=True)
                    final_url = r.url

                    if final_url != saved_url:
                        update_url(record_id, uid, final_url)
                    return final_url

                except Exception as e:
                    print(f"[Redirect check failed] {e}")
                    return saved_url

        print(f"❌ UID '{uid}' not found.")
        return None

    except Exception as e:
        print(f"[Fetch error] {e}")
        return None


def update_url(record_id, uid, new_url):
    url = f"{XATA_BASE_URL}/{record_id}"
    headers = {
        "Authorization": f"Bearer {XATA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "uid": uid,
        "url": new_url
    }

    try:
        res = requests.patch(url, headers=headers, json=payload, timeout=10)
        if res.ok:
            print(f"✅ Updated: {uid} → {new_url}")
        else:
            print(f"❌ Update failed: {res.text}")
    except Exception as e:
        print(f"[Update error] {e}")

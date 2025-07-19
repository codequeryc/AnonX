import requests
import os

XATA_API_KEY = os.environ.get("XATA_API_KEY")
XATA_BASE_URL = os.environ.get("XATA_BASE_URL")

def get_and_update_url(uid):
    headers = {
        "Authorization": f"Bearer {XATA_API_KEY}",
        "Content-Type": "application/json"
    }

    # 1. Get record
    url = f"{XATA_BASE_URL}/tables/urls/data/{uid}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return None  # or handle error

    record = response.json()
    original_url = record.get("url")

    if not original_url:
        return None

    # 2. Check if it redirects
    try:
        final_url = requests.get(original_url, allow_redirects=True, timeout=5).url
    except:
        return original_url  # fallback

    # 3. If redirected, update
    if final_url != original_url:
        update_url = f"{XATA_BASE_URL}/tables/urls/data/{uid}"
        requests.patch(update_url, headers=headers, json={"url": final_url})

    return final_url
print("✅ config.py loaded")

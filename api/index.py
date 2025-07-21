from flask import Flask, request
import sys
import os
sys.path.append(os.path.dirname(__file__))

from bot import process_webhook


app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "🤖 Bot is Running!"

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    return process_webhook(data)

# Optional: Vercel handler (needed for some setups)
def handler(event, context):
    from mangum import Mangum
    asgi_handler = Mangum(app)
    return asgi_handler(event, context)

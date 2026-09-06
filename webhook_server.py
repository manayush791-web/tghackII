"""
Flask Webhook Server — Handles ALL incoming webhooks
Admin bot does NOT start its own server. Flask feeds updates to it.
"""
import asyncio
import threading
from flask import Flask, request, jsonify
from telegram import Update

from utils import hash_token, health
from database import db
from managed_bot import process_update as managed_process_update

flask_app = Flask(__name__)

# References set by main.py
_main_loop = None
_admin_app = None
_token_map = {}
_token_lock = threading.Lock()


def setup_server(loop, admin_app):
    """Called by main.py to pass references"""
    global _main_loop, _admin_app
    _main_loop = loop
    _admin_app = admin_app
    _refresh_token_map()


def _refresh_token_map():
    """Load all bot tokens into hash map"""
    global _token_map
    try:
        # We need to run async DB call in the main loop
        if _main_loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(_load_tokens(), _main_loop)
        _token_map = future.result(timeout=10)
    except Exception as e:
        print(f"[Webhook] Token map refresh error: {e}")


async def _load_tokens():
    bots = await db.get_all_bots(limit=10000)
    return {hash_token(bot["token"]): bot["token"] for bot in bots}


@flask_app.route('/')
def index():
    return jsonify({
        "status": "running",
        "service": "Telegram Bot Manager v3.0",
        "running_bots": len(health.status())
    })


@flask_app.route('/health')
def health_check():
    status = health.status()
    status["running_bots"] = len(_token_map) if _token_map else 0
    return jsonify(status)


@flask_app.route('/webhook/admin', methods=['POST'])
def admin_webhook():
    """Receive updates for the admin bot"""
    if _admin_app is None or _main_loop is None:
        return 'Not Ready', 503

    try:
        update_data = request.get_json(force=True, silent=True) or {}
        update = Update.de_json(update_data, _admin_app.bot)

        # Schedule async processing on the main event loop
        asyncio.run_coroutine_threadsafe(
            _admin_app.process_update(update),
            _main_loop
        )
        return 'OK', 200
    except Exception as e:
        print(f"[Webhook Admin Error] {e}")
        return 'OK', 200


@flask_app.route('/webhook/<token_hash>', methods=['POST'])
def managed_webhook(token_hash):
    """Receive updates for any managed bot"""
    if _main_loop is None:
        return 'Not Ready', 503

    try:
        with _token_lock:
            token = _token_map.get(token_hash)

        if not token:
            # Try refresh
            _refresh_token_map()
            with _token_lock:
                token = _token_map.get(token_hash)

        if not token:
            return 'OK', 200  # Unknown bot, silently ignore

        update_data = request.get_json(force=True, silent=True) or {}

        # Schedule async processing on the main event loop
        asyncio.run_coroutine_threadsafe(
            managed_process_update(token, update_data),
            _main_loop
        )
        return 'OK', 200
    except Exception as e:
        print(f"[Webhook Managed Error] {e}")
        return 'OK', 200


def start_server(host, port):
    """Start Flask server (called in a thread by main.py)"""
    print(f"🌐 Webhook server starting on {host}:{port}")
    flask_app.run(host=host, port=port, threaded=True, debug=False)

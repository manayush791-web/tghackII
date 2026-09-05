"""
Flask Webhook Server for Render Hosting
Receives updates for ALL managed bots via a single endpoint
Routes by token hash to avoid exposing tokens in URLs
"""
import asyncio
import threading
from flask import Flask, request, jsonify

from utils import hash_token
from managed_bot import process_update
from database import db

app = Flask(__name__)

# Token hash -> actual token mapping (loaded from DB)
_token_map = {}
_token_map_lock = threading.Lock()

async def _load_token_map():
    """Load all bot tokens and build hash map"""
    global _token_map
    bots = await db.get_all_bots(limit=10000)
    new_map = {}
    for bot in bots:
        token = bot["token"]
        new_map[hash_token(token)] = token
    with _token_map_lock:
        _token_map = new_map

async def _get_token_from_hash(token_hash):
    """Get actual token from hash"""
    with _token_map_lock:
        return _token_map.get(token_hash)

async def _refresh_token_map():
    """Refresh token map periodically"""
    while True:
        await asyncio.sleep(300)  # Refresh every 5 minutes
        try:
            await _load_token_map()
        except Exception as e:
            print(f"[Webhook] Token map refresh error: {e}")

@app.route('/')
def index():
    return jsonify({
        "status": "running",
        "service": "Telegram Bot Manager",
        "version": "3.0"
    })

@app.route('/health')
def health_check():
    from utils import health
    from managed_bot import get_running_bots
    status = health.status()
    status["running_bots"] = len(get_running_bots())
    return jsonify(status)

@app.route('/webhook/<token_hash>', methods=['POST'])
def webhook_handler(token_hash):
    """Handle incoming webhook from Telegram for any bot"""
    try:
        # Get token from hash
        with _token_map_lock:
            token = _token_map.get(token_hash)

        if not token:
            # Try to find it in DB directly
            async def find_token():
                bots = await db.get_all_bots(limit=10000)
                for bot in bots:
                    if hash_token(bot["token"]) == token_hash:
                        return bot["token"]
                return None

            loop = asyncio.get_event_loop()
            token = loop.run_until_complete(find_token())

            if token:
                with _token_map_lock:
                    _token_map[token_hash] = token

        if not token:
            return 'OK', 200  # Silently ignore unknown bots

        # Parse update
        update_data = request.get_json(force=True, silent=True) or {}

        # Process asynchronously
        loop = asyncio.get_event_loop()
        loop.create_task(process_update(token, update_data))

        return 'OK', 200
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return 'OK', 200  # Always return 200 to Telegram

def start_webhook_server(host, port):
    """Start the Flask webhook server in a thread"""
    # Load token map first
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.init())
    loop.run_until_complete(_load_token_map())

    # Start background refresh
    def run_refresh():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_refresh_token_map())

    refresh_thread = threading.Thread(target=run_refresh, daemon=True)
    refresh_thread.start()

    print(f"🌐 Webhook server starting on {host}:{port}")
    app.run(host=host, port=port, threaded=True, debug=False)

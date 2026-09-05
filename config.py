"""
Configuration & Environment
Load everything from .env for security & flexibility
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Admin ───
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()

# ─── Render / Webhook ───
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
HOST = os.getenv("HOST", "0.0.0.0")

# ─── Database ───
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_manager.db")

# ─── Rate Limits ───
BROADCAST_BATCH_SIZE = int(os.getenv("BROADCAST_BATCH_SIZE", "30"))
BROADCAST_DELAY_SEC = float(os.getenv("BROADCAST_DELAY_SEC", "1.2"))
API_CALL_SEMAPHORE = int(os.getenv("API_CALL_SEMAPHORE", "50"))
MAX_CONCURRENT_BOTS = int(os.getenv("MAX_CONCURRENT_BOTS", "20"))

# ─── Auto-Restart ───
AUTO_RESTART_INTERVAL_MIN = int(os.getenv("AUTO_RESTART_INTERVAL_MIN", "60"))
AUTO_RESTART_ENABLED = os.getenv("AUTO_RESTART_ENABLED", "true").lower() == "true"

# ─── Health ───
HEALTH_CHECK_ENABLED = os.getenv("HEALTH_CHECK_ENABLED", "true").lower() == "true"

# ─── Animated Emoji / Dice ───
DICE_EMOJIS = ["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"]
PARTY_EMOJIS = ["🎉", "🎊", "🎈", "🎁", "🎆", "🎇"]

# ─── States ───
(
    STATE_IDLE, STATE_WAITING_TOKENS, STATE_WAITING_BROADCAST,
    STATE_WAITING_WELCOME, STATE_WAITING_BUTTONS, STATE_WAITING_CHANNEL,
    STATE_WAITING_CLONE_SOURCE, STATE_WAITING_CLONE_TARGET,
    STATE_WAITING_BIO, STATE_WAITING_THEME, STATE_WAITING_BROADCAST_PER_BOT
) = range(11)

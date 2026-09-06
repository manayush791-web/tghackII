"""
Example Plugin — demonstrates all available hooks
Create your own .py files in this folder to add features
"""
from plugins import register_hook
from telegram import InlineKeyboardButton

@register_hook("on_bot_added")
async def log_new_bot(token, username):
    """Called when a new bot token is added"""
    print(f"[Plugin] New bot added: @{username}")

@register_hook("on_bot_started")
async def log_start(token, username):
    """Called when a bot goes live"""
    print(f"[Plugin] Bot started: @{username}")

@register_hook("on_bot_stopped")
async def log_stop(token, username):
    """Called when a bot is stopped"""
    print(f"[Plugin] Bot stopped: @{username}")

@register_hook("on_user_joined")
async def greet_user(user_id, bot_token):
    """Called when a user /start's any managed bot"""
    print(f"[Plugin] User {user_id} joined bot {bot_token[:15]}...")

@register_hook("on_broadcast_sent")
async def log_broadcast(token_or_all, count):
    """Called after a broadcast completes"""
    print(f"[Plugin] Broadcast sent to {count} users (scope: {token_or_all})")

@register_hook("on_export")
async def log_export(filepath, admin_id):
    """Called when tokens are exported"""
    print(f"[Plugin] Tokens exported by admin {admin_id}")

@register_hook("on_text_received")
async def handle_custom_text(update, context):
    """
    Called for every text message received by admin bot.
    Return True to block default handling.
    """
    text = update.message.text if update.message else ""
    if text == "/ping":
        await update.message.reply_text("🏓 Pong! Plugin is working!")
        return True
    return False

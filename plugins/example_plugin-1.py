"""
Example Plugin
"""
from plugins import register_hook

@register_hook("on_bot_added")
async def log_new_bot(token, username):
    print(f"[Plugin] New bot added: @{username}")

@register_hook("on_bot_started")
async def log_start(token, username):
    print(f"[Plugin] Bot started: @{username}")

@register_hook("on_bot_stopped")
async def log_stop(token, username):
    print(f"[Plugin] Bot stopped: @{username}")

@register_hook("on_user_joined")
async def greet_user(user_id, bot_token):
    print(f"[Plugin] User {user_id} joined bot {bot_token[:15]}...")

@register_hook("on_broadcast_sent")
async def log_broadcast(token_or_all, count):
    print(f"[Plugin] Broadcast sent to {count} users")

@register_hook("on_text_received")
async def handle_custom_text(update, context):
    text = update.message.text if update.message else ""
    if text == "/ping":
        await update.message.reply_text("🏓 Pong! Plugin is working!")
        return True
    return False

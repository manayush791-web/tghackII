"""
Telegram Bot Manager v3.0 - Admin Bot
Ultimate upgrade: handles 1000+ bots, webhooks, auto-restart, health checks
"""
import os
import sys
import re
import json
import asyncio
import threading
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove, Bot
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from config import (
    ADMIN_IDS, ADMIN_BOT_TOKEN, WEBHOOK_URL, PORT, HOST,
    STATE_IDLE, STATE_WAITING_TOKENS, STATE_WAITING_BROADCAST,
    STATE_WAITING_WELCOME, STATE_WAITING_BUTTONS, STATE_WAITING_CHANNEL,
    STATE_WAITING_CLONE_SOURCE, STATE_WAITING_CLONE_TARGET,
    STATE_WAITING_BIO, STATE_WAITING_THEME, STATE_WAITING_BROADCAST_PER_BOT,
    BROADCAST_BATCH_SIZE, BROADCAST_DELAY_SEC, AUTO_RESTART_ENABLED, AUTO_RESTART_INTERVAL_MIN
)
from database import db
from managed_bot import (
    start_managed_bot, stop_managed_bot, stop_all_managed_bots,
    get_running_bots, get_running_bots_info, is_bot_running,
    broadcast_to_bot, broadcast_to_all, clear_bot_cache
)
from themes import THEMES, format_welcome, random_theme, get_random_dice
from utils import parse_tokens, truncate_text, format_number, health, safe_api_call, hash_token
from rate_limiter import rate_limiter
from plugins import load_plugins, call_hook, get_loaded_plugins
from webhook_server import start_webhook_server

# ============ INIT ============
_admin_app = None
_start_time = None

async def init_system():
    """Initialize database and plugins"""
    await db.init()
    load_plugins()
    print("✅ System initialized")


async def is_authorized_async(user_id: int) -> bool:
    """Async admin check"""
    if user_id in ADMIN_IDS:
        return True
    return await db.is_admin(user_id)


# ============ PAGINATED KEYBOARD BUILDERS ============
# CRITICAL FIX: Don't render 102 buttons at once - paginate!

BOTS_PER_PAGE = 8

def build_admin_panel():
    """Main admin control panel"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Bot Tokens", callback_data="add_tokens")],
        [InlineKeyboardButton("🚀 Start Bot", callback_data="start_bot"),
         InlineKeyboardButton("🛑 Stop Bot", callback_data="stop_bot")],
        [InlineKeyboardButton("📋 List Bots", callback_data="list_bots"),
         InlineKeyboardButton("🗑️ Delete Bot", callback_data="delete_bot")],
        [InlineKeyboardButton("📢 Global Broadcast", callback_data="broadcast"),
         InlineKeyboardButton("📡 Per-Bot Broadcast", callback_data="broadcast_per_bot")],
        [InlineKeyboardButton("👮 Check Admin", callback_data="check_admin"),
         InlineKeyboardButton("🔄 Clone Bot", callback_data="clone_bot")],
        [InlineKeyboardButton("✏️ Edit Welcome", callback_data="edit_welcome"),
         InlineKeyboardButton("🔘 Edit Buttons", callback_data="edit_buttons")],
        [InlineKeyboardButton("📝 Edit Bio", callback_data="edit_bio"),
         InlineKeyboardButton("🎨 Change Theme", callback_data="edit_theme")],
        [InlineKeyboardButton("🚫 Block User", callback_data="block_user"),
         InlineKeyboardButton("✅ Unblock User", callback_data="unblock_user")],
        [InlineKeyboardButton("📤 Export Tokens", callback_data="export_tokens"),
         InlineKeyboardButton("💾 Backup DB", callback_data="backup_db")],
        [InlineKeyboardButton("📊 Stats", callback_data="show_stats"),
         InlineKeyboardButton("🩺 Health", callback_data="show_health")],
        [InlineKeyboardButton("🔄 Restart All", callback_data="restart_all"),
         InlineKeyboardButton("🛑 Stop All", callback_data="stop_all")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def build_bot_list_keyboard(action="select", page=0):
    """Build PAGINATED keyboard with bots - THE FIX for 102+ bots crash"""
    offset = page * BOTS_PER_PAGE
    bots = await db.get_all_bots(limit=BOTS_PER_PAGE, offset=offset)
    total = await db.get_bots_count()

    keyboard = []
    for bot in bots:
        status = "🟢" if bot["status"] == "running" else "🔴"
        name = f"@{bot['username']}" if bot["username"] else bot["token"][:15] + "..."
        label = f"{status} {name}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{action}:{bot['token']}")])

    # Pagination controls
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"page:{action}:{page-1}"))
    if offset + BOTS_PER_PAGE < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"page:{action}:{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard), total


# ============ START COMMAND ============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not await is_authorized_async(user.id):
        await update.message.reply_text(
            "⛔ <b>Access Denied</b>\n\nYou are not authorized.",
            parse_mode=ParseMode.HTML
        )
        return STATE_IDLE

    await db.add_admin(user.id)

    welcome = f"""✨ 🌟 💎 🌟 ✨

<b>👑 Welcome to Bot Manager v3.0, {user.first_name}!</b>

🚀 <b>Ultimate Bot Management System</b>
<i>Handles 1000+ bots without crashing!</i>

💎 <b>What's New:</b>
• Webhook architecture (no polling overload)
• Paginated bot lists (no more crashes)
• Rate-limited broadcasting
• Auto-restart & health monitoring
• Per-bot broadcast
• User blocking system
• Database backups
• Working animated dice & party poppers

<b>Choose an action below:</b>"""

    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.HTML,
        reply_markup=build_admin_panel()
    )
    return STATE_IDLE


async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = f"""✨ 🌟 💎 🌟 ✨

<b>🎛️ Admin Control Panel v3.0</b>

<i>Select an action to manage your bots</i>

⚡ <b>Running:</b> {len(get_running_bots())} bots
📊 <b>Total:</b> {await db.get_bots_count()} bots
👥 <b>Users:</b> {format_number(await db.get_total_users_all_bots())}"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=build_admin_panel())
    return STATE_IDLE


# ============ ADD TOKENS ============
async def add_tokens_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """<b>➕ Add Bot Tokens</b>

Send me bot tokens in any format:
• One per line
• With or without quotes

<b>Example:</b>
<code>123456789:ABCdefGHIjklMNOpqrSTUvwxyz</code>
<code>"987654321:XYZabcDEFghiJKLmnoPQRstu"</code>

<i>You can send 100+ tokens at once — no crash!</i>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_TOKENS


async def receive_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    tokens = parse_tokens(text)

    if not tokens:
        await update.message.reply_text(
            "❌ <b>No valid tokens found!</b>\nTry again.",
            parse_mode=ParseMode.HTML
        )
        return STATE_WAITING_TOKENS

    results = []
    success_count = 0

    for token in tokens:
        try:
            temp_bot = Bot(token)
            me = await temp_bot.get_me()

            await db.add_bot(token, username=me.username)
            await call_hook("on_bot_added", token, me.username)

            results.append(f"✅ @{me.username}")
            success_count += 1

            await temp_bot.session.close()
        except Exception as e:
            results.append(f"❌ ...{token[-15:]} | {str(e)[:40]}")

    result_text = f"<b>📋 Results: {success_count}/{len(tokens)} added</b>\n\n"
    result_text += "\n".join(results[:30])
    if len(results) > 30:
        result_text += f"\n\n<i>...and {len(results) - 30} more</i>"

    await update.message.reply_text(
        result_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ PAGINATED LIST BOTS ============
async def list_bots_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:list:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("info", page=page)

    text = f"<b>📋 Your Bot Collection</b>\n<i>Page {page+1} | Total: {total} bots</i>\n\nTap a bot for details."

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard_markup)
    return STATE_IDLE


async def bot_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    bot_data = await db.get_bot(token)
    if not bot_data:
        await query.edit_message_text("❌ Bot not found.")
        return STATE_IDLE

    stats = await db.get_bot_stats(token)
    user_count = await db.get_user_count(token)

    text = f"""<b>🤖 Bot Info</b>

👤 <b>Username:</b> @{bot_data.get('username') or 'Unknown'}
🔑 <b>Token:</b> <code>{bot_data['token'][:20]}...</code>
📊 <b>Status:</b> {'🟢 RUNNING' if bot_data['status'] == 'running' else '🔴 STOPPED'}
🎨 <b>Theme:</b> {bot_data.get('theme', 'royal_gold')}
👥 <b>Users:</b> {format_number(user_count)}
📅 <b>Added:</b> {bot_data.get('created_at', 'N/A')}

📈 <b>Stats:</b>
├ Starts: {stats.get('start_count', 0) if stats else 0}
├ Stops: {stats.get('stop_count', 0) if stats else 0}
└ Last Start: {stats.get('last_started', 'Never') if stats else 'Never'}"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Start", callback_data=f"do_start:{token}"),
         InlineKeyboardButton("🛑 Stop", callback_data=f"do_stop:{token}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"do_delete:{token}")],
        [InlineKeyboardButton("🔙 Back to List", callback_data="list_bots")]
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return STATE_IDLE


# ============ START BOT ============
async def start_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:do_start:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("do_start", page=page)

    await query.edit_message_text(
        f"<b>🚀 Select a bot to START</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def do_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Starting...")

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]

    if await is_bot_running(token):
        await query.edit_message_text(
            "⚠️ Bot is already running!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
        return STATE_IDLE

    success, result = await start_managed_bot(token, WEBHOOK_URL)

    if success:
        text = f"""✅ <b>Bot Started!</b>

👤 @{result}
🔑 <code>{token[:15]}...</code>
📊 Status: 🟢 Running

<i>Webhook set successfully!</i>"""
    else:
        text = f"""❌ <b>Failed to Start</b>

🔑 <code>{token[:15]}...</code>
🚨 <code>{truncate_text(result, 100)}</code>"""

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ STOP BOT ============
async def stop_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    running = await get_running_bots_info()
    if not running:
        await query.edit_message_text(
            "❌ No bots are currently running.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
        return STATE_IDLE

    keyboard = []
    for info in running:
        label = f"🛑 @{info['username'] or 'Unknown'}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"do_stop:{info['token']}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])

    await query.edit_message_text(
        "<b>🛑 Select a bot to STOP:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_IDLE


async def do_stop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Stopping...")

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    success, result = await stop_managed_bot(token)

    text = f"✅ <b>Bot Stopped:</b> @{result}" if success else f"❌ <b>Error:</b> {result}"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ DELETE BOT ============
async def delete_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:do_delete:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("do_delete", page=page)

    await query.edit_message_text(
        f"<b>🗑️ Select bot to DELETE</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def do_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]

    if await is_bot_running(token):
        await stop_managed_bot(token)

    await db.delete_bot(token)

    await query.edit_message_text(
        "🗑️ <b>Bot deleted successfully!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ BROADCAST GLOBAL ============
async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    total_users = await db.get_total_users_all_bots()

    text = f"""<b>📢 Global Broadcast</b>

👥 <b>Total users to reach:</b> {format_number(total_users)}

Send me the message to broadcast.

<b>Supported:</b>
• Plain text
• HTML formatting
• Emoji & animated content

<i>Rate-limited: ~25 msgs/sec to prevent crashes</i>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_BROADCAST


async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    broadcast_text = message.text

    all_users = await db.get_all_users(limit=100000)
    if not all_users:
        await message.reply_text(
            "❌ No users found.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
        return STATE_IDLE

    log_id = await db.log_broadcast_start("all", broadcast_text[:50], len(all_users))

    status_msg = await message.reply_text(
        f"⏳ <b>Broadcasting to {format_number(len(all_users))} users...</b>\n"
        f"Sent: 0 | Failed: 0\nPlease wait...",
        parse_mode=ParseMode.HTML
    )

    async def status_callback(sent, failed, total):
        try:
            await status_msg.edit_text(
                f"⏳ <b>Broadcasting...</b>\n"
                f"Sent: {format_number(sent)} | Failed: {format_number(failed)}\n"
                f"Progress: {sent+failed}/{format_number(total)}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

    sent, failed = await broadcast_to_all(broadcast_text, status_callback)

    await db.log_broadcast_complete(log_id, sent, failed)
    health.record_broadcast()

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"📤 Sent: {format_number(sent)}\n"
        f"❌ Failed: {format_number(failed)}\n"
        f"👥 Total: {format_number(len(all_users))}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )

    await call_hook("on_broadcast_sent", "all", sent)
    return STATE_IDLE


# ============ PER-BOT BROADCAST ============
async def broadcast_per_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:broadcast_bot:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("broadcast_bot", page=page)

    await query.edit_message_text(
        f"<b>📡 Select bot to broadcast from</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_WAITING_BROADCAST_PER_BOT


async def broadcast_bot_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    context.user_data["broadcast_bot_token"] = token

    user_count = await db.get_user_count(token)
    bot_data = await db.get_bot(token)

    text = f"""<b>📡 Per-Bot Broadcast</b>

🤖 <b>Bot:</b> @{bot_data.get('username') or 'Unknown'}
👥 <b>Users:</b> {format_number(user_count)}

Send me the message to broadcast to this bot's users only."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_BROADCAST_PER_BOT


async def receive_broadcast_per_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data.get("broadcast_bot_token")
    if not token:
        await update.message.reply_text("❌ Session expired.")
        return STATE_IDLE

    broadcast_text = update.message.text
    users = await db.get_all_users(bot_token=token, limit=50000)

    if not users:
        await update.message.reply_text("❌ No users for this bot.")
        return STATE_IDLE

    log_id = await db.log_broadcast_start(token, broadcast_text[:50], len(users))

    status_msg = await update.message.reply_text(
        f"⏳ <b>Broadcasting to {format_number(len(users))} users...</b>",
        parse_mode=ParseMode.HTML
    )

    async def status_callback(sent, failed, total):
        try:
            await status_msg.edit_text(
                f"⏳ Broadcasting... {sent+failed}/{total}",
                parse_mode=ParseMode.HTML
            )
        except:
            pass

    sent, failed = await broadcast_to_bot(token, broadcast_text, status_callback)

    await db.log_broadcast_complete(log_id, sent, failed)

    await status_msg.edit_text(
        f"✅ <b>Done!</b> 📤 {sent} | ❌ {failed}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )

    context.user_data.pop("broadcast_bot_token", None)
    return STATE_IDLE


# ============ CHECK ADMIN ============
async def check_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """<b>👮 Check Admin Rights</b>

Send me the group/channel ID or username.

<b>Examples:</b>
<code>-1001234567890</code>
<code>@mygroup</code>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_CHANNEL


async def receive_channel_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    running = await get_running_bots_info()

    if not running:
        await update.message.reply_text("❌ No running bots.")
        return STATE_IDLE

    results = []
    for info in running:
        try:
            bot = Bot(info["token"])
            member = await bot.get_chat_member(channel, bot.id)
            status = member.status

            if status in ["administrator", "creator"]:
                results.append(f"✅ @{info['username']} - <b>{status.upper()}</b>")
            else:
                results.append(f"❌ @{info['username']} - {status}")

            await bot.session.close()
        except Exception as e:
            results.append(f"⚠️ @{info['username']} - {str(e)[:30]}")

    text = f"<b>👮 Results for {channel}</b>\n\n" + "\n".join(results)

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ CLONE BOT ============
async def clone_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """<b>🔄 Clone Bot Settings</b>

Send me the <b>source</b> bot token (copy FROM)."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_CLONE_SOURCE


async def receive_clone_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip().strip('"').strip("'")
    bot_data = await db.get_bot(token)

    if not bot_data:
        await update.message.reply_text("❌ Bot not found.")
        return STATE_IDLE

    context.user_data["clone_source"] = token

    text = f"""✅ <b>Source:</b> @{bot_data.get('username') or 'Unknown'}

Now send me the <b>target</b> bot token (copy TO)."""

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_CLONE_TARGET


async def receive_clone_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_token = update.message.text.strip().strip('"').strip("'")
    source_token = context.user_data.get("clone_source")

    if not source_token:
        await update.message.reply_text("❌ Session expired.")
        return STATE_IDLE

    source = await db.get_bot(source_token)
    target = await db.get_bot(target_token)

    if not target:
        await update.message.reply_text("❌ Target bot not found.")
        return STATE_IDLE

    await db.update_bot_welcome(target_token, source.get("welcome_msg"))
    await db.update_bot_buttons(target_token, source.get("buttons_json"))
    await db.update_bot_bio(target_token, source.get("bio"))
    await db.update_bot_theme(target_token, source.get("theme"))

    await update.message.reply_text(
        f"✅ <b>Clone Complete!</b>\n\nCopied all settings from @{source.get('username') or 'Unknown'} to @{target.get('username') or 'Unknown'}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )

    context.user_data.pop("clone_source", None)
    return STATE_IDLE


# ============ EDIT WELCOME ============
async def edit_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:edit_welcome_bot:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("edit_welcome_bot", page=page)

    await query.edit_message_text(
        f"<b>✏️ Select bot to edit welcome</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def edit_welcome_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    context.user_data["edit_bot_token"] = token

    bot_data = await db.get_bot(token)
    current = bot_data.get("welcome_msg") or "(default)"

    text = f"""<b>✏️ Edit Welcome Message</b>

Current:
<pre>{truncate_text(current, 400)}</pre>

Send new message.

<b>Variables:</b> <code>{{first_name}}</code>
<b>HTML:</b> &lt;b&gt;, &lt;i&gt;, &lt;code&gt;, &lt;pre&gt;, &lt;blockquote&gt;, &lt;tg-spoiler&gt;"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_WELCOME


async def receive_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data.get("edit_bot_token")
    if not token:
        await update.message.reply_text("❌ Session expired.")
        return STATE_IDLE

    welcome_msg = update.message.text
    await db.update_bot_welcome(token, welcome_msg)

    await update.message.reply_text(
        "✅ <b>Welcome message updated!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )

    context.user_data.pop("edit_bot_token", None)
    return STATE_IDLE


# ============ EDIT BUTTONS ============
async def edit_buttons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:edit_buttons_bot:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("edit_buttons_bot", page=page)

    await query.edit_message_text(
        f"<b>🔘 Select bot to edit buttons</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def edit_buttons_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    context.user_data["edit_buttons_token"] = token

    bot_data = await db.get_bot(token)
    current = bot_data.get("buttons_json") or json.dumps(DEFAULT_BUTTONS)

    text = f"""<b>🔘 Edit Buttons</b>

Current:
<code>{current}</code>

Send new JSON:
<pre>
[
  {{"text": "📢 Channel", "url": "https://t.me/channel"}},
  {{"text": "💬 Support", "url": "https://t.me/support"}}
]
</pre>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_BUTTONS


async def receive_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data.get("edit_buttons_token")
    if not token:
        await update.message.reply_text("❌ Session expired.")
        return STATE_IDLE

    try:
        buttons = json.loads(update.message.text)
        if not isinstance(buttons, list):
            raise ValueError("Must be a list")

        await db.update_bot_buttons(token, json.dumps(buttons))

        await update.message.reply_text(
            f"✅ <b>Buttons updated!</b> ({len(buttons)} buttons)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Invalid JSON:</b> {e}\n\nTry again.",
            parse_mode=ParseMode.HTML
        )
        return STATE_WAITING_BUTTONS

    context.user_data.pop("edit_buttons_token", None)
    return STATE_IDLE


# ============ EDIT BIO ============
async def edit_bio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:edit_bio_bot:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("edit_bio_bot", page=page)

    await query.edit_message_text(
        f"<b>📝 Select bot to edit bio</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def edit_bio_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    context.user_data["edit_bio_token"] = token

    bot_data = await db.get_bot(token)
    current = bot_data.get("bio") or "(empty)"

    text = f"""<b>📝 Edit Bio</b>

Current: <i>{truncate_text(current, 200)}</i>

Send new bio text."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_BIO


async def receive_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data.get("edit_bio_token")
    if not token:
        await update.message.reply_text("❌ Session expired.")
        return STATE_IDLE

    bio = update.message.text
    await db.update_bot_bio(token, bio)

    await update.message.reply_text(
        "✅ <b>Bio updated!</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )

    context.user_data.pop("edit_bio_token", None)
    return STATE_IDLE


# ============ EDIT THEME ============
async def edit_theme_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = 0
    if query.data.startswith("page:edit_theme_bot:"):
        page = int(query.data.split(":")[-1])

    keyboard_markup, total = await build_bot_list_keyboard("edit_theme_bot", page=page)

    await query.edit_message_text(
        f"<b>🎨 Select bot to change theme</b>\n<i>Page {page+1} | Total: {total}</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard_markup
    )
    return STATE_IDLE


async def edit_theme_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    token = data[1]
    context.user_data["edit_theme_token"] = token

    keyboard = []
    for theme_key, theme_data in THEMES.items():
        keyboard.append([InlineKeyboardButton(theme_data["name"], callback_data=f"set_theme:{theme_key}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])

    await query.edit_message_text(
        "<b>🎨 Choose a theme:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return STATE_WAITING_THEME


async def set_theme_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)
    if len(data) < 2:
        return STATE_IDLE

    theme_key = data[1]
    token = context.user_data.get("edit_theme_token")

    if not token:
        await query.edit_message_text("❌ Session expired.")
        return STATE_IDLE

    await db.update_bot_theme(token, theme_key)

    await query.edit_message_text(
        f"✅ <b>Theme changed to {THEMES.get(theme_key, {}).get('name', theme_key)}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )

    context.user_data.pop("edit_theme_token", None)
    return STATE_IDLE


# ============ BLOCK/UNBLOCK USER ============
async def block_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """<b>🚫 Block User</b>

Send me the user ID to block.

<i>This user will no longer receive broadcasts or interact with bots.</i>"""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_CHANNEL


async def unblock_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = """<b>✅ Unblock User</b>

Send me the user ID to unblock."""

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return STATE_WAITING_CHANNEL


async def receive_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        user_id = int(text)
        await db.block_user(user_id, "Blocked by admin")
        await update.message.reply_text(
            f"🚫 <b>User {user_id} blocked.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Send a number.")
        return STATE_WAITING_CHANNEL
    return STATE_IDLE


async def receive_unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        user_id = int(text)
        await db.unblock_user(user_id)
        await update.message.reply_text(
            f"✅ <b>User {user_id} unblocked.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Send a number.")
        return STATE_WAITING_CHANNEL
    return STATE_IDLE


# ============ EXPORT TOKENS ============
async def export_tokens_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Exporting...")

    filepath = f"/tmp/bot_tokens_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    try:
        await db.export_tokens_to_file(filepath)

        with open(filepath, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                caption=f"📤 <b>Exported {await db.get_bots_count()} bot tokens</b>",
                parse_mode=ParseMode.HTML
            )

        os.remove(filepath)

        await call_hook("on_export", filepath, update.effective_user.id)

        await query.edit_message_text(
            "✅ <b>Export complete!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Export failed: {e}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )

    return STATE_IDLE


# ============ BACKUP DB ============
async def backup_db_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Backing up...")

    backup_path = f"/tmp/bot_manager_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    try:
        await db.backup_database(backup_path)

        with open(backup_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                caption="💾 <b>Database Backup</b>",
                parse_mode=ParseMode.HTML
            )

        os.remove(backup_path)

        await query.edit_message_text(
            "✅ <b>Backup complete!</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ Backup failed: {e}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )

    return STATE_IDLE


# ============ STATS ============
async def show_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    total_bots = await db.get_bots_count()
    running_bots = len(get_running_bots())
    total_users = await db.get_total_users_all_bots()
    unique_users = await db.get_user_count()
    stats = await db.get_all_stats()

    text = f"""✨ 🌟 💎 🌟 ✨

<b>📊 Bot Manager Statistics</b>

🤖 <b>Bots:</b>
   ├ Total: {format_number(total_bots)}
   ├ Running: {format_number(running_bots)}
   └ Stopped: {format_number(total_bots - running_bots)}

👥 <b>Users:</b>
   ├ Total interactions: {format_number(total_users)}
   └ Unique users: {format_number(unique_users)}

⚡ <b>System:</b>
   ├ Plugins: {len(get_loaded_plugins())}
   ├ Health: {health.status()['status']}
   └ Errors: {health.status()['errors']}

📈 <b>Top Bots by Starts:</b>"""

    if stats:
        sorted_stats = sorted(stats, key=lambda x: x.get('start_count', 0), reverse=True)[:5]
        for i, s in enumerate(sorted_stats, 1):
            text += f"\n   {i}. {s.get('token', 'Unknown')[:15]}... ({s.get('start_count', 0)} starts)"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ HEALTH ============
async def show_health_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    status = health.status()

    text = f"""<b>🩺 System Health</b>

⏱️ <b>Uptime:</b> {status['uptime']}
📊 <b>Status:</b> {status['status']}
🚀 <b>Bot Starts:</b> {status['bot_starts']}
🛑 <b>Bot Stops:</b> {status['bot_stops']}
📢 <b>Broadcasts:</b> {status['broadcasts']}
❌ <b>Errors:</b> {status['errors']}

<i>Last error: {status['last_error'] or 'None'}</i>"""

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ RESTART ALL / STOP ALL ============
async def restart_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Restarting all bots...")

    await stop_all_managed_bots()
    await asyncio.sleep(2)

    bots = await db.get_all_bots(limit=10000)
    started = 0
    failed = 0

    for bot in bots:
        if bot["status"] == "running":
            success, _ = await start_managed_bot(bot["token"], WEBHOOK_URL)
            if success:
                started += 1
            else:
                failed += 1
            await asyncio.sleep(0.5)

    await query.edit_message_text(
        f"✅ <b>Restart Complete!</b>\n\n🚀 Started: {started}\n❌ Failed: {failed}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


async def stop_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Stopping all bots...")

    results = await stop_all_managed_bots()

    stopped = sum(1 for _, success, _ in results if success)

    await query.edit_message_text(
        f"✅ <b>Stopped {stopped} bots</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ CANCEL / FALLBACK ============
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❎ Cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        results = await call_hook("on_text_received", update, context)
        if any(results):
            return STATE_IDLE
    except:
        pass

    await update.message.reply_text(
        "⚠️ Use the buttons or /start",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎛️ Open Panel", callback_data="admin_panel")]
        ])
    )
    return STATE_IDLE


# ============ PAGE HANDLER ============
async def page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if len(parts) < 3:
        return STATE_IDLE

    action = parts[1]
    page = int(parts[2])

    if action == "select" or action == "info":
        query.data = f"page:list:{page}"
        return await list_bots_callback(update, context)
    elif action == "do_start":
        query.data = f"page:do_start:{page}"
        return await start_bot_callback(update, context)
    elif action == "do_delete":
        query.data = f"page:do_delete:{page}"
        return await delete_bot_callback(update, context)
    elif action == "broadcast_bot":
        query.data = f"page:broadcast_bot:{page}"
        return await broadcast_per_bot_callback(update, context)
    elif action == "edit_welcome_bot":
        query.data = f"page:edit_welcome_bot:{page}"
        return await edit_welcome_callback(update, context)
    elif action == "edit_buttons_bot":
        query.data = f"page:edit_buttons_bot:{page}"
        return await edit_buttons_callback(update, context)
    elif action == "edit_bio_bot":
        query.data = f"page:edit_bio_bot:{page}"
        return await edit_bio_callback(update, context)
    elif action == "edit_theme_bot":
        query.data = f"page:edit_theme_bot:{page}"
        return await edit_theme_callback(update, context)

    return STATE_IDLE


# ============ AUTO-RESTART TASK ============
async def auto_restart_task():
    if not AUTO_RESTART_ENABLED:
        return

    while True:
        await asyncio.sleep(AUTO_RESTART_INTERVAL_MIN * 60)
        try:
            print("[AutoRestart] Running scheduled restart...")
            running = list(get_running_bots())
            for token in running:
                await stop_managed_bot(token)
                await asyncio.sleep(1)
                await start_managed_bot(token, WEBHOOK_URL)
                await asyncio.sleep(1)
            print(f"[AutoRestart] Restarted {len(running)} bots")
        except Exception as e:
            print(f"[AutoRestart] Error: {e}")
            health.record_error(e)


# ============ MAIN ============
def main():
    import time
    global _start_time
    _start_time = time.time()

    if not ADMIN_BOT_TOKEN:
        print("=" * 60)
        print("TELEGRAM BOT MANAGER v3.0 - SETUP")
        print("=" * 60)
        print("\nSet ADMIN_BOT_TOKEN in .env file")
        print("=" * 60)
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_system())

    for admin_id in ADMIN_IDS:
        loop.run_until_complete(db.add_admin(admin_id))

    print("🚀 Starting Telegram Bot Manager v3.0...")
    print(f"📊 Database: {db.db_path}")
    print(f"🌐 Webhook URL: {WEBHOOK_URL or 'Not set (polling mode)'}")

    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    global _admin_app
    _admin_app = app

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_command),
        ],
        states={
            STATE_IDLE: [
                CallbackQueryHandler(admin_panel_callback, pattern="^admin_panel$"),
                CallbackQueryHandler(add_tokens_callback, pattern="^add_tokens$"),
                CallbackQueryHandler(start_bot_callback, pattern="^start_bot$|^page:do_start:"),
                CallbackQueryHandler(stop_bot_callback, pattern="^stop_bot$"),
                CallbackQueryHandler(list_bots_callback, pattern="^list_bots$|^page:list:"),
                CallbackQueryHandler(delete_bot_callback, pattern="^delete_bot$|^page:do_delete:"),
                CallbackQueryHandler(broadcast_callback, pattern="^broadcast$"),
                CallbackQueryHandler(broadcast_per_bot_callback, pattern="^broadcast_per_bot$|^page:broadcast_bot:"),
                CallbackQueryHandler(check_admin_callback, pattern="^check_admin$"),
                CallbackQueryHandler(clone_bot_callback, pattern="^clone_bot$"),
                CallbackQueryHandler(edit_welcome_callback, pattern="^edit_welcome$|^page:edit_welcome_bot:"),
                CallbackQueryHandler(edit_buttons_callback, pattern="^edit_buttons$|^page:edit_buttons_bot:"),
                CallbackQueryHandler(edit_bio_callback, pattern="^edit_bio$|^page:edit_bio_bot:"),
                CallbackQueryHandler(edit_theme_callback, pattern="^edit_theme$|^page:edit_theme_bot:"),
                CallbackQueryHandler(block_user_callback, pattern="^block_user$"),
                CallbackQueryHandler(unblock_user_callback, pattern="^unblock_user$"),
                CallbackQueryHandler(export_tokens_callback, pattern="^export_tokens$"),
                CallbackQueryHandler(backup_db_callback, pattern="^backup_db$"),
                CallbackQueryHandler(show_stats_callback, pattern="^show_stats$"),
                CallbackQueryHandler(show_health_callback, pattern="^show_health$"),
                CallbackQueryHandler(restart_all_callback, pattern="^restart_all$"),
                CallbackQueryHandler(stop_all_callback, pattern="^stop_all$"),
                CallbackQueryHandler(do_start_callback, pattern="^do_start:"),
                CallbackQueryHandler(do_stop_callback, pattern="^do_stop:"),
                CallbackQueryHandler(do_delete_callback, pattern="^do_delete:"),
                CallbackQueryHandler(bot_info_callback, pattern="^info:"),
                CallbackQueryHandler(edit_welcome_select_callback, pattern="^edit_welcome_bot:"),
                CallbackQueryHandler(edit_buttons_select_callback, pattern="^edit_buttons_bot:"),
                CallbackQueryHandler(edit_bio_select_callback, pattern="^edit_bio_bot:"),
                CallbackQueryHandler(edit_theme_select_callback, pattern="^edit_theme_bot:"),
                CallbackQueryHandler(set_theme_callback, pattern="^set_theme:"),
                CallbackQueryHandler(broadcast_bot_select_callback, pattern="^broadcast_bot:"),
                CallbackQueryHandler(page_handler, pattern="^page:"),
            ],
            STATE_WAITING_TOKENS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tokens),
            ],
            STATE_WAITING_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast),
            ],
            STATE_WAITING_BROADCAST_PER_BOT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_broadcast_per_bot),
            ],
            STATE_WAITING_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_channel_check),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_block_user),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_unblock_user),
            ],
            STATE_WAITING_CLONE_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_clone_source),
            ],
            STATE_WAITING_CLONE_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_clone_target),
            ],
            STATE_WAITING_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome),
            ],
            STATE_WAITING_BUTTONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_buttons),
            ],
            STATE_WAITING_BIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bio),
            ],
            STATE_WAITING_THEME: [
                CallbackQueryHandler(set_theme_callback, pattern="^set_theme:"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CommandHandler("start", start_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler),
        ],
        allow_reentry=True
    )

    app.add_handler(conv_handler)

    if AUTO_RESTART_ENABLED:
        asyncio.create_task(auto_restart_task())

    print("✅ Admin bot initialized")
    print("📱 Send /start to your admin bot")
    print("=" * 60)

    if WEBHOOK_URL:
        webhook_thread = threading.Thread(
            target=start_webhook_server,
            args=(HOST, PORT),
            daemon=True
        )
        webhook_thread.start()

        async def set_admin_webhook():
            async with Bot(ADMIN_BOT_TOKEN) as bot:
                await bot.set_webhook(
                    url=f"{WEBHOOK_URL}/webhook/admin",
                    allowed_updates=["message", "callback_query"]
                )

        loop.run_until_complete(set_admin_webhook())

        app.run_webhook(
            listen=HOST,
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/webhook/admin",
            drop_pending_updates=True
        )
    else:
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()

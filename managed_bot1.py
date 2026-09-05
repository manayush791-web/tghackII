"""
Managed Bot Pool Manager
Handles 1000+ bots without crashing via:
- On-demand Bot instance creation (not persistent Applications)
- LRU cache for active bots
- Shared aiohttp session
- Webhook-based updates (no polling connections)
- Semaphore-controlled concurrency
- Rate-limited API calls
"""
import json
import random
import asyncio
from collections import OrderedDict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

from config import DEFAULT_WELCOME, DEFAULT_BUTTONS, DICE_EMOJIS, PARTY_EMOJIS, MAX_CONCURRENT_BOTS
from database import db
from themes import format_welcome, get_random_dice, get_party_dice
from rate_limiter import rate_limiter
from utils import safe_api_call, health, hash_token
from plugins import call_hook

# ─── Bot Instance Cache (LRU) ───
# We keep only MAX_CONCURRENT_BOTS Bot objects in memory at a time
# This prevents memory exhaustion with 100+ bots
_bot_cache = OrderedDict()
_bot_cache_lock = asyncio.Lock()
_shared_session = None

# Track which bots are "active" (webhook set, receiving updates)
_active_bot_tokens = set()
_active_lock = asyncio.Lock()


async def _get_session():
    """Get or create shared aiohttp session"""
    global _shared_session
    if _shared_session is None or _shared_session.closed:
        import aiohttp
        _shared_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
        )
    return _shared_session


async def get_bot_instance(token):
    """Get a Bot instance from cache or create new one"""
    async with _bot_cache_lock:
        if token in _bot_cache:
            # Move to end (most recently used)
            _bot_cache.move_to_end(token)
            return _bot_cache[token]

        # Create new Bot instance with shared session
        session = await _get_session()
        bot = Bot(token)
        # Replace the bot's session with our shared one for efficiency
        # Note: In python-telegram-bot v21+, we need to be careful here
        # We'll create the bot normally and let it manage its own session
        # but close it properly when evicted from cache

        # If cache is full, remove oldest
        while len(_bot_cache) >= MAX_CONCURRENT_BOTS:
            oldest_token, oldest_bot = _bot_cache.popitem(last=False)
            try:
                await oldest_bot.session.close()
            except:
                pass

        _bot_cache[token] = bot
        return bot


async def clear_bot_cache():
    """Clear all cached bot instances"""
    async with _bot_cache_lock:
        for bot in _bot_cache.values():
            try:
                await bot.session.close()
            except:
                pass
        _bot_cache.clear()


# ─── Welcome Message Builder ───
def build_welcome_keyboard(buttons_json=None):
    """Build inline keyboard from stored buttons"""
    keyboard = []
    if buttons_json:
        try:
            stored = json.loads(buttons_json)
            for btn in stored:
                if btn.get("url"):
                    keyboard.append([InlineKeyboardButton(btn["text"], url=btn["url"])])
                elif btn.get("callback_data"):
                    keyboard.append([InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])])
        except:
            pass

    if not keyboard:
        for btn in DEFAULT_BUTTONS:
            keyboard.append([InlineKeyboardButton(btn["text"], url=btn["url"])])

    return InlineKeyboardMarkup(keyboard)


# ─── Update Handlers ───
async def handle_start(update: Update, token):
    """Handle /start for a managed bot"""
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return

    # Check if user is blocked
    if await db.is_user_blocked(user.id):
        return

    # Track user
    is_new = await db.add_user(
        user_id=user.id,
        bot_token=token,
        first_name=user.first_name or "User",
        username=user.username or "",
        chat_id=chat.id
    )

    # Call plugin hook
    try:
        await call_hook("on_user_joined", user.id, token)
    except:
        pass

    # Get bot settings
    bot_data = await db.get_bot(token)
    custom_msg = bot_data.get("welcome_msg") if bot_data else None
    buttons_json = bot_data.get("buttons_json") if bot_data else None
    theme = bot_data.get("theme") or "royal_gold"
    bio = bot_data.get("bio")

    # Build welcome
    welcome_text = format_welcome(
        user.first_name or "Friend",
        custom_msg=custom_msg,
        theme_name=theme,
        bio=bio
    )

    reply_markup = build_welcome_keyboard(buttons_json)

    bot = await get_bot_instance(token)

    try:
        async with rate_limiter:
            await safe_api_call(
                bot.send_message(
                    chat_id=chat.id,
                    text=welcome_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            )

        # Send animated dice for new users
        if is_new:
            dice_emoji = get_random_dice()
            async with rate_limiter:
                await safe_api_call(
                    bot.send_dice(chat_id=chat.id, emoji=dice_emoji)
                )

            # Small delay then send party popper
            await asyncio.sleep(0.5)
            async with rate_limiter:
                await safe_api_call(
                    bot.send_dice(chat_id=chat.id, emoji="🎉")
                )

    except Forbidden:
        # Bot was blocked by user
        pass
    except Exception as e:
        print(f"[ManagedBot] Welcome error for {token[:15]}...: {e}")
        health.record_error(e)


async def handle_help(update: Update, token):
    """Handle /help for managed bots"""
    chat = update.effective_chat
    if not chat:
        return

    bot = await get_bot_instance(token)
    help_text = """<b>🎉 Available Commands:</b>

/start - Start the bot & see welcome message
/help - Show this help message

<i>✨ Every message comes with animated surprises!</i>"""

    try:
        async with rate_limiter:
            await safe_api_call(
                bot.send_message(chat_id=chat.id, text=help_text, parse_mode=ParseMode.HTML)
            )
    except Exception as e:
        health.record_error(e)


async def process_update(token, update_dict):
    """Process an incoming update for a managed bot"""
    bot = await get_bot_instance(token)
    update = Update.de_json(update_dict, bot)

    if not update.message:
        return

    text = update.message.text or ""

    if text.startswith("/start"):
        await handle_start(update, token)
    elif text.startswith("/help"):
        await handle_help(update, token)
    else:
        # Plugin hook for text messages
        try:
            results = await call_hook("on_text_received", update, token)
            if any(results):
                return
        except:
            pass


# ─── Bot Lifecycle ───
async def start_managed_bot(token, webhook_base_url):
    """Start a managed bot by setting its webhook"""
    if await is_bot_running(token):
        return False, "Bot already running"

    try:
        bot = await get_bot_instance(token)

        # Verify token
        me = await safe_api_call(bot.get_me())
        if not me:
            return False, "Invalid token or API error"

        # Update DB
        await db.add_bot(token, username=me.username)
        await db.update_bot_status(token, "running")
        await db.increment_bot_start(token)
        await db.update_bot_username(token, me.username)

        # Set webhook
        if webhook_base_url:
            webhook_path = f"/webhook/{hash_token(token)}"
            webhook_url = f"{webhook_base_url}{webhook_path}"

            async with rate_limiter:
                await safe_api_call(
                    bot.set_webhook(
                        url=webhook_url,
                        allowed_updates=["message", "callback_query"],
                        drop_pending_updates=True
                    )
                )

        async with _active_lock:
            _active_bot_tokens.add(token)

        health.record_bot_start()

        try:
            await call_hook("on_bot_started", token, me.username)
        except:
            pass

        return True, me.username
    except Exception as e:
        health.record_error(e)
        return False, str(e)


async def stop_managed_bot(token):
    """Stop a managed bot by deleting its webhook"""
    if not await is_bot_running(token):
        return False, "Bot not running"

    try:
        bot = await get_bot_instance(token)

        async with rate_limiter:
            await safe_api_call(bot.delete_webhook(drop_pending_updates=True))

        await db.update_bot_status(token, "stopped")
        await db.increment_bot_stop(token)

        async with _active_lock:
            _active_bot_tokens.discard(token)

        # Remove from cache
        async with _bot_cache_lock:
            if token in _bot_cache:
                try:
                    await _bot_cache[token].session.close()
                except:
                    pass
                del _bot_cache[token]

        health.record_bot_stop()

        # Get username for response
        bot_data = await db.get_bot(token)
        username = bot_data.get("username") if bot_data else "Unknown"

        try:
            await call_hook("on_bot_stopped", token, username)
        except:
            pass

        return True, username
    except Exception as e:
        health.record_error(e)
        return False, str(e)


async def stop_all_managed_bots():
    """Stop all running managed bots"""
    tokens = list(_active_bot_tokens)
    results = []
    for token in tokens:
        success, msg = await stop_managed_bot(token)
        results.append((token, success, msg))
    return results


async def is_bot_running(token):
    """Check if a bot is currently active"""
    async with _active_lock:
        return token in _active_bot_tokens


def get_running_bots():
    """Get list of running bot tokens"""
    return list(_active_bot_tokens)


async def get_running_bots_info():
    """Get detailed info about running bots"""
    info = []
    for token in _active_bot_tokens:
        bot_data = await db.get_bot(token)
        if bot_data:
            info.append({
                "token": token,
                "username": bot_data.get("username"),
                "status": bot_data.get("status")
            })
    return info


# ─── Broadcast ───
async def broadcast_to_bot(token, message_text, status_callback=None):
    """Broadcast a message to all users of a specific bot"""
    users = await db.get_all_users(bot_token=token, limit=50000)
    if not users:
        return 0, 0

    bot = await get_bot_instance(token)
    sent = 0
    failed = 0

    for i, user_info in enumerate(users):
        user_id = user_info["user_id"]
        chat_id = user_info["chat_id"]

        # Check if blocked
        if await db.is_user_blocked(user_id):
            failed += 1
            continue

        try:
            async with rate_limiter:
                await safe_api_call(
                    bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                )
            sent += 1
        except Forbidden:
            # User blocked the bot
            failed += 1
        except BadRequest as e:
            failed += 1
            print(f"[Broadcast] BadRequest to {chat_id}: {e}")
        except Exception as e:
            failed += 1
            print(f"[Broadcast] Error to {chat_id}: {e}")
            health.record_error(e)

        # Rate limit delay
        if (i + 1) % 30 == 0:
            await asyncio.sleep(1.2)
            if status_callback:
                await status_callback(sent, failed, len(users))

    return sent, failed


async def broadcast_to_all(message_text, status_callback=None):
    """Broadcast to ALL users across ALL bots"""
    users = await db.get_all_users(limit=100000)
    if not users:
        return 0, 0

    sent = 0
    failed = 0

    for i, user_info in enumerate(users):
        user_id = user_info["user_id"]
        chat_id = user_info["chat_id"]
        bot_token = user_info["bot_token"]

        if await db.is_user_blocked(user_id):
            failed += 1
            continue

        try:
            bot = await get_bot_instance(bot_token)
            async with rate_limiter:
                await safe_api_call(
                    bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                )
            sent += 1
        except Forbidden:
            failed += 1
        except Exception as e:
            failed += 1
            print(f"[Broadcast All] Error: {e}")
            health.record_error(e)

        if (i + 1) % 30 == 0:
            await asyncio.sleep(1.2)
            if status_callback:
                await status_callback(sent, failed, len(users))

    return sent, failed

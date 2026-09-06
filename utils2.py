"""
Utility functions for the Bot Manager
"""
import hashlib
import re
import time
import asyncio
from datetime import datetime

def hash_token(token):
    """Create a URL-safe hash of a bot token for webhook paths"""
    return hashlib.sha256(token.encode()).hexdigest()[:16]

def parse_tokens(text):
    """Parse multiple bot tokens from text input"""
    tokens = []
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove quotes
        if (line.startswith('"') and line.endswith('"')) or \
           (line.startswith("'") and line.endswith("'")):
            line = line[1:-1]
        # Validate token format
        if re.match(r'^\d+:[A-Za-z0-9_-]+$', line):
            tokens.append(line)
    return tokens

def truncate_text(text, max_len=100):
    return text[:max_len] + "..." if len(text) > max_len else text

def format_number(n):
    """Format large numbers with commas"""
    return f"{n:,}"

def uptime_string(start_time):
    """Format uptime from start timestamp"""
    delta = int(time.time() - start_time)
    days = delta // 86400
    hours = (delta % 86400) // 3600
    mins = (delta % 3600) // 60
    secs = delta % 60
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if mins: parts.append(f"{mins}m")
    if secs or not parts: parts.append(f"{secs}s")
    return " ".join(parts)

def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def safe_api_call(coro, retries=3, backoff=2):
    """Execute an API call with retry and exponential backoff"""
    from telegram.error import RetryAfter, NetworkError, TimedOut

    for attempt in range(retries):
        try:
            return await coro
        except RetryAfter as e:
            wait = e.retry_after + 1
            print(f"[RateLimit] FloodWait {wait}s, attempt {attempt+1}/{retries}")
            await asyncio.sleep(wait)
        except (NetworkError, TimedOut) as e:
            wait = backoff ** attempt
            print(f"[Network] Error: {e}, retrying in {wait}s ({attempt+1}/{retries})")
            await asyncio.sleep(wait)
        except Exception as e:
            print(f"[API Error] {e}")
            if attempt == retries - 1:
                raise
    return None

class HealthMonitor:
    """Simple health monitoring"""
    def __init__(self):
        self.start_time = time.time()
        self.bot_start_count = 0
        self.bot_stop_count = 0
        self.broadcast_count = 0
        self.error_count = 0
        self.last_error = None

    def record_bot_start(self):
        self.bot_start_count += 1

    def record_bot_stop(self):
        self.bot_stop_count += 1

    def record_broadcast(self):
        self.broadcast_count += 1

    def record_error(self, error):
        self.error_count += 1
        self.last_error = str(error)[:200]

    def status(self):
        return {
            "uptime": uptime_string(self.start_time),
            "bot_starts": self.bot_start_count,
            "bot_stops": self.bot_stop_count,
            "broadcasts": self.broadcast_count,
            "errors": self.error_count,
            "last_error": self.last_error,
            "status": "healthy" if self.error_count < 100 else "degraded"
        }

health = HealthMonitor()

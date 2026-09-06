"""
Telegram API Rate Limiter
"""
import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_concurrent=50, per_chat_limit=20, per_chat_window=60, per_bot_limit=30, per_bot_window=1):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.per_chat_limit = per_chat_limit
        self.per_chat_window = per_chat_window
        self.per_bot_limit = per_bot_limit
        self.per_bot_window = per_bot_window

        self._chat_history = defaultdict(list)
        self._bot_history = defaultdict(list)
        self._lock = asyncio.Lock()

    async def acquire(self, bot_token=None, chat_id=None):
        await self.semaphore.acquire()

        if bot_token or chat_id:
            async with self._lock:
                now = time.time()

                if chat_id:
                    history = self._chat_history[chat_id]
                    cutoff = now - self.per_chat_window
                    self._chat_history[chat_id] = [t for t in history if t > cutoff]

                    if len(self._chat_history[chat_id]) >= self.per_chat_limit:
                        wait_time = self.per_chat_window - (now - self._chat_history[chat_id][0])
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)

                    self._chat_history[chat_id].append(time.time())

                if bot_token:
                    history = self._bot_history[bot_token]
                    cutoff = now - self.per_bot_window
                    self._bot_history[bot_token] = [t for t in history if t > cutoff]

                    if len(self._bot_history[bot_token]) >= self.per_bot_limit:
                        wait_time = self.per_bot_window - (now - self._bot_history[bot_token][0])
                        if wait_time > 0:
                            await asyncio.sleep(wait_time)

                    self._bot_history[bot_token].append(time.time())

    def release(self):
        try:
            self.semaphore.release()
        except ValueError:
            pass

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.release()


rate_limiter = RateLimiter()

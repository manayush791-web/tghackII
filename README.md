# 🤖 Telegram Bot Manager v3.0

**Ultimate multi-bot management system** — handles 1000+ Telegram bots without crashing.

## ✨ What's New in v3.0

| Feature | Description |
|---------|-------------|
| 🌐 **Webhook Architecture** | Zero persistent connections — perfect for Render |
| 📄 **Paginated Lists** | No more "message too long" crashes with 102+ bots |
| ⚡ **Async Database** | `aiosqlite` — fully non-blocking |
| 🚦 **Rate Limiter** | Token-bucket + semaphore prevents 429 errors |
| 🎲 **Working Animated Dice** | Real `send_dice` with 🎲🎯🏀⚽🎳🎰🎉 |
| 📡 **Per-Bot Broadcast** | Broadcast to specific bot users only |
| 🚫 **User Blocking** | Block spammers from all bots |
| 💾 **DB Backups** | One-click SQLite backup |
| 🩺 **Health Monitor** | Uptime, errors, bot counts |
| 🔄 **Auto-Restart** | Scheduled restart every 60 min |
| 🎨 **6 Premium Themes** | Royal Gold, Neon Cyber, Soft Pastel, Dark Elite, Celebration, Ocean Wave |
| 📝 **Bio Editor** | Per-bot about/bio text |
| 🔌 **Plugin System** | Add features without touching core code |

## 🚀 Quick Start

### 1. Install
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your tokens and settings
```

### 3. Run (local — polling mode)
```bash
python main.py
```

### 4. Deploy on Render (webhook mode)
Set these environment variables in Render dashboard:
- `ADMIN_BOT_TOKEN`
- `ADMIN_IDS`
- `WEBHOOK_URL` = `https://your-app.onrender.com`

Then deploy. The webhook server starts automatically.

## 🎯 Why v3.0 Doesn't Crash

| Old Problem | v3.0 Solution |
|-------------|---------------|
| 102 `Application` polling instances | Single `Bot` instances with LRU cache (max 20) |
| 102 persistent connections | Webhooks — zero connections |
| Blocking SQLite (`threading.Lock`) | `aiosqlite` — fully async |
| No rate limiting | Token-bucket + semaphore (50 max concurrent) |
| 102 buttons in one message | Paginated: 8 per page with Prev/Next |
| Broadcast flood = 429 crash | Batched: 30 msgs + 1.2s delay |
| Memory leaks over time | Auto-restart every 60 minutes |
| Fake animated emoji text | Real `send_dice` API calls |

## 📁 File Structure

```
tghack-upgraded/
├── main.py              ← Admin bot (paginated, async, webhook)
├── managed_bot.py       ← Bot pool (LRU cache, rate limits)
├── webhook_server.py    ← Flask webhook receiver for Render
├── database.py          ← Async SQLite (aiosqlite)
├── config.py            ← .env configuration loader
├── rate_limiter.py      ← Telegram API rate limiter
├── themes.py            ← 6 themes + animated dice
├── utils.py             ← Helpers, health monitor
├── plugins/
│   ├── __init__.py      ← Plugin loader & hook system
│   └── example_plugin.py
├── .env.example
└── requirements.txt
```

## 📜 License

MIT — use freely, modify boldly.

# 🤖 Telegram Bot Manager v3.0

**Ultimate multi-bot management** — handles 1000+ Telegram bots without crashing.

## 🚀 Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens
python main.py
```

## 🎯 What Was Fixed

| Problem | Fix |
|---|---|
| 102 bots = crash | Webhooks + LRU cache (max 20 bots in memory) |
| Port conflict | Flask is the ONLY server |
| Flood control | Admin bot webhook set ONCE manually |
| "Message too long" | Paginated lists (8 bots/page) |
| Fake animated emoji | Real `send_dice` API (🎲🎯🏀⚽🎳🎰🎉) |

## 📁 Files

```
tghack-upgraded-fixed/
├── main.py              ← Admin bot (Flask feeds updates)
├── managed_bot.py       ← Bot pool (LRU cache, rate limits)
├── webhook_server.py    ← Flask — the ONLY server
├── database.py          ← Async SQLite
├── config.py            ← .env loader
├── rate_limiter.py      ← API throttle
├── themes.py            ← 6 themes + animated dice
├── utils.py             ← Helpers + health monitor
├── plugins/
│   ├── __init__.py
│   └── example_plugin.py
├── .env.example
└── requirements.txt
```

## 🔧 Render Deploy

1. Set env vars:
   - `ADMIN_BOT_TOKEN`
   - `ADMIN_IDS`
   - `WEBHOOK_URL=https://your-app.onrender.com`
2. Deploy
3. Done — no crashes

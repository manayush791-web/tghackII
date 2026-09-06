"""
Premium Themes & Working Animated Content
"""
import random

# ─── Default Welcome Message ───
DEFAULT_WELCOME = """<blockquote expandable>
✨ <b>Welcome to the Premium Experience</b> ✨
</blockquote>

🎉 <b>Hello {first_name}!</b> 🎉

💖 <i>We're absolutely thrilled to have you here!</i> 💖

🌟 <b>What awaits you:</b>
├ 🔥 Premium animated content
├ ⚡ Lightning-fast updates
├ 💎 Exclusive member benefits
├ 🎊 Interactive touch-to-animate emoji
└ 🎁 Hidden surprises everywhere!

🎈 <b>Enjoy your stay and explore!</b> 🎈

<tg-spoiler>🎁 Tap any emoji to see it come alive!</tg-spoiler>"""

# ─── Default Buttons ───
DEFAULT_BUTTONS = [
    {"text": "📢 Join Our Channel", "url": "https://t.me/father_ddos"},
    {"text": "💬 Contact Support", "url": "https://t.me/dev_ker"}
]

# ─── Dice & Party Emojis ───
DICE_EMOJIS = ["🎲", "🎯", "🏀", "⚽", "🎳", "🎰"]
PARTY_EMOJIS = ["🎉", "🎊", "🎈", "🎁", "🎆", "🎇"]

THEMES = {
    "royal_gold": {
        "name": "👑 Royal Gold",
        "header": "👑 ✨ 🏆 ✨ 👑",
        "footer": "💫 🥇 💎 🥇 💫",
        "accent": "🟡",
        "decorations": ["✨", "🌟", "💎", "👑", "🏆", "🥇", "⚜️", "🔱"],
        "divider": "━",
        "color_tone": "warm"
    },
    "neon_cyber": {
        "name": "⚡ Neon Cyber",
        "header": "⚡ 🔥 💀 🔥 ⚡",
        "footer": "💎 🌃 🚀 🌃 💎",
        "accent": "🔵",
        "decorations": ["⚡", "🔥", "💀", "🤖", "🚀", "🌃", "🔮", "🛸"],
        "divider": "═",
        "color_tone": "cool"
    },
    "soft_pastel": {
        "name": "🌸 Soft Pastel",
        "header": "🌸 💖 🌈 💖 🌸",
        "footer": "☁️ 🦋 💫 🦋 ☁️",
        "accent": "🩷",
        "decorations": ["🌸", "💖", "🌈", "☁️", "🦋", "💫", "🍥", "🎀"],
        "divider": "─",
        "color_tone": "soft"
    },
    "dark_elite": {
        "name": "🖤 Dark Elite",
        "header": "🖤 🌑 ⚫ 🌑 🖤",
        "footer": "⬛ 🥀 🖤 🥀 ⬛",
        "accent": "⬛",
        "decorations": ["🖤", "🌑", "⚫", "🥀", "🦇", "🌙", "🗡️", "🛡️"],
        "divider": "▪",
        "color_tone": "dark"
    },
    "celebration": {
        "name": "🎉 Celebration",
        "header": "🎉 🎊 🎈 🎊 🎉",
        "footer": "🎁 🍾 🥂 🍾 🎁",
        "accent": "🎊",
        "decorations": ["🎉", "🎊", "🎈", "🎁", "🍾", "🥂", "🎆", "🎇"],
        "divider": "✦",
        "color_tone": "party"
    },
    "ocean_wave": {
        "name": "🌊 Ocean Wave",
        "header": "🌊 🐬 🐳 🐬 🌊",
        "footer": "🐚 🦀 🌴 🦀 🐚",
        "accent": "🔷",
        "decorations": ["🌊", "🐬", "🐳", "🐚", "🦀", "🌴", "🏝️", "🐙"],
        "divider": "~",
        "color_tone": "fresh"
    }
}

DEFAULT_THEME = "royal_gold"


def get_theme(theme_name):
    return THEMES.get(theme_name, THEMES[DEFAULT_THEME])


def random_theme():
    return random.choice(list(THEMES.keys()))


def format_welcome(first_name, custom_msg=None, theme_name="royal_gold", bio=None):
    theme = get_theme(theme_name)
    header = theme["header"]
    footer = theme["footer"]
    deco = random.choice(theme["decorations"])
    div = theme["divider"]

    if custom_msg:
        msg = custom_msg.replace("{first_name}", first_name)
    else:
        msg = DEFAULT_WELCOME.replace("{first_name}", first_name)

    if bio:
        msg += f"\n\n📋 <b>About:</b>\n<blockquote>{bio}</blockquote>"

    full = f"""{header}

{msg}

{div * 20}

{footer}"""

    return full


def get_random_dice():
    return random.choice(DICE_EMOJIS)


def get_party_dice():
    return "🎉"

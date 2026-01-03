#!/usr/bin/env python3
import os
import logging
import asyncio
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ⚡ Для работы с Jupyter/online env, исправляет "event loop already running"
try:
    import nest_asyncio
    nest_asyncio.apply()
except:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# ===================== DATABASE =====================
class GameDB:
    def __init__(self, path="bot.db"):
        self.path = path

    async def init_db(self):
        async with aiosqlite.connect(self.path) as db:
            # Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    vip_until DATETIME,
                    coins INTEGER DEFAULT 0,
                    exp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    duels_won INTEGER DEFAULT 0,
                    duels_lost INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Игровые предметы
            await db.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT,
                    price INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Инвентарь
            await db.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    user_id INTEGER,
                    item_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    PRIMARY KEY(user_id,item_id),
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(item_id) REFERENCES items(item_id)
                )
            """)
            # Промокоды
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    coins INTEGER,
                    expires_at DATETIME
                )
            """)
            # Дуэли
            await db.execute("""
                CREATE TABLE IF NOT EXISTS duels (
                    duel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user1_id INTEGER,
                    user2_id INTEGER,
                    stake INTEGER,
                    winner_id INTEGER,
                    status TEXT DEFAULT 'waiting',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("✅ Database initialized")

    async def add_user(self, user_id, username, first_name):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user_id, username, first_name))
            await db.commit()

    async def get_user(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
                return await cur.fetchone()

    async def add_coins(self, user_id, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
            await db.commit()

    async def add_exp(self, user_id, amount):
        async with aiosqlite.connect(self.path) as db:
            user = await self.get_user(user_id)
            new_exp = (user[5] + amount)
            new_level = user[6]
            # Левел ап каждые 100 exp
            if new_exp >= new_level*100:
                new_level += 1
                new_exp = new_exp - (new_level-1)*100
            await db.execute("UPDATE users SET exp=?, level=? WHERE user_id=?", (new_exp, new_level, user_id))
            await db.commit()

    async def get_top(self, limit=10, criteria="coins"):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(f"SELECT username, coins, level FROM users ORDER BY {criteria} DESC LIMIT ?", (limit,)) as cur:
                return await cur.fetchall()

    async def add_item(self, name, desc, price):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO items (name, description, price) VALUES (?, ?, ?)", (name, desc, price))
            await db.commit()

    async def get_items(self):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT item_id, name, description, price FROM items") as cur:
                return await cur.fetchall()

    async def add_inventory(self, user_id, item_id, quantity=1):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                INSERT INTO inventory (user_id, item_id, quantity) 
                VALUES (?, ?, ?) 
                ON CONFLICT(user_id,item_id) DO UPDATE SET quantity = quantity + ?
            """, (user_id, item_id, quantity, quantity))
            await db.commit()

db = GameDB()
asyncio.run(db.init_db())

# ===================== BOT =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)
    keyboard = [
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("💎 Профиль", callback_data="profile")],
        [InlineKeyboardButton("⚔ Дуэли", callback_data="duels")],
        [InlineKeyboardButton("🏹 Экспедиции", callback_data="expeditions")],
        [InlineKeyboardButton("📊 Топ-10", callback_data="top10")],
        [InlineKeyboardButton("💰 Купить VIP", url="https://t.me/<YOUR_USERNAME>")]
    ]
    await update.message.reply_text(
        f"Привет, {user.first_name}! Выбери действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "shop":
        await show_shop(query)
    elif data == "profile":
        await show_profile(query)
    elif data == "duels":
        await show_duels(query)
    elif data == "expeditions":
        await show_expeditions(query)
    elif data == "top10":
        await show_top10(query)

# ===================== SHOP =====================
async def show_shop(query):
    items = await db.get_items()
    if not items:
        text = "Магазин пока пуст."
    else:
        text = "🛒 **Магазин:**\n\n"
        for item_id, name, desc, price in items:
            text += f"🪙 {name} ({price} монет)\nОписание: {desc}\n\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ===================== PROFILE =====================
async def show_profile(query):
    user = await db.get_user(query.from_user.id)
    if not user:
        await query.edit_message_text("Пользователь не найден")
        return
    text = f"""
👤 {user[2]} (@{user[1]})
💰 Монеты: {user[4]}
🎯 Опыт: {user[5]}
🏆 Уровень: {user[6]}
⚔ Дуэли: {user[7]} побед / {user[8]} поражений
💎 VIP до: {user[3] or "нет"}
"""
    await query.edit_message_text(text, parse_mode="Markdown")

# ===================== TOP10 =====================
async def show_top10(query):
    top = await db.get_top()
    text = "🏆 **Топ игроков по монетам:**\n\n"
    for i, (username, coins, level) in enumerate(top, 1):
        text += f"{i}. @{username} - {coins} монет, уровень {level}\n"
    await query.edit_message_text(text, parse_mode="Markdown")

# ===================== DUELS =====================
async def show_duels(query):
    text = "⚔ Дуэли пока находятся в разработке."
    await query.edit_message_text(text)

# ===================== EXPEDITIONS =====================
async def show_expeditions(query):
    text = "🏹 Экспедиции пока находятся в разработке."
    await query.edit_message_text(text)

# ===================== MAIN =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    logger.info("🚀 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

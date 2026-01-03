#!/usr/bin/env python3
import os
import logging
import aiosqlite
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# ----------------- ENV -----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# ----------------- DATABASE -----------------
class GameDB:
    def __init__(self, path="bot.db"):
        self.path = path

    async def init_db(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    vip_until DATETIME,
                    currency INTEGER DEFAULT 0,
                    total_score INTEGER DEFAULT 0,
                    games_played INTEGER DEFAULT 0,
                    best_score INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    score INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    amount INTEGER,
                    used_by TEXT
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

    async def add_score(self, user_id, score, currency=0):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT INTO games (user_id, score) VALUES (?, ?)", (user_id, score))
            await db.execute("""
                UPDATE users
                SET total_score = total_score + ?,
                    currency = currency + ?,
                    games_played = games_played + 1,
                    best_score = MAX(best_score, ?)
                WHERE user_id = ?
            """, (score, currency, score, user_id))
            await db.commit()

    async def get_user_stats(self, user_id):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("""
                SELECT total_score, games_played, best_score, vip_until, currency
                FROM users WHERE user_id = ?
            """, (user_id,)) as cur:
                return await cur.fetchone() or (0,0,0,None,0)

    async def get_leaderboard(self, limit=10):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("""
                SELECT first_name, total_score, games_played, best_score
                FROM users ORDER BY total_score DESC LIMIT ?
            """, (limit,)) as cur:
                return await cur.fetchall()

    async def give_vip(self, user_id, days=0):
        async with aiosqlite.connect(self.path) as db:
            if days==0:
                vip_until = None
            else:
                vip_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (vip_until, user_id))
            await db.commit()

    async def give_currency(self, user_id, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET currency = currency + ? WHERE user_id=?", (amount, user_id))
            await db.commit()

    async def add_promo(self, code, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR IGNORE INTO promo_codes (code, amount) VALUES (?,?)", (code, amount))
            await db.commit()

    async def use_promo(self, user_id, code):
        async with aiosqlite.connect(self.path) as db:
            async with db.execute("SELECT amount, used_by FROM promo_codes WHERE code=?", (code,)) as cur:
                row = await cur.fetchone()
                if not row:
                    return 0
                amount, used_by = row
                used = used_by.split(",") if used_by else []
                if str(user_id) in used:
                    return 0
                used.append(str(user_id))
                await db.execute("UPDATE promo_codes SET used_by=? WHERE code=?", (",".join(used), code))
                await self.give_currency(user_id, amount)
                await db.commit()
                return amount

db = GameDB()

# ----------------- START -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)
    keyboard = [
        [InlineKeyboardButton("⛏️ Добыча", callback_data="mine")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏆 Топ-10", callback_data="leaderboard")],
        [InlineKeyboardButton("💎 VIP", callback_data="vip")],
        [InlineKeyboardButton("🎁 Промокод", callback_data="promo")],
    ]
    await update.message.reply_text("🎮 Выберите действие:", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- BUTTON CALLBACK -----------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "mine":
        await mine_game(query)
    elif data == "profile":
        await show_profile(query)
    elif data == "leaderboard":
        await show_leaderboard(query)
    elif data == "vip":
        await query.edit_message_text("Для VIP обращайтесь к администратору")
    elif data == "promo":
        await query.edit_message_text("Отправьте /usepromo <код> для активации")

# ----------------- GAME -----------------
async def mine_game(query):
    await query.edit_message_text("⛏️ Добыча в процессе... 3 секунды")
    await asyncio.sleep(3)
    currency = random.randint(5, 25)
    score = random.randint(1, 10)
    await db.add_score(query.from_user.id, score, currency)
    await query.edit_message_text(f"✅ Вы получили {currency} монет и {score} очков!")

# ----------------- PROFILE -----------------
async def show_profile(query):
    total, games, best, vip_until, currency = await db.get_user_stats(query.from_user.id)
    vip_text = f"VIP до {vip_until}" if vip_until else "Нет VIP"
    await query.edit_message_text(
        f"📊 Профиль {query.from_user.first_name}\n"
        f"💰 Монеты: {currency}\n"
        f"⚡ Всего очков: {total}\n"
        f"🎮 Игр: {games}\n"
        f"🎯 Рекорд: {best}\n"
        f"👑 {vip_text}"
    )

# ----------------- LEADERBOARD -----------------
async def show_leaderboard(query):
    top = await db.get_leaderboard()
    text = "🏆 ТОП-10 игроков:\n"
    for i, (name, score, games, best) in enumerate(top, 1):
        text += f"{i}. {name} — {score} очков | {games} игр | Рекорд: {best}\n"
    await query.edit_message_text(text)

# ----------------- PROMOCODE -----------------
async def use_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /usepromo <код>")
        return
    code = context.args[0]
    amount = await db.use_promo(update.effective_user.id, code)
    if amount:
        await update.message.reply_text(f"🎉 Промокод активирован! Вы получили {amount} монет")
    else:
        await update.message.reply_text("❌ Неверный промокод или уже использован")

# ----------------- ADMIN -----------------
async def give_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 1:
        await update.message.reply_text("/givevip <user_id> [days]")
        return
    user_id = int(context.args[0])
    days = int(context.args[1]) if len(context.args) > 1 else 0
    await db.give_vip(user_id, days)
    await update.message.reply_text("✅ VIP выдан!")

async def give_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("/givecurrency <user_id> <amount>")
        return
    user_id = int(context.args[0])
    amount = int(context.args[1])
    await db.give_currency(user_id, amount)
    await update.message.reply_text(f"✅ {amount} монет выданы пользователю {user_id}")

# ----------------- MAIN -----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("usepromo", use_promo))
    app.add_handler(CommandHandler("givevip", give_vip))
    app.add_handler(CommandHandler("givecurrency", give_currency))
    # Инициализация базы
    import asyncio
    asyncio.get_event_loop().run_until_complete(db.init_db())
    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()

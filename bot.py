#!/usr/bin/env python3
import os
import logging
import aiosqlite
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",")]

# ----------------- База данных -----------------
class GameDatabase:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
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
            await db.commit()
            logger.info("✅ DB initialized")

    async def add_user(self, user_id, username, first_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user_id, username, first_name))
            await db.commit()

    async def add_score(self, user_id, score):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO games (user_id, score) VALUES (?, ?)", (user_id, score))
            await db.execute("""
                UPDATE users
                SET total_score = total_score + ?,
                    games_played = games_played + 1,
                    best_score = MAX(best_score, ?)
                WHERE user_id = ?
            """, (score, score, user_id))
            await db.commit()

    async def get_user_stats(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("""
                SELECT total_score, games_played, best_score
                FROM users WHERE user_id = ?
            """, (user_id,)) as cursor:
                return await cursor.fetchone() or (0, 0, 0)

db = GameDatabase()

# ----------------- Хендлеры -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name)

    keyboard = [
        [InlineKeyboardButton("🎮 Играть!", callback_data="play_game")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏆 Топ-10", callback_data="leaderboard")]
    ]
    await update.message.reply_text(
        f"🎉 Добро пожаловать, {user.first_name}!\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "play_game":
        await start_game(query)
    elif data == "profile":
        await show_profile(query)
    elif data == "leaderboard":
        await show_leaderboard(query)

async def start_game(query):
    await query.edit_message_text("🎮 Игра началась! Ждём 5 секунд...")
    await asyncio.sleep(5)
    score = random.randint(10, 50)
    await db.add_score(query.from_user.id, score)
    await query.edit_message_text(f"🏁 Игра закончена! Очки: {score}")

async def show_profile(query):
    total, games, best = await db.get_user_stats(query.from_user.id)
    await query.edit_message_text(
        f"📊 Профиль {query.from_user.first_name}\n"
        f"💰 Всего очков: {total}\n"
        f"⚡ Игр: {games}\n"
        f"🎯 Рекорд: {best}"
    )

async def show_leaderboard(query):
    async with aiosqlite.connect(db.db_path) as conn:
        async with conn.execute("SELECT first_name, total_score FROM users ORDER BY total_score DESC LIMIT 10") as cur:
            rows = await cur.fetchall()
    text = "🏆 ТОП-10 игроков:\n"
    for i, (name, score) in enumerate(rows, 1):
        text += f"{i}. {name} — {score} очков\n"
    await query.edit_message_text(text)

# ----------------- Основной запуск -----------------
async def main():
    await db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

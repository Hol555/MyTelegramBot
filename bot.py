#!/usr/bin/env python3
import os
import asyncio
import logging
import random
import time
from datetime import datetime
import aiosqlite
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- CONFIG ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x]
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME","YOUR_USERNAME")

DB_PATH = "bot.db"
VIP_BONUS_MULTIPLIER = 2
GAME_RESOURCES = ["gold","gems","crystals"]
RARE_RESOURCES = ["diamond","artifact","crystal_shard"]

# ---------------- DATABASE ----------------
class DB:
    def __init__(self, path=DB_PATH):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                gold INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                crystals INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                vip_until INTEGER,
                banned INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS duels(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1 INTEGER,
                player2 INTEGER,
                stake_currency TEXT,
                stake_amount INTEGER,
                winner INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS promocodes(
                code TEXT PRIMARY KEY,
                currency TEXT,
                amount INTEGER,
                active INTEGER DEFAULT 1
            );
            """)
            await db.commit()

    async def add_user(self, u):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users(user_id,username) VALUES (?,?)",
                (u.id,u.username or "NoUsername")
            )
            await db.commit()

    async def get_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            c = await db.execute("SELECT * FROM users WHERE user_id=?",(uid,))
            return await c.fetchone()

    async def update_currency(self, uid, currency, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(f"UPDATE users SET {currency}={currency}+? WHERE user_id=?",(amount,uid))
            await db.commit()

    async def add_xp(self, uid, xp):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET xp=xp+? WHERE user_id=?",(xp,uid))
            user = await self.get_user(uid)
            if user:
                new_level = (user[5]+xp)//50 +1
                if new_level>user[6]:
                    await db.execute("UPDATE users SET level=? WHERE user_id=?",(new_level,uid))
            await db.commit()

    async def set_vip(self, uid, until_timestamp):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET vip_until=? WHERE user_id=?",(until_timestamp,uid))
            await db.commit()

    async def ban_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET banned=1 WHERE user_id=?",(uid,))
            await db.commit()

    async def unban_user(self, uid):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("UPDATE users SET banned=0 WHERE user_id=?",(uid,))
            await db.commit()

    async def get_top(self, field="gold", limit=10):
        async with aiosqlite.connect(self.path) as db:
            c = await db.execute(f"SELECT username,{field} FROM users ORDER BY {field} DESC LIMIT ?",(limit,))
            return await c.fetchall()

    async def add_promocode(self, code, currency, amount):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("INSERT OR REPLACE INTO promocodes(code,currency,amount,active) VALUES (?,?,?,1)",(code,currency,amount))
            await db.commit()

    async def use_promocode(self, code):
        async with aiosqlite.connect(self.path) as db:
            c = await db.execute("SELECT currency,amount,active FROM promocodes WHERE code=?",(code,))
            result = await c.fetchone()
            if result and result[2]==1:
                await db.execute("UPDATE promocodes SET active=0 WHERE code=?",(code,))
                await db.commit()
                return result[0],result[1]
            return None,None

db = DB()

# ---------------- HELPERS ----------------
def vip_text(vip_until):
    if vip_until==0: return "♾ навсегда"
    if vip_until and vip_until>int(time.time()): return datetime.fromtimestamp(vip_until).strftime("%d.%m.%Y")
    return "—"

def is_vip(vip_until):
    if vip_until is None: return False
    if vip_until==0: return True
    return vip_until>int(time.time())

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await db.add_user(update.effective_user)
    kb = [
        [InlineKeyboardButton("🎮 Добыча",callback_data="farm")],
        [InlineKeyboardButton("🗺 Экспедиции",callback_data="expedition")],
        [InlineKeyboardButton("👤 Профиль",callback_data="profile")],
        [InlineKeyboardButton("🏆 Топ-10",callback_data="stats")],
        [InlineKeyboardButton("💎 Купить VIP",url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    if update.effective_user.id in ADMIN_IDS:
        kb.append([InlineKeyboardButton("🛠 Админ панель",callback_data="admin")])
    await update.message.reply_text("🎮 Добро пожаловать!",reply_markup=InlineKeyboardMarkup(kb))

# ---------------- CALLBACK ----------------
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    user = await db.get_user(uid)
    if not user:
        await db.add_user(q.from_user)
        user = await db.get_user(uid)

    # ---------------- PROFILE ----------------
    if data=="profile":
        text = f"👤 Профиль @{user[1]}\n💰 Gold: {user[2]}\n💎 Gems: {user[3]}\n🔹 Crystals: {user[4]}\n⚡ XP: {user[5]}\n🏆 Level: {user[6]}\n👑 VIP: {vip_text(user[7])}\nWins: {user[9]}\nLosses: {user[10]}"
        kb = [[InlineKeyboardButton("🏠 Главное меню",callback_data="main")]]
        await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb))

    # ---------------- FARM ----------------
    elif data=="farm":
        multiplier = VIP_BONUS_MULTIPLIER if is_vip(user[7]) else 1
        resource = random.choice(GAME_RESOURCES)
        amount = int(random.randint(1,10)*multiplier)
        await db.update_currency(uid,resource,amount)
        await db.add_xp(uid,random.randint(1,5)*multiplier)
        kb = [[InlineKeyboardButton("🎮 Добыча",callback_data="farm")],[InlineKeyboardButton("🏠 Главное меню",callback_data="main")]]
        await q.edit_message_text(f"🎉 Вы добыли {amount} {resource}!",reply_markup=InlineKeyboardMarkup(kb))

    # ---------------- EXPEDITION ----------------
    elif data=="expedition":
        multiplier = VIP_BONUS_MULTIPLIER if is_vip(user[7]) else 1
        resource = random.choice(GAME_RESOURCES + RARE_RESOURCES)
        amount = random.randint(1,5) * multiplier
        xp = random.randint(5,15) * multiplier
        rare = resource in RARE_RESOURCES
        await db.update_currency(uid,resource,amount)
        await db.add_xp(uid,xp)
        kb = [[InlineKeyboardButton("🗺 Экспедиция",callback_data="expedition")],[InlineKeyboardButton("🏠 Главное меню",callback_data="main")]]
        await q.edit_message_text(
            f"🗺 Экспедиция завершена!\n🎁 Получено: {amount} {resource}\n⚡ XP: {xp}\n{'💎 Редкий ресурс!' if rare else ''}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # ---------------- STATS ----------------
    elif data=="stats":
        top_gold = await db.get_top("gold")
        text="🏆 Топ по Gold:\n"
        for i,(name,val) in enumerate(top_gold,1):
            text+=f"{i}. {name}: {val}\n"
        kb=[[InlineKeyboardButton("🏠 Главное меню",callback_data="main")]]
        await q.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb))

    # ---------------- ADMIN ----------------
    elif data=="admin" and uid in ADMIN_IDS:
        kb = [
            [InlineKeyboardButton("🎖 Выдать VIP",callback_data="admin_vip")],
            [InlineKeyboardButton("💰 Выдать валюту",callback_data="admin_currency")],
            [InlineKeyboardButton("🚫 Бан",callback_data="admin_ban")],
            [InlineKeyboardButton("✅ Разбан",callback_data="admin_unban")],
            [InlineKeyboardButton("🏠 Главное меню",callback_data="main")]
        ]
        await q.edit_message_text("🛠 Админ-панель",reply_markup=InlineKeyboardMarkup(kb))

    # ---------------- MAIN MENU ----------------
    elif data=="main":
        await start(update,context)

    else:
        kb=[[InlineKeyboardButton("🏠 Главное меню",callback_data="main")]]
        await q.edit_message_text("❌ Неизвестная кнопка. Вернитесь в главное меню.",reply_markup=InlineKeyboardMarkup(kb))

# ---------------- MAIN ----------------
async def main():
    await db.init()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    await app.run_polling()

if __name__=="__main__":
    # --- исправленный запуск для Python 3.13 ---
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        asyncio.create_task(main())
        loop.run_forever()
    else:
        asyncio.run(main())

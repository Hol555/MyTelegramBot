# ==============================
# bot.py — MMO Telegram Bot
# ==============================

import asyncio
import os
import random
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
import aiosqlite

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ==============================
# ENV
# ==============================

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = "game.db"

# ==============================
# USER STATES
# ==============================

user_states: dict[int, dict] = {}

def set_state(user_id: int, mode: str, data: dict | None = None):
    user_states[user_id] = {"mode": mode, "data": data or {}}

def get_state(user_id: int):
    return user_states.get(user_id)

def clear_state(user_id: int):
    if user_id in user_states:
        del user_states[user_id]

# ==============================
# KEYBOARDS
# ==============================

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["Магазин", "Инвентарь", "Профиль"],
        ["Майнинг", "Экспедиции", "Миссии"],
        ["Дуэли", "Боссы", "Кланы"],
        ["Донат"]
    ],
    resize_keyboard=True
)

BACK_MENU = ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)

# ==============================
# DATABASE INIT
# ==============================

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1000,
            donate_balance INTEGER DEFAULT 0,
            exp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            clan_id INTEGER,
            last_mining INTEGER DEFAULT 0,
            last_expedition INTEGER DEFAULT 0,
            last_mission INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            description TEXT,
            power INTEGER,
            price INTEGER,
            donate_price INTEGER
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            amount INTEGER
        );

        CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            owner_id INTEGER,
            treasury INTEGER DEFAULT 0,
            member_limit INTEGER DEFAULT 10
        );

        CREATE TABLE IF NOT EXISTS clan_roles (
            clan_id INTEGER,
            user_id INTEGER,
            can_invite INTEGER,
            can_kick INTEGER,
            can_manage_roles INTEGER,
            can_attack_boss INTEGER,
            can_use_treasury INTEGER
        );

        CREATE TABLE IF NOT EXISTS clan_bosses (
            clan_id INTEGER,
            last_attack INTEGER
        );

        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            reward_min INTEGER,
            reward_max INTEGER
        );
        """)
        await db.commit()

        cur = await db.execute("SELECT COUNT(*) FROM items")
        if (await cur.fetchone())[0] == 0:
            await db.executemany("""
            INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (1,"Меч +50","weapon","+50 к урону в PvP и PvE",50,500,5),
                (2,"Щит +30","armor","+30 защиты",30,400,4),
                (3,"Зелье силы","buff","+20% урона на бой",20,300,3),
                (4,"Камень добычи","buff","+10% к фарму",10,200,2),
                (5,"Эликсир HP","resource","+100 HP в рейдах",100,150,2),
                (6,"Расширение клана","expansion","+5 слотов клана",5,50000,5),
                (7,"Клановый бафф урона","clan_buff","+10% урона клана",10,1000,10),
                (8,"Дебафф босса","clan_debuff","-10% силы босса",10,1000,10)
            ])
            await db.commit()

# ==============================
# USER INIT
# ==============================

async def ensure_user(db, user_id: int, username: str):
    cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not await cur.fetchone():
        await db.execute(
            "INSERT INTO users (user_id, username) VALUES (?,?)",
            (user_id, username)
        )
        await db.commit()

# ==============================
# START / PROFILE
# ==============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        await ensure_user(db, update.effective_user.id, update.effective_user.username or "")
    await update.message.reply_text(
        "⚔️ Добро пожаловать в MMO-мир!\n\n"
        "PvP • Рейды • Кланы • Экономика\n"
        "Развивайся и доминируй.",
        reply_markup=MAIN_MENU
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT balance, donate_balance, level, exp, wins, losses
        FROM users WHERE user_id=?
        """, (uid,))
        b,d,l,e,w,lo = await cur.fetchone()

    await update.message.reply_text(
        f"👤 Профиль\n\n"
        f"💰 Баланс: {b}\n"
        f"💎 Донат: {d}\n"
        f"⭐ Уровень: {l}\n"
        f"📊 Опыт: {e}\n"
        f"⚔ Победы: {w}\n"
        f"💀 Поражения: {lo}",
        reply_markup=MAIN_MENU
    )

# ==============================
# SHOP
# ==============================

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id,name,price,donate_price FROM items")
        items = await cur.fetchall()

    kb = []
    for i in items:
        kb.append([InlineKeyboardButton(
            f"{i[1]} | {i[2]}₽ / {i[3]}💎",
            callback_data=f"shop_{i[0]}"
        )])

    await update.message.reply_text(
        "🏪 Магазин",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def shop_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split("_")[1])

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT name,description,price,donate_price
        FROM items WHERE id=?
        """,(item_id,))
        n,d,p,dp = await cur.fetchone()

    await q.edit_message_text(
        f"📦 {n}\n\n{d}\n\nЦена: {p}₽ / {dp}💎",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Купить за ₽", callback_data=f"buy_money_{item_id}"),
                InlineKeyboardButton("Купить за 💎", callback_data=f"buy_donate_{item_id}")
            ]
        ])
    )

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _,method,item_id = q.data.split("_")
    item_id = int(item_id)
    uid = q.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT price,donate_price FROM items WHERE id=?", (item_id,))
        price, dprice = await cur.fetchone()

        cur = await db.execute("SELECT balance,donate_balance FROM users WHERE user_id=?", (uid,))
        bal,don = await cur.fetchone()

        if method=="money":
            if bal<price:
                await q.edit_message_text("❌ Недостаточно средств")
                return
            await db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price,uid))
        else:
            if don<dprice:
                await q.edit_message_text("❌ Недостаточно доната")
                return
            await db.execute("UPDATE users SET donate_balance=donate_balance-? WHERE user_id=?", (dprice,uid))

        cur = await db.execute("SELECT id FROM inventory WHERE user_id=? AND item_id=?", (uid,item_id))
        row = await cur.fetchone()
        if row:
            await db.execute("UPDATE inventory SET amount=amount+1 WHERE id=?", (row[0],))
        else:
            await db.execute("INSERT INTO inventory (user_id,item_id,amount) VALUES (?,?,1)", (uid,item_id))
        await db.commit()

    await q.edit_message_text("✅ Покупка успешна")

# ==============================
# INVENTORY / MINING / DONATE
# ==============================

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
        SELECT items.name,items.type,inventory.amount
        FROM inventory
        JOIN items ON items.id=inventory.item_id
        WHERE inventory.user_id=?
        """,(uid,))
        rows = await cur.fetchall()

    if not rows:
        text="🎒 Инвентарь пуст"
    else:
        text="🎒 Инвентарь:\n\n"
        for r in rows:
            text+=f"{r[0]} ({r[1]}) x{r[2]}\n"

    await update.message.reply_text(text, reply_markup=MAIN_MENU)

async def mining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    now=int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        cur=await db.execute("SELECT last_mining FROM users WHERE user_id=?", (uid,))
        last=(await cur.fetchone())[0]
        if now-last<300:
            await update.message.reply_text("⛏️ КД 5 минут")
            return
        reward=random.randint(50,150)
        await db.execute("UPDATE users SET balance=balance+?, last_mining=? WHERE user_id=?", (reward,now,uid))
        await db.commit()
    await update.message.reply_text(f"⛏️ Добыто {reward}₽", reply_markup=MAIN_MENU)

async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💎 Донат\n\n"
        "Используется для покупки премиум-контента.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Написать админу", url="https://t.me/soblaznss")]
        ])
    )

# ==============================
# ADMIN
# ==============================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    await update.message.reply_text(
        "/give_balance id amt\n"
        "/give_donate id amt\n"
        "/ban id\n"
        "/unban id"
    )

async def give_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    uid=int(context.args[0])
    amt=int(context.args[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amt,uid))
        await db.commit()
    await update.message.reply_text("OK")

async def give_donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    uid=int(context.args[0])
    amt=int(context.args[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET donate_balance=donate_balance+? WHERE user_id=?", (amt,uid))
        await db.commit()
    await update.message.reply_text("OK")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    uid=int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (uid,))
        await db.commit()
    await update.message.reply_text("BANNED")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id!=ADMIN_ID:
        return
    uid=int(context.args[0])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (uid,))
        await db.commit()
    await update.message.reply_text("UNBANNED")

# ==============================
# MAIN
# ==============================

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("give_balance", give_balance))
    app.add_handler(CommandHandler("give_donate", give_donate))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))

    app.add_handler(MessageHandler(filters.Regex("^Профиль$"), profile))
    app.add_handler(MessageHandler(filters.Regex("^Магазин$"), shop))
    app.add_handler(MessageHandler(filters.Regex("^Инвентарь$"), inventory))
    app.add_handler(MessageHandler(filters.Regex("^Майнинг$"), mining))
    app.add_handler(MessageHandler(filters.Regex("^Донат$"), donate))

    app.add_handler(CallbackQueryHandler(shop_item, pattern="^shop_"))
    app.add_handler(CallbackQueryHandler(buy_item, pattern="^buy_"))

    async def on_start(app):
        await init_db()

    app.post_init=on_start
    app.run_polling()

if __name__=="__main__":
    main()

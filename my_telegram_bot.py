import os
import random
import time
import logging
import aiosqlite
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv

# ================== CONFIG ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
DONATE_ADMIN = "soblaznss"

EVENT_ACTIVE = True
EVENT_MULTIPLIER = 2.0
BOSS_COOLDOWN = 86400

logging.basicConfig(level=logging.INFO)

# ================== STATES ==================
user_states = {}

def set_state(uid, mode, data=None):
    user_states[uid] = {"mode": mode, "data": data or {}}

def get_state(uid):
    return user_states.get(uid, {"mode": "none", "data": {}})

def clear_state(uid):
    user_states.pop(uid, None)

# ================== DB ==================
async def init_db(app):
    async with aiosqlite.connect("bot.db") as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1000,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            vip_until REAL DEFAULT 0,
            sword INTEGER DEFAULT 0,
            shield INTEGER DEFAULT 0,
            crown INTEGER DEFAULT 0,
            clan_id INTEGER DEFAULT NULL,
            last_boss REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            owner_id INTEGER
        );
        """)
        await db.commit()

async def create_user(uid, username):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?,?)",
            (uid, username)
        )
        await db.commit()

async def get_user(uid):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (uid,)) as c:
            row = await c.fetchone()
            if not row:
                return None
            cols = [x[0] for x in c.description]
            user = dict(zip(cols, row))
            user["vip"] = user["vip_until"] > time.time()
            return user

async def get_user_by_username(username):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ) as c:
            row = await c.fetchone()
            if not row:
                return None
            return dict(zip([x[0] for x in c.description], row))

# ================== MENUS ==================
def reply_main_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎁 Сундуки"), KeyboardButton("⚔️ Дуэли")],
        [KeyboardButton("🏪 Магазин"), KeyboardButton("👥 Кланы")],
        [KeyboardButton("👹 Босс"), KeyboardButton("💸 Донат")],
        [KeyboardButton("📊 Профиль")]
    ], resize_keyboard=True)

def inline_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Сундуки", callback_data="chests")],
        [InlineKeyboardButton("⚔️ Дуэли", callback_data="duels")],
        [InlineKeyboardButton("🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton("👥 Кланы", callback_data="clans")],
        [InlineKeyboardButton("👹 Босс", callback_data="boss")],
        [InlineKeyboardButton("💸 Донат", callback_data="donate")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")]
    ])

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await create_user(user.id, user.username or "unknown")
    await update.message.reply_text(
        "🎮 Добро пожаловать!",
        reply_markup=reply_main_menu()
    )

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = await get_user(uid)

    # --- сундуки ---
    if q.data == "chests":
        set_state(uid, "chests")
        await q.edit_message_text(
            "🎁 Выберите сундук:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Обычный (100)", callback_data="chest_common")],
                [InlineKeyboardButton("Редкий (300)", callback_data="chest_rare")],
                [InlineKeyboardButton("Эпический (700)", callback_data="chest_epic")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    elif q.data.startswith("chest_"):
        prices = {"common":100,"rare":300,"epic":700}
        rewards = {"common":(50,150),"rare":(200,400),"epic":(500,1000)}
        t = q.data.split("_")[1]

        if user["balance"] < prices[t]:
            await q.answer("❌ Недостаточно монет", show_alert=True)
            return

        reward = random.randint(*rewards[t])
        if user["vip"]:
            reward = int(reward * 1.5)
        if EVENT_ACTIVE:
            reward = int(reward * EVENT_MULTIPLIER)

        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance = balance - ? + ? WHERE user_id=?",
                (prices[t], reward, uid)
            )
            await db.commit()

        clear_state(uid)
        await q.edit_message_text(
            f"🎉 Вы получили {reward} монет!",
            reply_markup=inline_main_menu()
        )

    # --- дуэли ---
    elif q.data == "duels":
        set_state(uid, "duel_input")
        await q.edit_message_text(
            "⚔️ Введите:\n@username ставка",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    # --- магазин ---
    elif q.data == "shop":
        await q.edit_message_text(
            "🏪 Магазин:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ VIP (500)", callback_data="buy_vip")],
                [InlineKeyboardButton("⚔️ Меч (300)", callback_data="buy_sword")],
                [InlineKeyboardButton("🛡️ Щит (300)", callback_data="buy_shield")],
                [InlineKeyboardButton("👑 Корона (300)", callback_data="buy_crown")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    elif q.data == "buy_vip":
        if user["balance"] < 500:
            await q.answer("❌ Недостаточно монет", show_alert=True)
            return
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance=balance-500, vip_until=? WHERE user_id=?",
                (time.time()+86400*30, uid)
            )
            await db.commit()
        await q.edit_message_text("⭐ VIP активирован на 30 дней!", reply_markup=inline_main_menu())

    # --- кланы ---
    elif q.data == "clans":
        await q.edit_message_text(
            "👥 Кланы",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Создать", callback_data="clan_create")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    elif q.data == "clan_create":
        set_state(uid, "clan_create")
        await q.edit_message_text("Введите название клана:")

    # --- босс ---
    elif q.data == "boss":
        if time.time() - user["last_boss"] < BOSS_COOLDOWN:
            await q.answer("⏳ Босс доступен раз в день", show_alert=True)
            return

        dmg = random.randint(50,150)
        if user["sword"]: dmg += 30
        reward = dmg * 3
        if EVENT_ACTIVE:
            reward *= EVENT_MULTIPLIER

        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance=balance+?, last_boss=? WHERE user_id=?",
                (reward, time.time(), uid)
            )
            await db.commit()

        await q.edit_message_text(
            f"👹 Босс побеждён!\n🔥 Урон: {dmg}\n💰 Награда: {reward}",
            reply_markup=inline_main_menu()
        )

    # --- донат ---
    elif q.data == "donate":
        set_state(uid, "donate")
        await q.edit_message_text(
            "💸 Донат\nНапишите сумму и что хотите купить.\n"
            "Заявка будет отправлена администратору.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    elif q.data == "profile":
        await q.edit_message_text(
            f"📊 Профиль\n💰 {user['balance']}\n"
            f"🏆 {user['wins']} / {user['losses']}\n"
            f"⭐ VIP: {'Да' if user['vip'] else 'Нет'}",
            reply_markup=inline_main_menu()
        )

    elif q.data == "main":
        clear_state(uid)
        await q.edit_message_text("🏠 Главное меню", reply_markup=inline_main_menu())

# ================== TEXT ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = get_state(uid)

    if state["mode"] == "donate":
        await context.bot.send_message(
            chat_id=f"@{DONATE_ADMIN}",
            text=(
                "💸 ЗАЯВКА НА ДОНАТ\n"
                f"👤 @{update.effective_user.username}\n"
                f"🆔 {uid}\n"
                f"📩 {text}"
            )
        )
        clear_state(uid)
        await update.message.reply_text(
            "✅ Заявка отправлена!",
            reply_markup=reply_main_menu()
        )
        return

    if state["mode"] == "clan_create":
        async with aiosqlite.connect("bot.db") as db:
            try:
                await db.execute(
                    "INSERT INTO clans (name, owner_id) VALUES (?,?)",
                    (text, uid)
                )
                await db.execute(
                    "UPDATE users SET clan_id=(SELECT id FROM clans WHERE owner_id=?) WHERE user_id=?",
                    (uid, uid)
                )
                await db.commit()
                await update.message.reply_text("✅ Клан создан!", reply_markup=reply_main_menu())
            except:
                await update.message.reply_text("❌ Название занято")
        clear_state(uid)

    if state["mode"] == "duel_input":
        parts = text.split()
        if len(parts)!=2 or not parts[0].startswith("@") or not parts[1].isdigit():
            await update.message.reply_text("❌ Формат: @username ставка")
            return

        opponent = await get_user_by_username(parts[0][1:])
        if not opponent:
            await update.message.reply_text("❌ Игрок не найден")
            return

        bet = int(parts[1])
        user = await get_user(uid)
        if user["balance"] < bet or opponent["balance"] < bet:
            await update.message.reply_text("❌ Недостаточно монет")
            return

        win = random.random() > 0.5
        async with aiosqlite.connect("bot.db") as db:
            if win:
                await db.execute("UPDATE users SET balance=balance+?, wins=wins+1 WHERE user_id=?", (bet, uid))
                await db.execute("UPDATE users SET balance=balance-?, losses=losses+1 WHERE user_id=?", (bet, opponent["user_id"]))
                msg = "🏆 ПОБЕДА!"
            else:
                await db.execute("UPDATE users SET balance=balance-bet, losses=losses+1 WHERE user_id=?", (uid,))
                await db.execute("UPDATE users SET balance=balance+?, wins=wins+1 WHERE user_id=?", (bet, opponent["user_id"]))
                msg = "❌ ПОРАЖЕНИЕ"
            await db.commit()

        clear_state(uid)
        await update.message.reply_text(msg, reply_markup=reply_main_menu())

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()

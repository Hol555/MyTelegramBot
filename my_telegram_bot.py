import os
import random
import time
import logging
import aiosqlite
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

logging.basicConfig(level=logging.INFO)

# ================== STATES ==================
user_states = {}

def set_state(uid, mode, data=None):
    user_states[uid] = {"mode": mode, "data": data or {}}

def get_state(uid):
    return user_states.get(uid)

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
            last_boss REAL DEFAULT 0
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
            user = dict(zip([x[0] for x in c.description], row))
            user["vip"] = user["vip_until"] > time.time()
            return user

async def get_user_by_username(username):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE username=?", (username,)) as c:
            row = await c.fetchone()
            return dict(zip([x[0] for x in c.description], row)) if row else None

# ================== MENUS ==================
def reply_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎁 Сундуки"), KeyboardButton("⚔️ Дуэли")],
        [KeyboardButton("🏪 Магазин"), KeyboardButton("👹 Босс")],
        [KeyboardButton("💸 Донат"), KeyboardButton("📊 Профиль")]
    ], resize_keyboard=True)

def inline_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Сундуки", callback_data="chests")],
        [InlineKeyboardButton("⚔️ Дуэли", callback_data="duels")],
        [InlineKeyboardButton("🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton("👹 Босс", callback_data="boss")],
        [InlineKeyboardButton("💸 Донат", callback_data="donate")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Выдать деньги", callback_data="admin_money")],
        [InlineKeyboardButton("⭐ Выдать VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("📦 Выдать предмет", callback_data="admin_item")],
        [InlineKeyboardButton("🔙 В меню", callback_data="main")]
    ])

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await create_user(u.id, u.username or "unknown")
    await update.message.reply_text(
        "🎮 Игра запущена!",
        reply_markup=reply_menu()
    )

# ================== ADMIN ==================
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Нет доступа")
        return
    await update.message.reply_text("🔧 Админ-панель", reply_markup=admin_menu())

# ================== CALLBACK ==================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    user = await get_user(uid)

    # ---------- MAIN ----------
    if q.data == "main":
        clear_state(uid)
        await q.edit_message_text("🏠 Главное меню", reply_markup=inline_menu())

    # ---------- CHESTS ----------
    elif q.data == "chests":
        await q.edit_message_text(
            "🎁 Сундуки",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Обычный (100)", callback_data="chest_100")],
                [InlineKeyboardButton("Редкий (300)", callback_data="chest_300")],
                [InlineKeyboardButton("🔙 Назад", callback_data="main")]
            ])
        )

    elif q.data.startswith("chest_"):
        price = int(q.data.split("_")[1])
        if user["balance"] < price:
            await q.answer("❌ Недостаточно монет", show_alert=True)
            return
        reward = random.randint(price//2, price*2)
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance=balance-?+? WHERE user_id=?",
                (price, reward, uid)
            )
            await db.commit()
        await q.edit_message_text(
            f"🎉 Награда: {reward}",
            reply_markup=inline_menu()
        )

    # ---------- DUELS ----------
    elif q.data == "duels":
        set_state(uid, "duel")
        await q.edit_message_text("⚔️ Введите: @user ставка")

    # ---------- SHOP ----------
    elif q.data == "shop":
        await q.edit_message_text(
            "🏪 Магазин",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ VIP (500)", callback_data="buy_vip")],
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
        await q.edit_message_text("⭐ VIP активирован", reply_markup=inline_menu())

    # ---------- BOSS ----------
    elif q.data == "boss":
        dmg = random.randint(50,150)
        reward = dmg * 3
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance=balance+?, last_boss=? WHERE user_id=?",
                (reward, time.time(), uid)
            )
            await db.commit()
        await q.edit_message_text(
            f"👹 Босс побеждён\n💥 {dmg}\n💰 {reward}",
            reply_markup=inline_menu()
        )

    # ---------- DONATE ----------
    elif q.data == "donate":
        set_state(uid, "donate")
        await q.edit_message_text("💸 Напишите заявку текстом")

    # ---------- PROFILE ----------
    elif q.data == "profile":
        await q.edit_message_text(
            f"📊 Профиль\n💰 {user['balance']}\n⭐ VIP: {'Да' if user['vip'] else 'Нет'}",
            reply_markup=inline_menu()
        )

    # ---------- ADMIN ----------
    elif uid == ADMIN_ID:
        if q.data == "admin_money":
            set_state(uid, "admin_money")
            await q.edit_message_text("Введите: @user сумма")

        elif q.data == "admin_vip":
            set_state(uid, "admin_vip")
            await q.edit_message_text("Введите: @user")

# ================== TEXT ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    state = get_state(uid)

    # reply → inline
    if text in ["🎁 Сундуки","⚔️ Дуэли","🏪 Магазин","👹 Босс","💸 Донат","📊 Профиль"]:
        await update.message.reply_text("⬇️", reply_markup=inline_menu())
        return

    if not state:
        return

    # donate
    if state["mode"] == "donate":
        await context.bot.send_message(
            chat_id=f"@{DONATE_ADMIN}",
            text=f"💸 Донат от @{update.effective_user.username}\n{text}"
        )
        clear_state(uid)
        await update.message.reply_text("✅ Заявка отправлена", reply_markup=reply_menu())

    # duel
    elif state["mode"] == "duel":
        parts = text.split()
        if len(parts)!=2 or not parts[0].startswith("@"):
            await update.message.reply_text("❌ Формат неверный")
            return
        opponent = await get_user_by_username(parts[0][1:])
        if not opponent:
            await update.message.reply_text("❌ Игрок не найден")
            return
        win = random.random() > 0.5
        msg = "🏆 Победа!" if win else "❌ Поражение"
        clear_state(uid)
        await update.message.reply_text(msg, reply_markup=reply_menu())

    # admin money
    elif state["mode"] == "admin_money":
        u, amt = text.split()
        target = await get_user_by_username(u[1:])
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=?",
                (int(amt), target["user_id"])
            )
            await db.commit()
        clear_state(uid)
        await update.message.reply_text("✅ Выдано", reply_markup=reply_menu())

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

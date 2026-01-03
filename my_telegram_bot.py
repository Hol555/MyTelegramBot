import asyncio
import aiosqlite
import nest_asyncio
import random
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import os
from dotenv import load_dotenv

# =========================
# Загружаем .env
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_ENV = os.getenv("ADMIN_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

if not BOT_TOKEN or not ADMIN_ID_ENV or not ADMIN_USERNAME:
    raise ValueError("Ошибка: проверьте .env, должны быть BOT_TOKEN, ADMIN_ID, ADMIN_USERNAME")

ADMIN_IDS = [int(ADMIN_ID_ENV)]

# =========================
# Исправляем event loop для asyncio
# =========================
nest_asyncio.apply()

# =========================
# Настройки базы данных
# =========================
DB_FILE = "game_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users(
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            balance INTEGER DEFAULT 0,
                            vip_until TEXT DEFAULT '',
                            inventory TEXT DEFAULT '',
                            duels_won INTEGER DEFAULT 0,
                            duels_lost INTEGER DEFAULT 0
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promo_codes(
                            code TEXT PRIMARY KEY,
                            currency INTEGER,
                            uses_left INTEGER,
                            expires_at TEXT
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS duels(
                            challenger_id INTEGER,
                            opponent_id INTEGER,
                            bet INTEGER,
                            status TEXT DEFAULT 'pending'
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS banned_users(
                            user_id INTEGER PRIMARY KEY
                            )""")
        await db.commit()
    print("✅ Database initialized")

# =========================
# Вспомогательные функции
# =========================
async def get_user(user_id, username=None):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.execute("INSERT INTO users(user_id, username) VALUES(?,?)", (user_id, username))
            await db.commit()
            async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
                user = await cursor.fetchone()
        return user

async def update_balance(user_id, amount):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

async def add_item(user_id, item):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT inventory FROM users WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
        inv_list = inv[0].split(",") if inv[0] else []
        inv_list.append(item)
        await db.execute("UPDATE users SET inventory=? WHERE user_id=?", (",".join(inv_list), user_id))
        await db.commit()

async def get_inventory(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT inventory FROM users WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
    return inv[0].split(",") if inv[0] else []

# =========================
# Промокоды
# =========================
async def use_promocode(user_id, code):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT currency, uses_left, expires_at FROM promo_codes WHERE code=?", (code,)) as cursor:
            promo = await cursor.fetchone()
        if not promo:
            return "❌ Промокод не найден."
        currency, uses_left, expires_at = promo
        if uses_left <= 0:
            return "❌ Промокод исчерпан."
        if expires_at and datetime.utcnow() > datetime.fromisoformat(expires_at):
            return "❌ Промокод истёк."
        await update_balance(user_id, currency)
        await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code=?", (code,))
        await db.commit()
        return f"✅ Вы получили {currency} валюты!"

# =========================
# Магазин
# =========================
SHOP_ITEMS = {
    "Меч": {"price": 100, "description": "Увеличивает силу в дуэлях"},
    "Щит": {"price": 80, "description": "Снижает урон от дуэлей"},
    "Зелье": {"price": 50, "description": "Восстанавливает 50 валюты"},
    "Редкий сундук": {"price": 300, "description": "Содержит случайную награду"}
}

# Ограничение добычи валюты
LAST_MINE = {}
MINE_COOLDOWN = 60  # секунд

# =========================
# Главное меню
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id, update.effective_user.username)
    kb = [
        [InlineKeyboardButton("Добыча", callback_data="mine")],
        [InlineKeyboardButton("Профиль", callback_data="profile"),
         InlineKeyboardButton("Топ 10", callback_data="top")],
        [InlineKeyboardButton("Магазин", callback_data="shop")],
        [InlineKeyboardButton("Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("Экспедиции", callback_data="expedition"),
         InlineKeyboardButton("Миссии", callback_data="mission")],
        [InlineKeyboardButton("Дуэли", callback_data="duel")],
        [InlineKeyboardButton("Админ-панель", callback_data="admin")],
        [InlineKeyboardButton("Активировать промокод", callback_data="promo")]
    ]
    await update.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(kb))

# =========================
# Кнопки
# =========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # ---------- ДОБЫЧА ----------
    if data == "mine":
        now = datetime.utcnow()
        last_time = LAST_MINE.get(user_id)
        if last_time and (now - last_time).total_seconds() < MINE_COOLDOWN:
            await query.edit_message_text(f"⏳ Добыча доступна через {int(MINE_COOLDOWN - (now - last_time).total_seconds())} секунд")
            return
        LAST_MINE[user_id] = now
        gain = random.randint(10, 50)
        await update_balance(user_id, gain)
        msg = f"Вы добыли {gain} валюты!"
        if random.random() < 0.1:
            item = "Редкий сундук"
            await add_item(user_id, item)
            msg += f" Вы нашли {item}!"
        await query.edit_message_text(msg)

    # ---------- ПРОФИЛЬ ----------
    elif data == "profile":
        user = await get_user(user_id)
        inv = await get_inventory(user_id)
        vip_status = f"VIP до {user[3]}" if user[3] else "Нет VIP"
        text = f"Профиль @{user[1]}:\nБаланс: {user[2]}\nVIP: {vip_status}\nИнвентарь: {', '.join(inv) if inv else 'Пусто'}"
        await query.edit_message_text(text)

    # ---------- ТОП 10 ----------
    elif data == "top":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        text = "🏆 Топ 10 по валюте:\n" + "\n".join([f"{i+1}. @{r[0]} — {r[1]}" for i,r in enumerate(rows)])
        await query.edit_message_text(text)

    # ---------- МАГАЗИН ----------
    elif data == "shop":
        kb = [[InlineKeyboardButton(f"{item} ({info['price']})", callback_data=f"shop_{item}")] for item, info in SHOP_ITEMS.items()]
        kb.append([InlineKeyboardButton("Вернуться в меню", callback_data="start")])
        await query.edit_message_text("Магазин:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("shop_"):
        item_name = data[5:]
        info = SHOP_ITEMS[item_name]
        kb = [
            [InlineKeyboardButton("Купить", callback_data=f"buy_{item_name}")],
            [InlineKeyboardButton("Вернуться в магазин", callback_data="shop")]
        ]
        await query.edit_message_text(f"{item_name}\nЦена: {info['price']}\nОписание: {info['description']}", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("buy_"):
        item_name = data[4:]
        user = await get_user(user_id)
        if user[2] >= SHOP_ITEMS[item_name]["price"]:
            await update_balance(user_id, -SHOP_ITEMS[item_name]["price"])
            await add_item(user_id, item_name)
            await query.edit_message_text(f"Вы купили {item_name}!")
        else:
            await query.edit_message_text("Недостаточно валюты!")

    # ---------- ИНВЕНТАРЬ ----------
    elif data == "inventory":
        inv = await get_inventory(user_id)
        if not inv:
            await query.edit_message_text("Инвентарь пуст.")
            return
        kb = [[InlineKeyboardButton(item, callback_data=f"use_{item}")] for item in inv]
        kb.append([InlineKeyboardButton("Вернуться в меню", callback_data="start")])
        await query.edit_message_text("Инвентарь:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("use_"):
        item_name = data[4:]
        await query.edit_message_text(f"Вы использовали {item_name}!")

    # ---------- ЭКСПЕДИЦИИ ----------
    elif data == "expedition":
        reward = random.randint(20, 100)
        await update_balance(user_id, reward)
        await query.edit_message_text(f"Вы отправились в экспедицию и получили {reward} валюты!")

    # ---------- МИССИИ ----------
    elif data == "mission":
        reward = random.randint(30, 120)
        await update_balance(user_id, reward)
        await query.edit_message_text(f"Вы выполнили миссию и получили {reward} валюты!")

    # ---------- ПРОМОКОД ----------
    elif data == "promo":
        await query.edit_message_text("Введите промокод:")

    # ---------- АДМИН-ПАНЕЛЬ ----------
    elif data == "admin" and user_id in ADMIN_IDS:
        kb = [
            [InlineKeyboardButton("Выдать валюту", callback_data="admin_currency")],
            [InlineKeyboardButton("Выдать VIP", callback_data="admin_vip")],
            [InlineKeyboardButton("Бан", callback_data="admin_ban")],
            [InlineKeyboardButton("Разбан", callback_data="admin_unban")],
            [InlineKeyboardButton("Создать промокод", callback_data="admin_promo_create")],
            [InlineKeyboardButton("Удалить промокод", callback_data="admin_promo_delete")],
            [InlineKeyboardButton("Купить VIP", url=f"https://t.me/{ADMIN_USERNAME}")]
        ]
        await query.edit_message_text("Админ-панель:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("admin_") and user_id in ADMIN_IDS:
        context.user_data['admin_action'] = data

    # ---------- ВОЗВРАТ В МЕНЮ ----------
    elif data == "start":
        await start(update, context)

# =========================
# Обработка ввода промокода и админских команд (НОВАЯ ЛОГИКА)
# =========================
async def message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id in ADMIN_IDS:
        action = context.user_data.get('admin_action')
        if action:
            try:
                if action == "admin_currency":
                    username, amount = text.split()
                    amount = int(amount)
                    async with aiosqlite.connect(DB_FILE) as db:
                        async with db.execute("SELECT user_id FROM users WHERE username=?", (username.lstrip("@"),)) as cursor:
                            target = await cursor.fetchone()
                        if not target:
                            await update.message.reply_text(f"❌ Пользователь {username} не найден")
                            return
                        target_id = target[0]
                        await update_balance(target_id, amount)
                        await update.message.reply_text(f"✅ Выдали {amount} валюты пользователю {username}")

                elif action == "admin_vip":
                    username, days = text.split()
                    days = int(days)
                    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("UPDATE users SET vip_until=? WHERE username=?", (expires, username.lstrip("@")))
                        await db.commit()
                    await update.message.reply_text(f"✅ Выдали VIP на {days} дней пользователю {username}")

                elif action == "admin_ban":
                    username = text
                    async with aiosqlite.connect(DB_FILE) as db:
                        async with db.execute("SELECT user_id FROM users WHERE username=?", (username.lstrip("@"),)) as cursor:
                            target = await cursor.fetchone()
                        if not target:
                            await update.message.reply_text(f"❌ Пользователь {username} не найден")
                            return
                        await db.execute("INSERT OR IGNORE INTO banned_users(user_id) VALUES(?)", (target[0],))
                        await db.commit()
                    await update.message.reply_text(f"✅ Пользователь {username} забанен")

                elif action == "admin_unban":
                    username = text
                    async with aiosqlite.connect(DB_FILE) as db:
                        async with db.execute("SELECT user_id FROM users WHERE username=?", (username.lstrip("@"),)) as cursor:
                            target = await cursor.fetchone()
                        if not target:
                            await update.message.reply_text(f"❌ Пользователь {username} не найден")
                            return
                        await db.execute("DELETE FROM banned_users WHERE user_id=?", (target[0],))
                        await db.commit()
                    await update.message.reply_text(f"✅ Пользователь {username} разбанен")

                elif action == "admin_promo_create":
                    parts = text.split()
                    code = parts[0]
                    if parts[1].lower() == "баланс":
                        currency = int(parts[2])
                    elif parts[1].lower() == "vip":
                        currency = int(parts[2])
                    else:
                        await update.message.reply_text("❌ Ошибка формата. Используйте: CODE баланс 100 или CODE vip 7")
                        return
                    uses = 1
                    expires = (datetime.utcnow() + timedelta(days=30)).isoformat()
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("INSERT INTO promo_codes(code, currency, uses_left, expires_at) VALUES(?,?,?,?)",
                                         (code, currency, uses, expires))
                        await db.commit()
                    await update.message.reply_text(f"✅ Промокод {code} создан")

                elif action == "admin_promo_delete":
                    code = text
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("DELETE FROM promo_codes WHERE code=?", (code,))
                        await db.commit()
                    await update.message.reply_text(f"✅ Промокод {code} удалён")

            except Exception as e:
                await update.message.reply_text(f"❌ Ошибка: {e}")

            context.user_data['admin_action'] = None
            return

    # Обычные пользователи — вводят промокод
    result = await use_promocode(user_id, text)
    await update.message.reply_text(result)

# =========================
# Основной запуск
# =========================
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_input))
    print("✅ Bot is running")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

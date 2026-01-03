# === ВЕРХНИЙ КОД ТВОЕГО БОТА ===
import asyncio
import aiosqlite
import nest_asyncio  # исправляет "event loop already running"
import random
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# =========================
# Настройки
# =========================
BOT_TOKEN = "7766252776:AAF-Eif3iud_CiBPr5RA28auoTTu79dzxFw"
ADMIN_IDS = [7591100907]  # твой ID
ADMIN_USERNAME = "soblaznss"

# =========================
# Включаем nest_asyncio
# =========================
nest_asyncio.apply()

# =========================
# База данных
# =========================
DB_FILE = "game_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        # Пользователи
        await db.execute("""CREATE TABLE IF NOT EXISTS users(
                            user_id INTEGER PRIMARY KEY,
                            username TEXT,
                            balance INTEGER DEFAULT 0,
                            vip_until TEXT DEFAULT '',
                            inventory TEXT DEFAULT '',
                            duels_won INTEGER DEFAULT 0,
                            duels_lost INTEGER DEFAULT 0
                            )""")
        # Промокоды
        await db.execute("""CREATE TABLE IF NOT EXISTS promo_codes(
                            code TEXT PRIMARY KEY,
                            currency INTEGER,
                            uses_left INTEGER,
                            expires_at TEXT
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
# Магазин
# =========================
SHOP_ITEMS = {
    "Меч": {"price": 100, "description": "Увеличивает силу в дуэлях"},
    "Щит": {"price": 80, "description": "Снижает урон от дуэлей"},
    "Зелье": {"price": 50, "description": "Восстанавливает 50 валюты"},
    "Редкий сундук": {"price": 300, "description": "Содержит случайную награду"},
}

# =========================
# Промокоды
# =========================
async def use_promocode(user_id, code):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT currency, uses_left, expires_at FROM promo_codes WHERE code=?", (code,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return "Промокод не найден!"
        currency, uses_left, expires_at = row
        if uses_left <= 0:
            return "Этот промокод больше не действует!"
        if datetime.utcnow() > datetime.fromisoformat(expires_at):
            return "Промокод истёк!"
        await update_balance(user_id, currency)
        await db.execute("UPDATE promo_codes SET uses_left=uses_left-1 WHERE code=?", (code,))
        await db.commit()
        return f"Вы активировали промокод {code}! Получено {currency}💰."

# =========================
# Команды
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("Добыча", callback_data="mine")],
        [InlineKeyboardButton("Профиль", callback_data="profile"),
         InlineKeyboardButton("Топ 10", callback_data="top")],
        [InlineKeyboardButton("Магазин", callback_data="shop"),
         InlineKeyboardButton("Инвентарь", callback_data="inventory")],
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

    # --- Добыча ---
    if data == "mine":
        gain = random.randint(10, 50)
        await update_balance(user_id, gain)
        msg = f"Вы добыли {gain}💰!"
        if random.random() < 0.1:
            item = "Редкий сундук"
            await add_item(user_id, item)
            msg += f" Найден {item}!"
        await query.edit_message_text(msg)

    # --- Профиль ---
    elif data == "profile":
        user = await get_user(user_id)
        inv = await get_inventory(user_id)
        vip_status = f"VIP до {user[3]}" if user[3] else "Нет VIP"
        text = f"Профиль @{user[1]}:\nБаланс: {user[2]}💰\nVIP: {vip_status}\nИнвентарь: {', '.join(inv) if inv else 'Пусто'}"
        await query.edit_message_text(text)

    # --- Топ 10 ---
    elif data == "top":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        text = "🏆 Топ 10:\n" + "\n".join([f"{i+1}. @{r[0]} — {r[1]}💰" for i,r in enumerate(rows)])
        await query.edit_message_text(text)

    # --- Магазин ---
    elif data == "shop":
        kb = [[InlineKeyboardButton(f"{item} ({info['price']}💰)", callback_data=f"shop_{item}")] for item, info in SHOP_ITEMS.items()]
        kb.append([InlineKeyboardButton("Вернуться в меню", callback_data="start")])
        await query.edit_message_text("Магазин:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("shop_"):
        item_name = data[5:]
        info = SHOP_ITEMS[item_name]
        kb = [
            [InlineKeyboardButton("Купить", callback_data=f"buy_{item_name}")],
            [InlineKeyboardButton("Вернуться в магазин", callback_data="shop")]
        ]
        await query.edit_message_text(f"{item_name}\nЦена: {info['price']}💰\nОписание: {info['description']}", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("buy_"):
        item_name = data[4:]
        user = await get_user(user_id)
        price = SHOP_ITEMS[item_name]["price"]
        if user[2] >= price:
            await update_balance(user_id, -price)
            await add_item(user_id, item_name)
            await query.edit_message_text(f"Вы купили {item_name}!")
        else:
            await query.edit_message_text("Недостаточно валюты!")

    # --- Инвентарь ---
    elif data == "inventory":
        inv = await get_inventory(user_id)
        if not inv:
            await query.edit_message_text("Ваш инвентарь пуст.")
            return
        kb = [[InlineKeyboardButton(f"Использовать {item}", callback_data=f"use_{item}")] for item in inv]
        kb.append([InlineKeyboardButton("Вернуться в меню", callback_data="start")])
        await query.edit_message_text("Инвентарь:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("use_"):
        item_name = data[4:]
        await query.edit_message_text(f"Вы использовали {item_name}! (Эффект пока демонстрационный)")

    # --- Админ-панель ---
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

    # --- Промокоды ---
    elif data == "promo":
        await query.edit_message_text("Введите промокод с помощью команды /usepromo <код>")

# =========================
# Промокод команда
# =========================
async def usepromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Использование: /usepromo <код>")
        return
    code = context.args[0]
    res = await use_promocode(update.effective_user.id, code)
    await update.message.reply_text(res)

# =========================
# Основной запуск
# =========================
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usepromo", usepromo))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("✅ Bot is running")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

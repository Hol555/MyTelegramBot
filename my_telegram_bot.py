import asyncio
import aiosqlite
import nest_asyncio  # исправляет "event loop already running"
import random
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler

# =========================
# Настройки
# =========================
BOT_TOKEN = "ВАШ_BOT_TOKEN"
ADMIN_IDS = [7591100907]  # твой ID
ADMIN_USERNAME = "soblaznss"

# =========================
# Включаем nest_asyncio
# =========================
nest_asyncio.apply()

# =========================
# Инициализация базы данных
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
    "Редкий сундук": {"price": 300, "description": "Содержит случайную награду"}
}

# =========================
# Команды
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id, update.effective_user.username)
    kb = [
        [InlineKeyboardButton("Добыча", callback_data="mine")],
        [InlineKeyboardButton("Профиль", callback_data="profile"),
         InlineKeyboardButton("Топ 10", callback_data="top")],
        [InlineKeyboardButton("Магазин", callback_data="shop")],
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

    if data == "mine":
        # Добыча с рандомом
        gain = random.randint(10, 50)
        await update_balance(user_id, gain)
        msg = f"Вы добыли {gain} валюты!"
        # Случайные сундуки
        if random.random() < 0.1:
            item = "Редкий сундук"
            await add_item(user_id, item)
            msg += f" Вы нашли {item}!"
        await query.edit_message_text(msg)
    
    elif data == "profile":
        user = await get_user(user_id)
        inv = await get_inventory(user_id)
        vip_status = f"VIP до {user[3]}" if user[3] else "Нет VIP"
        text = f"Профиль @{user[1]}:\nБаланс: {user[2]}\nVIP: {vip_status}\nИнвентарь: {', '.join(inv) if inv else 'Пусто'}"
        await query.edit_message_text(text)

    elif data == "top":
        # Топ 10 по балансу
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        text = "🏆 Топ 10 по валюте:\n"
        text += "\n".join([f"{i+1}. @{r[0]} — {r[1]}" for i,r in enumerate(rows)])
        await query.edit_message_text(text)

    elif data == "shop":
        # Показываем магазин
        kb = []
        for item, info in SHOP_ITEMS.items():
            kb.append([InlineKeyboardButton(f"{item} ({info['price']})", callback_data=f"shop_{item}")])
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

    elif data == "start":
        await start(update, context)

# =========================
# Основной запуск
# =========================
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("✅ Bot is running")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

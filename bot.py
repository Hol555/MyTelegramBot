import os
import random
import asyncio
import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()  # Исправляет "event loop already running"

# ---------------------- Настройки ----------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7591100907"))  # soblaznss
DB_PATH = "game_bot.db"

# ---------------------- Инициализация БД ----------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 0,
            vip INTEGER DEFAULT 0,
            items TEXT DEFAULT "",
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS duels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1 INTEGER,
            player2 INTEGER,
            stake INTEGER,
            winner INTEGER,
            status TEXT DEFAULT "waiting"
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS expeditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            reward_coins INTEGER,
            reward_items TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mission TEXT,
            reward_coins INTEGER,
            reward_items TEXT,
            completed INTEGER DEFAULT 0
        )''')
        await db.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            coins INTEGER,
            vip INTEGER,
            items TEXT
        )''')
        await db.commit()

# ---------------------- Пользователь ----------------------
async def add_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.commit()

# ---------------------- Главные кнопки ----------------------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("🗺️ Экспедиция", callback_data="expedition")],
        [InlineKeyboardButton("⚔ Дуэль", callback_data="duel")],
        [InlineKeyboardButton("🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🗡️ Миссии", callback_data="missions")],
        [InlineKeyboardButton("🎖️ Профиль", callback_data="profile")],
        [InlineKeyboardButton("🏆 Топ-10", callback_data="leaderboard")],
        [InlineKeyboardButton("🎁 Промокод", callback_data="promocode")],
        [InlineKeyboardButton("🛠️ Админ-панель", callback_data="admin")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------------- Старт ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await add_user(user.id, user.username)
    await update.message.reply_text(
        f"Привет, {user.first_name}! Добро пожаловать в игровой бот.",
        reply_markup=main_menu()
    )

# ---------------------- Экспедиция ----------------------
async def start_expedition(query):
    user_id = query.from_user.id
    expedition_types = {"Лёгкая": (5, 15), "Средняя": (10, 30), "Сложная": (20, 50)}
    choice = random.choice(list(expedition_types.keys()))
    min_r, max_r = expedition_types[choice]

    await query.edit_message_text(f"🗺️ Экспедиция {choice} началась! ⏳ В пути...")
    await asyncio.sleep(3)

    reward_coins = random.randint(min_r, max_r)
    items_list = ["Зелье здоровья", "Редкий камень", "Свиток опыта", "Древний артефакт"]
    reward_items = random.choices(items_list, k=random.randint(0,2))
    reward_items_str = ", ".join(reward_items) if reward_items else "Нет предметов"

    # Случайное событие
    event_chance = random.randint(1,100)
    event_text = ""
    if event_chance <= 20:  # 20% шанс
        bonus = random.randint(5, 20)
        reward_coins += bonus
        event_text = f"\n✨ Случайное событие! Вы нашли бонус {bonus} монет!"

    # Редкий сундук
    chest_chance = random.randint(1,100)
    chest_text = ""
    if chest_chance <= 10:  # 10% шанс
        chest_item = random.choice(items_list)
        reward_items.append(chest_item)
        reward_items_str = ", ".join(reward_items)
        chest_text = f"\n🎁 Редкий сундук! Вы получили {chest_item}!"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO expeditions (user_id, type, reward_coins, reward_items)
            VALUES (?, ?, ?, ?)
        ''', (user_id, choice, reward_coins, reward_items_str))
        await db.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (reward_coins, user_id))
        current_items = await db.execute("SELECT items FROM users WHERE user_id=?", (user_id,))
        row = await current_items.fetchone()
        new_items = (row[0] + "," + reward_items_str) if row and row[0] else reward_items_str
        await db.execute("UPDATE users SET items=? WHERE user_id=?", (new_items, user_id))
        await db.commit()

    await query.edit_message_text(
        f"🗺️ Экспедиция завершена!\nТип: {choice}\n💰 Монеты: {reward_coins}\n🎁 Предметы: {reward_items_str}"
        f"{event_text}{chest_text}"
    )

# ---------------------- Миссии ----------------------
MISSIONS_LIST = {
    "Собрать ресурсы": (10, ["Зелье здоровья"]),
    "Победить монстров": (20, ["Свиток опыта"]),
    "Исследовать пещеру": (30, ["Древний артефакт"])
}

async def missions(query):
    user_id = query.from_user.id
    mission_name = random.choice(list(MISSIONS_LIST.keys()))
    reward_coins, reward_items_list = MISSIONS_LIST[mission_name]
    reward_items_str = ", ".join(reward_items_list)

    # Случайное событие
    event_chance = random.randint(1,100)
    event_text = ""
    if event_chance <= 15:
        bonus = random.randint(5, 15)
        reward_coins += bonus
        event_text = f"\n✨ Случайное событие! Доп. монеты: {bonus}"

    await query.edit_message_text(f"🗡️ Миссия '{mission_name}' выполнена!\n💰 Монеты: {reward_coins}\n🎁 Предметы: {reward_items_str}{event_text}")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO missions (user_id, mission, reward_coins, reward_items, completed) VALUES (?, ?, ?, ?, 1)',
                         (user_id, mission_name, reward_coins, reward_items_str))
        await db.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (reward_coins, user_id))
        current_items = await db.execute("SELECT items FROM users WHERE user_id=?", (user_id,))
        row = await current_items.fetchone()
        new_items = (row[0] + "," + reward_items_str) if row and row[0] else reward_items_str
        await db.execute("UPDATE users SET items=? WHERE user_id=?", (new_items, user_id))
        await db.commit()

# ---------------------- Магазин ----------------------
SHOP_ITEMS = {
    "Зелье здоровья": "Восстанавливает здоровье",
    "Редкий камень": "Используется для улучшений",
    "Свиток опыта": "Даёт опыт для прокачки",
    "Доспехи": "Увеличивает выносливость",
    "Меч": "Увеличивает силу в дуэлях"
}

async def shop(query):
    text = "🏪 Магазин:\n\n"
    for name, desc in SHOP_ITEMS.items():
        text += f"• {name} — {desc}\n"
    await query.edit_message_text(text)

# ---------------------- Профиль ----------------------
async def profile(query):
    user_id = query.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT coins, vip, items, level, exp FROM users WHERE user_id=?", (user_id,))
        row = await cursor.fetchone()
    coins = row[0] if row else 0
    vip = "Да" if row[1] else "Нет"
    items = row[2] if row[2] else "Нет предметов"
    level = row[3] if row else 1
    exp = row[4] if row else 0
    await query.edit_message_text(
        f"🎖️ Профиль:\n💰 Монеты: {coins}\n👑 VIP: {vip}\n🎁 Предметы: {items}\n"
        f"🏅 Уровень: {level}\n✨ Опыт: {exp}"
    )

# ---------------------- Топ-10 ----------------------
async def leaderboard(query):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT username, coins FROM users ORDER BY coins DESC LIMIT 10")
        rows = await cursor.fetchall()
    text = "🏆 Топ-10 игроков:\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {row[1]} монет\n"
    await query.edit_message_text(text)

# ---------------------- Промокоды ----------------------
PROMO_LIST = {
    "WELCOME100": (100, 0, ""),
    "VIPNOW": (0, 1, ""),
    "TREASURE50": (50, 0, "Редкий камень")
}

async def promocode(query):
    await query.edit_message_text("Введите промокод (например, WELCOME100):")
    context = query._bot  # Получаем объект бота

    async def get_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        code = update.message.text.upper()
        if code in PROMO_LIST:
            coins, vip, items = PROMO_LIST[code]
            user_id = update.effective_user.id
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE users SET coins = coins + ?, vip = vip + ? WHERE user_id=?", (coins, vip, user_id))
                if items:
                    cursor = await db.execute("SELECT items FROM users WHERE user_id=?", (user_id,))
                    row = await cursor.fetchone()
                    new_items = (row[0] + "," + items) if row and row[0] else items
                    await db.execute("UPDATE users SET items=? WHERE user_id=?", (new_items, user_id))
                await db.commit()
            await update.message.reply_text(f"🎉 Промокод активирован! Вы получили: {coins} монет, VIP: {vip}, предметы: {items}")
        else:
            await update.message.reply_text("❌ Неверный промокод.")
        context.remove_handler(handler)  # Убираем после использования

    handler = CommandHandler("text", get_code)
    context.add_handler(handler)

# ---------------------- Админ-панель ----------------------
async def admin_panel(query):
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ Только админ может открыть панель.")
        return
    keyboard = [
        [InlineKeyboardButton("💎 Выдать валюту", callback_data="give_money")],
        [InlineKeyboardButton("👑 Выдать VIP", callback_data="give_vip")],
        [InlineKeyboardButton("⛔ Бан/Разбан", callback_data="ban_user")]
    ]
    await query.edit_message_text("🛠️ Админ-панель", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------------------- Дуэли ----------------------
DUEL_QUEUE = []

async def duel(query):
    user_id = query.from_user.id
    DUEL_QUEUE.append(user_id)
    await query.edit_message_text("⚔ Вы в очереди на дуэль. Ожидаем противника...")
    if len(DUEL_QUEUE) >= 2:
        p1, p2 = DUEL_QUEUE.pop(0), DUEL_QUEUE.pop(0)
        stake = random.randint(5, 20)
        winner = random.choice([p1, p2])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (stake, winner))
            await db.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (stake, p1 if winner==p2 else p2))
            await db.commit()
        await query.edit_message_text(f"⚔ Дуэль завершена! Победитель: {winner} (ставка {stake} монет)")

# ---------------------- Кнопки ----------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "expedition":
        await start_expedition(query)
    elif query.data == "shop":
        await shop(query)
    elif query.data == "profile":
        await profile(query)
    elif query.data == "leaderboard":
        await leaderboard(query)
    elif query.data == "admin":
        await admin_panel(query)
    elif query.data == "duel":
        await duel(query)
    elif query.data == "missions":
        await missions(query)
    elif query.data == "promocode":
        await promocode(query)

# ---------------------- Основной цикл ----------------------
async def main():
    await init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("Бот запущен...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

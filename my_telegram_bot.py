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
                            currency INTEGER DEFAULT 0,
                            vip_days INTEGER DEFAULT 0,
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
async def get_user_by_username(username):
    """Получить user_id по username"""
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT user_id FROM users WHERE username=?", (username,)) as cursor:
            result = await cursor.fetchone()
        return result[0] if result else None

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

async def set_vip(user_id, days):
    expires = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET vip_until=? WHERE user_id=?", (expires, user_id))
        await db.commit()

async def ban_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO banned_users(user_id) VALUES(?)", (user_id,))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
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
        async with db.execute("SELECT currency, vip_days, uses_left, expires_at FROM promo_codes WHERE code=?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
        if not promo:
            return "❌ Промокод не найден."
        currency, vip_days, uses_left, expires_at = promo
        if uses_left <= 0:
            return "❌ Промокод исчерпан."
        if expires_at and datetime.utcnow() > datetime.fromisoformat(expires_at):
            return "❌ Промокод истёк."
        
        result = ""
        if currency > 0:
            await update_balance(user_id, currency)
            result += f"✅ Получено {currency} валюты!\n"
        if vip_days > 0:
            await set_vip(user_id, vip_days)
            result += f"✅ Получен VIP на {vip_days} дней!\n"
        
        await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code=?", (code.upper(),))
        await db.commit()
        return result or "❌ Промокод не содержит наград."

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
            msg += f"\nВы нашли {item}!"
        await query.edit_message_text(msg)

    # ---------- ПРОФИЛЬ ----------
    elif data == "profile":
        user = await get_user(user_id)
        inv = await get_inventory(user_id)
        vip_status = f"VIP до {user[3]}" if user[3] else "Нет VIP"
        text = f"Профиль @{user[1] or 'неизвестно'}:\nБаланс: {user[2]}\nVIP: {vip_status}\nИнвентарь: {', '.join(inv) if inv else 'Пусто'}"
        await query.edit_message_text(text)

    # ---------- ТОП 10 ----------
    elif data == "top":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        text = "🏆 Топ 10 по валюте:\n" + "\n".join([f"{i+1}. @{r[0] or 'неизвестно'} — {r[1]}" for i,r in enumerate(rows)])
        await query.edit_message_text(text)

    # ---------- МАГАЗИН ----------
    elif data == "shop":
        kb = [[InlineKeyboardButton(f"{item} ({info['price']})", callback_data=f"shop_{item}")] for item, info in SHOP_ITEMS.items()]
        kb.append([InlineKeyboardButton("Вернуться в меню", callback_data="start")])
        await query.edit_message_text("🛒 Магазин:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("shop_"):
        item_name = data[5:]
        info = SHOP_ITEMS[item_name]
        kb = [
            [InlineKeyboardButton("💰 Купить", callback_data=f"buy_{item_name}")],
            [InlineKeyboardButton("⬅️ Назад в магазин", callback_data="shop")]
        ]
        await query.edit_message_text(f"{item_name}\n💰 Цена: {info['price']}\n📝 {info['description']}", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("buy_"):
        item_name = data[4:]
        user = await get_user(user_id)
        price = SHOP_ITEMS[item_name]["price"]
        if user[2] >= price:
            await update_balance(user_id, -price)
            await add_item(user_id, item_name)
            await query.edit_message_text(f"✅ Вы купили {item_name}!")
        else:
            await query.edit_message_text(f"❌ Недостаточно валюты! Нужно: {price}")

    # ---------- ИНВЕНТАРЬ ----------
    elif data == "inventory":
        inv = await get_inventory(user_id)
        if not inv or inv == ['']:
            await query.edit_message_text("🎒 Инвентарь пуст.")
            return
        kb = [[InlineKeyboardButton(item, callback_data=f"use_{item}")] for item in inv if item]
        kb.append([InlineKeyboardButton("⬅️ В меню", callback_data="start")])
        await query.edit_message_text("🎒 Инвентарь:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("use_"):
        item_name = data[4:]
        await query.edit_message_text(f"✅ Вы использовали {item_name}!")

    # ---------- ЭКСПЕДИЦИИ ----------
    elif data == "expedition":
        reward = random.randint(20, 100)
        await update_balance(user_id, reward)
        await query.edit_message_text(f"🌍 Экспедиция завершена!\n💰 Получено: {reward} валюты!")

    # ---------- МИССИИ ----------
    elif data == "mission":
        reward = random.randint(30, 120)
        await update_balance(user_id, reward)
        await query.edit_message_text(f"🎯 Миссия выполнена!\n💰 Получено: {reward} валюты!")

    # ---------- ПРОМОКОД ----------
    elif data == "promo":
        context.user_data['waiting_promo'] = True
        await query.edit_message_text("🎁 Введите промокод:")

    # ---------- АДМИН-ПАНЕЛЬ ----------
    elif data == "admin" and user_id in ADMIN_IDS:
        kb = [
            [InlineKeyboardButton("💰 Выдать валюту", callback_data="admin_currency")],
            [InlineKeyboardButton("👑 Выдать VIP", callback_data="admin_vip")],
            [InlineKeyboardButton("🔨 Бан", callback_data="admin_ban")],
            [InlineKeyboardButton("✅ Разбан", callback_data="admin_unban")],
            [InlineKeyboardButton("➕ Создать промокод", callback_data="admin_promo_create")],
            [InlineKeyboardButton("🗑️ Удалить промокод", callback_data="admin_promo_delete")],
            [InlineKeyboardButton("⬅️ В меню", callback_data="start")]
        ]
        await query.edit_message_text("🔧 Админ-панель:", reply_markup=InlineKeyboardMarkup(kb))

    # ---------- АДМИН ДЕЙСТВИЯ - Запрос username ----------
    elif data.startswith("admin_") and user_id in ADMIN_IDS:
        actions_need_username = ["admin_currency", "admin_vip", "admin_ban", "admin_unban"]
        if data in actions_need_username:
            context.user_data['admin_action'] = data
            await query.edit_message_text("👤 Введите @username пользователя (без @):")
        elif data == "admin_promo_create":
            context.user_data['admin_action'] = data
            await query.edit_message_text("🎁 Создать промокод\nФормат: CODE сумма_валюты_или_vip_дней количество_использований [дата_истечения YYYY-MM-DD]\nПример: WELCOME100 100 1000\nПример: VIP7 vip 7 500 2025-12-31")
        elif data == "admin_promo_delete":
            context.user_data['admin_action'] = data
            await query.edit_message_text("🗑️ Введите название промокода для удаления:")

    # ---------- ВОЗВРАТ В МЕНЮ ----------
    elif data == "start":
        await start(update, context)

# =========================
# Обработка текстового ввода
# =========================
async def message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Проверка на промокод
    if context.user_data.get('waiting_promo'):
        context.user_data['waiting_promo'] = False
        result = await use_promocode(user_id, text)
        await update.message.reply_text(result)
        return

    # Проверка на админа
    if user_id in ADMIN_IDS:
        action = context.user_data.get('admin_action')
        if action:
            if action in ["admin_currency", "admin_vip", "admin_ban", "admin_unban"]:
                # Поиск пользователя по username
                username = text.lstrip('@')
                target_id = await get_user_by_username(username)
                
                if not target_id:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
                
                context.user_data['target_user_id'] = target_id
                context.user_data['target_username'] = username
                
                if action == "admin_currency":
                    await update.message.reply_text(f"✅ Найден @{username} (ID: {target_id})\n💰 Введите сумму для выдачи:")
                elif action == "admin_vip":
                    await update.message.reply_text(f"✅ Найден @{username} (ID: {target_id})\n👑 Введите количество дней VIP:")
                elif action == "admin_ban":
                    await ban_user(target_id)
                    await update.message.reply_text(f"✅ Пользователь @{username} (ID: {target_id}) забанен!")
                    context.user_data['admin_action'] = None
                    return
                elif action == "admin_unban":
                    unban_user(target_id)
                    await update.message.reply_text(f"✅ Пользователь @{username} (ID: {target_id}) разбанен!")
                    context.user_data['admin_action'] = None
                    return
                    
            elif action == "admin_promo_create":
                try:
                    parts = text.split()
                    code = parts[0].upper()
                    param1 = parts[1].lower()
                    
                    if param1 == "vip":
                        vip_days = int(parts[2])
                        currency = 0
                        uses_left = int(parts[3])
                        expires_at = parts[4] if len(parts) > 4 else None
                    else:
                        currency = int(param1)
                        vip_days = 0
                        uses_left = int(parts[2])
                        expires_at = parts[3] if len(parts) > 3 else None
                    
                    expires_iso = None
                    if expires_at:
                        expires_iso = datetime.strptime(expires_at, "%Y-%m-%d").isoformat()
                    
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("""INSERT OR REPLACE INTO promo_codes 
                                         (code, currency, vip_days, uses_left, expires_at) 
                                         VALUES(?,?,?,?,?)""",
                                       (code, currency, vip_days, uses_left, expires_iso))
                        await db.commit()
                    
                    msg = f"✅ Промокод **{code}** создан!\n"
                    if currency > 0:
                        msg += f"💰 Валюта: {currency}\n"
                    if vip_days > 0:
                        msg += f"👑 VIP: {vip_days} дней\n"
                    msg += f"🔢 Использований: {uses_left}"
                    await update.message.reply_text(msg)
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка создания промокода: {str(e)}")
                context.user_data['admin_action'] = None
                return
                
            elif action == "admin_promo_delete":
                try:
                    code = text.upper()
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("DELETE FROM promo_codes WHERE code=?", (code,))
                        await db.commit()
                    await update.message.reply_text(f"✅ Промокод **{code}** удалён!")
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка удаления: {str(e)}")
                context.user_data['admin_action'] = None
                return
            
            # Финальные действия после ввода суммы/дней
            if 'target_user_id' in context.user_data:
                target_id = context.user_data['target_user_id']
                target_username = context.user_data['target_username']
                
                try:
                    amount = int(text)
                    if action == "admin_currency":
                        await update_balance(target_id, amount)
                        await update.message.reply_text(f"✅ @{target_username}: +{amount} валюты!")
                    elif action == "admin_vip":
                        await set_vip(target_id, amount)
                        await update.message.reply_text(f"✅ @{target_username}: VIP на {amount} дней!")
                except:
                    await update.message.reply_text("❌ Ошибка! Введите число.")
                
                context.user_data.pop('target_user_id', None)
                context.user_data.pop('target_username', None)
                context.user_data['admin_action'] = None
                return

    # Обычный промокод для не-админов
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

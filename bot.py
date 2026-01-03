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
                            duels_lost INTEGER DEFAULT 0,
                            last_mine TIMESTAMP DEFAULT '',
                            last_expedition TIMESTAMP DEFAULT '',
                            last_mission TIMESTAMP DEFAULT '',
                            daily_mission TEXT DEFAULT '',
                            mission_progress INTEGER DEFAULT 0
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promo_codes(
                            code TEXT PRIMARY KEY,
                            currency INTEGER DEFAULT 0,
                            vip_days INTEGER DEFAULT 0,
                            uses_left INTEGER,
                            expires_at TEXT
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS duels(
                            duel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            challenger_id INTEGER,
                            opponent_id INTEGER,
                            bet INTEGER,
                            status TEXT DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS banned_users(
                            user_id INTEGER PRIMARY KEY
                            )""")
        await db.commit()
    print("✅ Database initialized")

# =========================
# Вспомогательные функции
# =========================
async def is_banned(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_user_by_username(username):
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

async def can_action(user_id, action):
    """Проверка кулдауна для действий"""
    now = datetime.utcnow()
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT last_mine, last_expedition, last_mission FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
    
    cooldowns = {
        'mine': 900,  # 15 минут
        'expedition': 3600,  # 1 час
        'mission': 7200  # 2 часа
    }
    
    last_time = {
        'mine': user[0],
        'expedition': user[1],
        'mission': user[2]
    }.get(action)
    
    if last_time:
        last_time = datetime.fromisoformat(last_time)
        if (now - last_time).total_seconds() < cooldowns[action]:
            return False, int(cooldowns[action] - (now - last_time).total_seconds())
    
    return True, 0

async def update_last_action(user_id, action):
    now_str = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_FILE) as db:
        if action == 'mine':
            await db.execute("UPDATE users SET last_mine=? WHERE user_id=?", (now_str, user_id))
        elif action == 'expedition':
            await db.execute("UPDATE users SET last_expedition=? WHERE user_id=?", (now_str, user_id))
        elif action == 'mission':
            await db.execute("UPDATE users SET last_mission=? WHERE user_id=?", (now_str, user_id))
        await db.commit()

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
        if item not in inv_list:
            inv_list.append(item)
        await db.execute("UPDATE users SET inventory=? WHERE user_id=?", (",".join(inv_list), user_id))
        await db.commit()

async def remove_item(user_id, item):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT inventory FROM users WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
        inv_list = inv[0].split(",") if inv[0] else []
        if item in inv_list:
            inv_list.remove(item)
        await db.execute("UPDATE users SET inventory=? WHERE user_id=?", (",".join(inv_list), user_id))
        await db.commit()

async def get_inventory(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT inventory FROM users WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
    return [item for item in inv[0].split(",") if item] if inv and inv[0] else []

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
            result += f"💰 +{currency} валюты!\n"
        if vip_days > 0:
            await set_vip(user_id, vip_days)
            result += f"👑 VIP на {vip_days} дней!\n"
        
        await db.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code=?", (code.upper(),))
        await db.commit()
        return result or "❌ Промокод не содержит наград."

# =========================
# Магазин - РАСШИРЕННЫЙ
# =========================
SHOP_ITEMS = {
    "🥷 Ниндзя-кинжал": {"price": 150, "description": "Увеличивает шанс критического удара +20%"},
    "🛡️ Мифический щит": {"price": 200, "description": "Блокирует 50% урона в дуэлях"},
    "⚗️ Эликсир силы": {"price": 80, "description": "Временный баф: +50% к урону на 3 дуэли"},
    "💎 Редкий сундук": {"price": 500, "description": "Гарантированная легендарная награда"},
    "🎒 Большой рюкзак": {"price": 300, "description": "+50% к наградам от экспедиций"},
    "🔮 Кристалл удачи": {"price": 250, "description": "+25% шанс дропа редких предметов"},
    "🍀 Амулет fortune": {"price": 400, "description": "Удваивает награду от миссий 1 раз в день"},
    "👑 Корона чемпиона": {"price": 1000, "description": "VIP статус +15 дней + титул в профиле"}
}

# =========================
# ДУЭЛИ - ПОЛНАЯ СИСТЕМА
# =========================
async def create_duel(challenger_id, opponent_id, bet):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("INSERT INTO duels(challenger_id, opponent_id, bet) VALUES(?,?,?)", 
                                (challenger_id, opponent_id, bet))
        duel_id = cursor.lastrowid
        await db.commit()
        return duel_id

async def resolve_duel(duel_id, winner_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM duels WHERE duel_id=?", (duel_id,)) as cursor:
            duel = await cursor.fetchone()
        
        if not duel or duel[4] != 'pending':
            return False
        
        challenger_id, opponent_id, bet = duel[1], duel[2], duel[3]
        
        # Обновляем статистику
        if winner_id == challenger_id:
            await db.execute("UPDATE users SET duels_won = duels_won + 1 WHERE user_id=?", (challenger_id,))
            await db.execute("UPDATE users SET duels_lost = duels_lost + 1 WHERE user_id=?", (opponent_id,))
        else:
            await db.execute("UPDATE users SET duels_won = duels_won + 1 WHERE user_id=?", (opponent_id,))
            await db.execute("UPDATE users SET duels_lost = duels_lost + 1 WHERE user_id=?", (challenger_id,))
        
        # Переводим ставку
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (bet*2, winner_id))
        await db.execute("UPDATE duels SET status='completed' WHERE duel_id=?", (duel_id,))
        await db.commit()
        return True

# =========================
# Главное меню
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
        
    user = await get_user(update.effective_user.id, update.effective_user.username)
    kb = [
        [InlineKeyboardButton("⛏️ Добыча", callback_data="mine")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile"),
         InlineKeyboardButton("🏆 Топ 10", callback_data="top")],
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🌍 Экспедиции", callback_data="expedition"),
         InlineKeyboardButton("🎯 Миссии", callback_data="mission")],
        [InlineKeyboardButton("⚔️ Дуэли", callback_data="duel")],
        [InlineKeyboardButton("🔧 Админ" if update.effective_user.id in ADMIN_IDS else "🎁 Промокод", 
                              callback_data="admin" if update.effective_user.id in ADMIN_IDS else "promo")]
    ]
    await update.message.reply_text("🎮 **Главное меню бота**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# =========================
# Обработка кнопок
# =========================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if await is_banned(user_id):
        await query.edit_message_text("🚫 Вы заблокированы!")
        return

    # ---------- ДОБЫЧА ----------
    if data == "mine":
        can_mine, cooldown = await can_action(user_id, 'mine')
        if not can_mine:
            await query.edit_message_text(f"⏳ Добыча доступна через {cooldown//60}м {cooldown%60}с")
            return
        
        await update_last_action(user_id, 'mine')
        gain = random.randint(15, 75)
        await update_balance(user_id, gain)
        msg = f"⛏️ **Добыча завершена!**\n💰 +{gain} валюты!"
        
        if random.random() < 0.15:  # 15% шанс сундука
            chest = random.choice(["💎 Редкий сундук", "🥇 Золотой сундук"])
            await add_item(user_id, chest)
            msg += f"\n\n{chest} найден!"
            
        await query.edit_message_text(msg, parse_mode='Markdown')

    # ---------- ПРОФИЛЬ ----------
    elif data == "profile":
        user = await get_user(user_id)
        inv = await get_inventory(user_id)
        vip_status = "👑 VIP" if user[3] else "➖ Нет VIP"
        text = f"""📊 **Профиль @{user[1] or 'неизвестно'}**

💰 Баланс: `{user[2]}`
{vip_status}
⚔️ Побед: {user[5]} | Поражений: {user[6]}
🎒 Инвентарь: {len(inv)} предметов"""
        await query.edit_message_text(text, parse_mode='Markdown')

    # ---------- ТОП 10 ----------
    elif data == "top":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10") as cursor:
                rows = await cursor.fetchall()
        text = "🏆 **Топ 10 по богатству:**\n\n"
        for i, (username, balance) in enumerate(rows):
            text += f"{i+1}. @{username or 'неизвестно'} — `{balance}`\n"
        await query.edit_message_text(text, parse_mode='Markdown')

    # ---------- МАГАЗИН ----------
    elif data == "shop":
        text = "🛒 **Магазин**\n\n"
        kb = []
        for i, (item, info) in enumerate(SHOP_ITEMS.items()):
            text += f"**{item}** — `{info['price']}`\n{info['description']}\n\n"
            kb.append([InlineKeyboardButton(f"{item} ({info['price']})", callback_data=f"shop_{item}")])
        kb.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="start")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("shop_"):
        item_name = data[5:]
        info = SHOP_ITEMS[item_name]
        kb = [
            [InlineKeyboardButton("💰 Купить", callback_data=f"buy_{item_name}")],
            [InlineKeyboardButton("⬅️ В магазин", callback_data="shop"),
             InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
        ]
        text = f"**{item_name}**\n\n💰 Цена: `{info['price']}`\n📝 {info['description']}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("buy_"):
        item_name = data[4:]
        user = await get_user(user_id)
        price = SHOP_ITEMS[item_name]["price"]
        if user[2] >= price:
            await update_balance(user_id, -price)
            await add_item(user_id, item_name)
            await query.edit_message_text(f"✅ **Покупка успешна!**\nВы приобрели: {item_name}", parse_mode='Markdown')
        else:
            await query.edit_message_text(f"❌ **Недостаточно средств!**\nНужно: `{price}`, есть: `{user[2]}`", parse_mode='Markdown')

    # ---------- ИНВЕНТАРЬ ----------
    elif data == "inventory":
        inv = await get_inventory(user_id)
        if not inv:
            await query.edit_message_text("🎒 **Инвентарь пуст**\nПерейдите в магазин!", parse_mode='Markdown')
            return
        
        text = "🎒 **Инвентарь:**\n\n"
        kb = []
        for item in inv[:10]:  # Первые 10 предметов
            text += f"• {item}\n"
            kb.append([InlineKeyboardButton(item[:20], callback_data=f"use_{item}")])
        if len(inv) > 10:
            text += f"\n... и ещё {len(inv)-10} предметов"
        
        kb.append([InlineKeyboardButton("🏠 Главное меню", callback_data="start")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("use_"):
        item_name = data[4:]
        inv = await get_inventory(user_id)
        if item_name not in inv:
            await query.edit_message_text("❌ Предмет не найден!")
            return
        
        await remove_item(user_id, item_name)
        
        if "сундук" in item_name.lower():
            # Случайная награда из сундука
            rewards = list(SHOP_ITEMS.keys()) + ["💰 500 валюты", "👑 VIP 3 дня"]
            reward = random.choice(rewards)
            if "валюты" in reward:
                await update_balance(user_id, 500)
                msg = f"✅ **Сундук открыт!**\n{reward}"
            elif "VIP" in reward:
                await set_vip(user_id, 3)
                msg = f"✅ **Сундук открыт!**\n{reward}"
            else:
                await add_item(user_id, reward)
                msg = f"✅ **Сундук открыт!**\nПолучен: {reward}"
        else:
            msg = f"✅ **{item_name} использован!**"
        
        await query.edit_message_text(msg, parse_mode='Markdown')

    # ---------- ЭКСПЕДИЦИИ ----------
    elif data == "expedition":
        can_exp, cooldown = await can_action(user_id, 'expedition')
        if not can_exp:
            await query.edit_message_text(f"⏳ Экспедиция доступна через {cooldown//60}м {cooldown%60}с")
            return
        
        await update_last_action(user_id, 'expedition')
        reward = random.randint(50, 250)
        await update_balance(user_id, reward)
        msg = f"🌍 **Экспедиция завершена!**\n💰 +{reward} валюты!"
        
        if random.random() < 0.2:
            item = random.choice(["🔮 Кристалл удачи", "🍀 Амулет fortune"])
            await add_item(user_id, item)
            msg += f"\n\n{item} найден!"
            
        await query.edit_message_text(msg, parse_mode='Markdown')

    # ---------- МИССИИ ----------
    elif data == "mission":
        can_miss, cooldown = await can_action(user_id, 'mission')
        if not can_miss:
            await query.edit_message_text(f"⏳ Миссия доступна через {cooldown//60}м {cooldown%60}с")
            return
        
        await update_last_action(user_id, 'mission')
        reward = random.randint(75, 300)
        await update_balance(user_id, reward)
        msg = f"🎯 **Миссия выполнена!**\n💰 +{reward} валюты!"
        
        if random.random() < 0.25:
            item = random.choice(list(SHOP_ITEMS.keys())[:3])
            await add_item(user_id, item)
            msg += f"\n\n{item} получен!"
            
        await query.edit_message_text(msg, parse_mode='Markdown')

    # ---------- ДУЭЛИ ----------
    elif data == "duel":
        kb = [
            [InlineKeyboardButton("⚔️ Создать дуэль", callback_data="duel_create")],
            [InlineKeyboardButton("📋 Мои дуэли", callback_data="duel_my")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
        ]
        await query.edit_message_text(
            "⚔️ **Дуэли**\n\n"
            "**Правила:**\n"
            "• Выберите ставку\n"
            "• Укажите оппонента по @username\n"
            "• Победитель забирает ВСЕ деньги\n"
            "• Бой проходит автоматически\n\n"
            "**Формат вызова:**\n"
            "`@username 100` - вызов на 100 валюты",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
        )

    elif data == "duel_create":
        context.user_data['waiting_duel'] = True
        await query.edit_message_text(
            "⚔️ **Создать дуэль**\n\n"
            "Введите: `@username сумма`\n"
            "Пример: `@friend123 500`",
            parse_mode='Markdown'
        )

    elif data == "duel_my":
        # Пока заглушка - можно добавить позже
        await query.edit_message_text("📋 **Ваши дуэли**\nФункция в разработке", parse_mode='Markdown')

    # ---------- ПРОМОКОД ----------
    elif data == "promo":
        context.user_data['waiting_promo'] = True
        await query.edit_message_text("🎁 **Введите промокод:**")

    # ---------- АДМИН-ПАНЕЛЬ ----------
    elif data == "admin" and user_id in ADMIN_IDS:
        kb = [
            [InlineKeyboardButton("💰 Выдать валюту", callback_data="admin_currency")],
            [InlineKeyboardButton("👑 Выдать VIP", callback_data="admin_vip")],
            [InlineKeyboardButton("🔨 Бан", callback_data="admin_ban"),
             InlineKeyboardButton("✅ Разбан", callback_data="admin_unban")],
            [InlineKeyboardButton("➕ Создать промокод", callback_data="admin_promo_create")],
            [InlineKeyboardButton("🗑️ Удалить промокод", callback_data="admin_promo_delete")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="start")]
        ]
        await query.edit_message_text("🔧 **Админ-панель**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("admin_") and user_id in ADMIN_IDS:
        actions_need_username = ["admin_currency", "admin_vip", "admin_ban", "admin_unban"]
        if data in actions_need_username:
            context.user_data['admin_action'] = data
            await query.edit_message_text("👤 **Введите @username** (без знака @):", parse_mode='Markdown')
        elif data == "admin_promo_create":
            context.user_data['admin_action'] = data
            await query.edit_message_text(
                "🎁 **Создать промокод**\n\n"
                "**Формат:** `КОД сумма_валюты_или_vip_дней количество_использований [дата]`\n\n"
                "**Примеры:**\n"
                "`WELCOME100 100 1000` → 100 валют\n"
                "`VIP7 vip 7 500` → VIP 7 дней\n"
                "`GOLDEN 500 200 2025-12-31` → 500 валют до конца года",
                parse_mode='Markdown'
            )
        elif data == "admin_promo_delete":
            context.user_data['admin_action'] = data
            await query.edit_message_text("🗑️ **Введите название промокода:**", parse_mode='Markdown')

    elif data == "start":
        await start(update, context)

# =========================
# Обработка текстового ввода
# =========================
async def message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if await is_banned(user_id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return

    # Дуэль вызов
    if context.user_data.get('waiting_duel'):
        context.user_data['waiting_duel'] = False
        try:
            parts = text.split()
            if len(parts) < 2:
                await update.message.reply_text("❌ Формат: `@username сумма`")
                return
            
            opponent_username = parts[0].lstrip('@')
            bet = int(parts[1])
            
            user = await get_user(user_id)
            if user[2] < bet:
                await update.message.reply_text(f"❌ Недостаточно валюты! Нужно: {bet}")
                return
            
            opponent_id = await get_user_by_username(opponent_username)
            if not opponent_id:
                await update.message.reply_text(f"❌ Пользователь @{opponent_username} не найден!")
                return
            
            if opponent_id == user_id:
                await update.message.reply_text("❌ Нельзя вызвать себя на дуэль!")
                return
            
            await update_balance(user_id, -bet)
            duel_id = await create_duel(user_id, opponent_id, bet)
            
            # Автоматический бой через 30 секунд (можно изменить)
            await asyncio.sleep(30)
            winner = random.choice([user_id, opponent_id])
            await resolve_duel(duel_id, winner)
            
            result = "Выиграл!" if winner == user_id else "Проиграл!"
            await update.message.reply_text(f"⚔️ **Дуэль завершена!**\nРезультат: {result}\n💰 Получено: {bet*2}", parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        return

    # Промокод
    if context.user_data.get('waiting_promo'):
        context.user_data['waiting_promo'] = False
        result = await use_promocode(user_id, text)
        await update.message.reply_text(result)
        return

    # Админ действия
    if user_id in ADMIN_IDS:
        action = context.user_data.get('admin_action')
        if action:
            # Поиск username
            if action in ["admin_currency", "admin_vip", "admin_ban", "admin_unban"]:
                username = text.lstrip('@')
                target_id = await get_user_by_username(username)
                
                if not target_id:
                    await update.message.reply_text(f"❌ Пользователь @{username} не найден!")
                    return
                
                context.user_data['target_user_id'] = target_id
                context.user_data['target_username'] = username
                
                if action == "admin_currency":
                    await update.message.reply_text(f"✅ Найден @{username}\n💰 **Введите сумму:**", parse_mode='Markdown')
                elif action == "admin_vip":
                    await update.message.reply_text(f"✅ Найден @{username}\n👑 **Введите дни VIP:**", parse_mode='Markdown')
                elif action == "admin_ban":
                    await ban_user(target_id)
                    await update.message.reply_text(f"✅ **@{username} забанен!**", parse_mode='Markdown')
                    context.user_data['admin_action'] = None
                    return
                elif action == "admin_unban":
                    await unban_user(target_id)
                    await update.message.reply_text(f"✅ **@{username} разбанен!**", parse_mode='Markdown')
                    context.user_data['admin_action'] = None
                    return
            
            # Создание промокода - ИСПРАВЛЕНО
            elif action == "admin_promo_create":
                try:
                    parts = text.split()
                    if len(parts) < 3:
                        await update.message.reply_text("❌ Минимум 3 параметра: КОД значение количество")
                        return
                    
                    code = parts[0].upper()
                    param1 = parts[1].lower()
                    uses_left = int(parts[2])
                    
                    currency = 0
                    vip_days = 0
                    expires_at = None
                    
                    if param1 == "vip":
                        vip_days = int(parts[2])
                    else:
                        currency = int(param1)
                    
                    if len(parts) > 3:
                        expires_at = datetime.strptime(parts[3], "%Y-%m-%d").isoformat()
                    
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute("""INSERT OR REPLACE INTO promo_codes 
                                         (code, currency, vip_days, uses_left, expires_at) 
                                         VALUES(?,?,?,?,?)""",
                                       (code, currency, vip_days, uses_left, expires_at))
                        await db.commit()
                    
                    msg = f"✅ **Промокод `{code}` создан!**\n"
                    if currency > 0:
                        msg += f"💰 `{currency}` валюты\n"
                    if vip_days > 0:
                        msg += f"👑 `{vip_days}` дней VIP\n"
                    msg += f"🔢 `{uses_left}` использований"
                    
                    await update.message.reply_text(msg, parse_mode='Markdown')
                    
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка: `{str(e)}`", parse_mode='Markdown')
                context.user_data['admin_action'] = None
                return
            
            # Удаление промокода
            elif action == "admin_promo_delete":
                try:
                    code = text.upper()
                    async with aiosqlite.connect(DB_FILE) as db:
                        cursor = await db.execute("DELETE FROM promo_codes WHERE code=?", (code,))
                        await db.commit()
                    if cursor.rowcount > 0:
                        await update.message.reply_text(f"✅ **Промокод `{code}` удалён!**", parse_mode='Markdown')
                    else:
                        await update.message.reply_text(f"❌ Промокод `{code}` не найден!", parse_mode='Markdown')
                except Exception as e:
                    await update.message.reply_text(f"❌ Ошибка: `{str(e)}`", parse_mode='Markdown')
                context.user_data['admin_action'] = None
                return
            
            # Финальные админ действия
            if 'target_user_id' in context.user_data:
                target_id = context.user_data['target_user_id']
                target_username = context.user_data['target_username']
                
                try:
                    amount = int(text)
                    if action == "admin_currency":
                        await update_balance(target_id, amount)
                        await update.message.reply_text(f"✅ **@{target_username}:** `+{amount}` валюты!", parse_mode='Markdown')
                    elif action == "admin_vip":
                        await set_vip(target_id, amount)
                        await update.message.reply_text(f"✅ **@{target_username}:** VIP `{amount}` дней!", parse_mode='Markdown')
                except:
                    await update.message.reply_text("❌ **Введите число!**", parse_mode='Markdown')
                
                context.user_data.pop('target_user_id', None)
                context.user_data.pop('target_username', None)
                context.user_data['admin_action'] = None
                return

    # Обычный промокод
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

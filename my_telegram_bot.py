import logging
import os
import asyncio
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные состояния
user_states = {}
duel_rooms = {}
clan_bosses = {}  # {clan_id: {'boss_hp': 1000, 'participants': [], 'start_time': time}}

async def init_db(application: Application):
    async with aiosqlite.connect('bot.db') as db:
        # БАЗОВЫЕ ТАБЛИЦЫ
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0, vip_until REAL DEFAULT 0,
            sword INTEGER DEFAULT 0, crown INTEGER DEFAULT 0, shield INTEGER DEFAULT 0,
            pickaxe INTEGER DEFAULT 0, helmet INTEGER DEFAULT 0, armor INTEGER DEFAULT 0,
            amulet INTEGER DEFAULT 0, ring INTEGER DEFAULT 0,
            clan_power INTEGER DEFAULT 0, buffs TEXT DEFAULT '{}', debuffs TEXT DEFAULT '{}'
        )''')
        
        # КЛАНЫ + БОССЫ + БАФЫ
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            max_members INTEGER DEFAULT 15, current_members INTEGER DEFAULT 1,
            treasury INTEGER DEFAULT 0, level INTEGER DEFAULT 1, power INTEGER DEFAULT 0,
            boss_active INTEGER DEFAULT 0, boss_hp INTEGER DEFAULT 0, boss_timer REAL DEFAULT 0,
            buffs TEXT DEFAULT '{}', debuffs TEXT DEFAULT '{}',
            created_at REAL DEFAULT (strftime('%s','now'))
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            user_id INTEGER, clan_id INTEGER, role TEXT DEFAULT 'member',
            joined_at REAL DEFAULT (strftime('%s','now')), power INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, clan_id)
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_requests (
            user_id INTEGER, clan_id INTEGER, created_at REAL DEFAULT (strftime('%s','now')),
            PRIMARY KEY (user_id, clan_id)
        )''')
        
        # АДМИН ТАБЛИЦЫ
        await db.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER DEFAULT 0, max_uses INTEGER
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY, reason TEXT)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS shop_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, 
            emoji TEXT, description TEXT, type TEXT DEFAULT 'item'
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS vip_packages (
            package_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER,
            duration_days INTEGER, multiplier REAL DEFAULT 2.0, description TEXT
        )''')
        
        # ИНИЦИАЛИЗАЦИЯ ДАННЫХ
        await db.executemany("INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES (?, ?, ?)",
            [('WELCOME1000', 1000, 100), ('CLANSTART', 50000, 10), ('MINER2024', 2500, 50), ('LUCKYDAY', 5000, 20)])
        
        await db.executemany("INSERT OR IGNORE INTO shop_items (item_id, name, price, emoji, description, type) VALUES (?, ?, ?, ?, ?, ?)",
            [(1, 'Легендарный меч', 500, '⚔️', '+50% к урону в дуэлях', 'item'),
             (2, 'Королевская корона', 1000, '👑', '+25% ко всем доходам', 'item'),
             (3, 'Абсолютный щит', 750, '🛡️', '+30% защиты в дуэлях', 'item'),
             (9, 'Бронзовый сундук', 200, '📦', 'Рандом: 100-500₽ + предметы', 'chest')])
        
        await db.executemany("INSERT OR IGNORE INTO vip_packages (package_id, name, price, duration_days, multiplier, description) VALUES (?, ?, ?, ?, ?, ?)",
            [(1, 'VIP 7 дней', 500, 7, 2.0, '+100% ко всем доходам'),
             (2, 'VIP 30 дней', 1500, 30, 2.5, '+150% ко всем доходам + эксклюзив')])
        
        # ТЕСТОВЫЕ КЛАНЫ
        await db.executemany("INSERT OR IGNORE INTO clans (clan_id, name, leader_id, power) VALUES (?, ?, ?, ?)",
            [(1, 'ИМПЕРИЯ', 123456789, 50000),
             (2, 'ЛЕГЕНДЫ', 987654321, 45000)])
        
        await db.commit()
        logger.info("✅ База данных инициализирована")

# 🛠️ КЛАНОВЫЕ ФУНКЦИИ (ПОЛНЫЕ)
async def get_user_clan(user_id):
    user = await get_user_data(user_id)
    return user[8] if user else None  # clan_id

async def join_clan_by_id(user_id, clan_id):
    clan = await get_clan_data(clan_id)
    if not clan:
        return False, "❌ Клан не найден!"
    
    user_clan = await get_user_clan(user_id)
    if user_clan:
        return False, "❌ Вы уже в клане!"
    
    if clan[4] >= clan[3]:  # current_members >= max_members
        return False, "❌ Клан полный!"
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE clans SET current_members = current_members + 1 WHERE clan_id = ?', (clan_id,))
        await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, user_id))
        await db.execute('INSERT INTO clan_members (user_id, clan_id) VALUES (?, ?)', (user_id, clan_id))
        await db.commit()
    return True, f"✅ Вступили в **[{clan[1]}]**!"

async def create_clan(user_id, clan_name):
    async with aiosqlite.connect('bot.db') as db:
        try:
            clan_id = int(time.time())
            await db.execute('INSERT INTO clans (clan_id, name, leader_id, current_members) VALUES (?, ?, ?, 1)', 
                           (clan_id, clan_name, user_id))
            await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, user_id))
            await db.execute('INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, "leader")', (user_id, clan_id))
            await db.commit()
            return True, f"🏰 **{clan_name}** создан! ID: `{clan_id}`"
        except:
            return False, "❌ Ошибка создания клана!"

async def get_all_clans():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT clan_id, name, power, current_members, max_members FROM clans ORDER BY power DESC LIMIT 20') as cursor:
            return await cursor.fetchall()

# 🛠️ АДМИН УТИЛИТЫ (исправленные)
async def admin_get_all_promocodes():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM promos') as cursor:
            return await cursor.fetchall()

async def admin_get_all_shop_items():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM shop_items ORDER BY item_id') as cursor:
            return await cursor.fetchall()

def admin_shop_menu(items):
    keyboard = []
    for item in items[:8]:
        keyboard.append([InlineKeyboardButton(f"{item[3]} {item[1]} ({item[2]}₽)", callback_data=f"admin_shop_view_{item[0]}")])
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить", callback_data="admin_shop_add")],
        [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
    ])
    return InlineKeyboardMarkup(keyboard)

def admin_promo_menu(promocodes):
    keyboard = []
    for promo in promocodes:
        keyboard.append([InlineKeyboardButton(f"{promo[0]} ({promo[1]}₽)", callback_data=f"admin_promo_view_{promo[0]}")])
    keyboard.extend([
        [InlineKeyboardButton("➕ Добавить", callback_data="admin_promo_add")],
        [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
    ])
    return InlineKeyboardMarkup(keyboard)

# 🎮 ОСНОВНЫЕ УТИЛИТЫ
async def get_user_data(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_by_username(username):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT user_id FROM users WHERE username = ?', (username.replace('@', ''),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_top_users():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10') as cursor:
            return await cursor.fetchall()

async def get_top_clans():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT c.clan_id, c.name, c.power, c.level FROM clans c ORDER BY c.power DESC LIMIT 10') as cursor:
            return await cursor.fetchall()

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                        (amount, abs(amount), user_id))
        await db.commit()

async def is_vip(user_id):
    user = await get_user_data(user_id)
    return user and time.time() < user[12]

async def get_vip_multiplier(user_id):
    return 2.0 if await is_vip(user_id) else 1.0

async def is_banned(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT 1 FROM banned WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_clan_data(clan_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM clans WHERE clan_id = ?', (clan_id,)) as cursor:
            return await cursor.fetchone()

# 🛠️ КУЛДАУНЫ (исправлено)
async def set_cooldown(user_id, cooldown_field, cooldown_seconds):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute(f'UPDATE users SET {cooldown_field} = ? WHERE user_id = ?', 
                        (time.time() + cooldown_seconds, user_id))
        await db.commit()

async def can_use_cooldown(user_id, cooldown_index):
    user = await get_user_data(user_id)
    if not user:
        return False
    cooldown_time = user[cooldown_index]  # 3 = mining_cooldown
    return time.time() >= cooldown_time

async def mining_logic(user_id):
    user = await get_user_data(user_id)
    vip_mult = await get_vip_multiplier(user_id)
    pickaxe_bonus = user[16] * 0.5 if user[16] else 0
    
    base_reward = random.randint(50, 150) * vip_mult
    total_reward = int(base_reward * (1 + pickaxe_bonus))
    
    await update_user_balance(user_id, total_reward)
    await set_cooldown(user_id, 'mining_cooldown', 300)
    return total_reward

# МЕНЮ
def main_menu(is_admin=False):
    keyboard = [
        [KeyboardButton("⚔️ Дуэли"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("⛏️ Майнинг"), KeyboardButton("🗺️ Экспедиция")],
        [KeyboardButton("💰 Баланс"), KeyboardButton("👥 Кланы")],
        [KeyboardButton("🎁 Промокод"), KeyboardButton("📊 Статистика")]
    ]
    if is_admin:
        keyboard.append([KeyboardButton("👑 Админ")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_main_menu():
    keyboard = [
        [KeyboardButton("👤 Игроки"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("🎁 Промокоды"), KeyboardButton("⭐ VIP")],
        [KeyboardButton("🔨 Бан/Разбан"), KeyboardButton("🏰 Кланы")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🔙 Главное")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def clan_menu():
    keyboard = [
        [InlineKeyboardButton("🏆 Топ кланов", callback_data="clan_top")],
        [InlineKeyboardButton("🏰 Мой клан", callback_data="clan_info")],
        [InlineKeyboardButton("🔍 Поиск кланов", callback_data="clan_search")],
        [InlineKeyboardButton("👥 Создать клан", callback_data="clan_create")],
        [InlineKeyboardButton("📝 Вступить по ID", callback_data="clan_join_id")],
        [InlineKeyboardButton("⚔️ Босс", callback_data="clan_boss")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def clan_top_menu(clans):
    keyboard = []
    for clan_id, name, power, members, max_members in clans:
        keyboard.append([InlineKeyboardButton(
            f"🏆 [{name}] Сила:{power:,} ({members}/{max_members})", 
            callback_data=f"clan_view_{clan_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 Кланы", callback_data="clan_menu")])
    return InlineKeyboardMarkup(keyboard)

# 🛠️ СОСТОЯНИЯ
def set_user_state(user_id, state, data=None):
    user_states[user_id] = {'state': state, 'data': data or {}}

def get_user_state(user_id):
    return user_states.get(user_id)

def clear_user_state(user_id):
    user_states.pop(user_id, None)

# 🎮 СТАРТ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
        
    user = update.effective_user
    user_id = user.id
    ref_id = None
    
    if len(update.message.text.split()) > 1:
        ref_id = update.message.text.split()[1]
    
    is_admin = user_id == ADMIN_ID
    
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        existing = await cursor.fetchone()
        
        if not existing:
            if ref_id and ref_id.isdigit():
                await db.execute('UPDATE users SET balance = balance + 500 WHERE user_id = ?', (int(ref_id),))
                await db.execute('INSERT INTO users (user_id, username, balance, ref_id) VALUES (?, ?, 1000, ?)', 
                               (user_id, user.username or 'user', int(ref_id)))
            else:
                await db.execute('INSERT INTO users (user_id, username, balance) VALUES (?, ?, 1000)', 
                               (user_id, user.username or 'user'))
            await db.commit()
    
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.mention_html()}!\n💰 Стартовый баланс: <b>1,000₽</b>",
        parse_mode='HTML', reply_markup=main_menu(is_admin)
    )

# 👑 АДМИН ПАНЕЛЬ
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    await update.message.reply_text("👑 **ПОЛНАЯ АДМИН ПАНЕЛЬ**", parse_mode='Markdown', reply_markup=admin_main_menu())

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
        
    top_users = await get_top_users()
    top_clans = await get_top_clans()
    
    users_text = "👥 **ТОП ИГРОКИ:**\n"
    for i, (uid, uname, bal) in enumerate(top_users, 1):
        users_text += f"{i}. @{uname or uid}: {bal:,}₽\n"
    
    clans_text = "\n🏆 **ТОП КЛАНЫ:**\n"
    for i, (cid, cname, cpower, clevel) in enumerate(top_clans, 1):
        clans_text += f"{i}. [{cname}] Ур.{clevel} Сила:{cpower:,}\n"
    
    await update.message.reply_text(users_text + clans_text, parse_mode='Markdown')

# ✅ ОБРАБОТЧИК СООБЩЕНИЙ
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id == ADMIN_ID
    
    if await is_banned(user_id) and not is_admin:
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
    
    text = update.message.text
    state = get_user_state(user_id)
    user_data = await get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("👆 /start", reply_markup=main_menu(is_admin))
        return
    
    # 👑 АДМИН КОМАНДЫ
    if is_admin:
        if text == "👑 Админ":
            await update.message.reply_text("👑 **ПОЛНАЯ АДМИН ПАНЕЛЬ**", parse_mode='Markdown', reply_markup=admin_main_menu())
            return
        
        elif text == "👤 Игроки":
            set_user_state(user_id, 'admin_player_search')
            await update.message.reply_text("🔍 Введите `@username` игрока:")
            return
            
        elif text == "🛒 Магазин":
            items = await admin_get_all_shop_items()
            await update.message.reply_text("🛒 **Управление магазином**", reply_markup=admin_shop_menu(items))
            return
            
        elif text == "🎁 Промокоды":
            promos = await admin_get_all_promocodes()
            await update.message.reply_text("🎁 **Управление промокодами**", reply_markup=admin_promo_menu(promos))
            return
            
        elif text == "📊 Статистика":
            await show_admin_stats(update, context)
            return
            
        elif text == "🔙 Главное":
            clear_user_state(user_id)
            await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu(True))
            return
    
    # ✅ ОСНОВНЫЕ ФУНКЦИИ
    if text == "👥 Кланы":
        await update.message.reply_text("🏰 **КЛАНЫ**", reply_markup=clan_menu())
        return
    
    elif text == "⛏️ Майнинг":
        if await can_use_cooldown(user_id, 3):
            reward = await mining_logic(user_id)
            await update.message.reply_text(f"⛏️ **+{reward:,}₽**\n⏰ 5 мин кулдаун", parse_mode='Markdown', reply_markup=main_menu(is_admin))
        else:
            cooldown_left = int(user_data[3] - time.time())
            await update.message.reply_text(f"⛏️ Кулдаун: {cooldown_left//60}м", reply_markup=main_menu(is_admin))
    
    elif text == "💰 Баланс":
        vip_status = "⭐ VIP" if await is_vip(user_id) else ""
        await update.message.reply_text(f"💰 **{user_data[2]:,}₽** {vip_status}", parse_mode='Markdown', reply_markup=main_menu(is_admin))
    
    else:
        await update.message.reply_text("👆 Выберите кнопку меню", reply_markup=main_menu(is_admin))

# ✅ CALLBACK (ПОЛНЫЙ КЛАНОВЫЙ)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    is_admin = user_id == ADMIN_ID
    
    if data == "main_menu":
        await query.edit_message_text("🏠 Главное меню", reply_markup=main_menu(is_admin))
        return
    
    elif data == "admin_main":
        await query.edit_message_text("👑 Админ панель", reply_markup=admin_main_menu())
        return
    
    # 🏰 КЛАНЫ (ПОЛНАЯ СИСТЕМА)
    elif data == "clan_menu":
        await query.edit_message_text("🏰 **КЛАНЫ**", reply_markup=clan_menu())
    
    elif data == "clan_top":
        clans = await get_all_clans()
        text = "🏆 **ТОП КЛАНОВ:**\n"
        for clan_id, name, power, members, max_members in clans[:10]:
            text += f"**{name}** [{clan_id}] Сила:{power:,} ({members}/{max_members})\n"
        await query.edit_message_text(text, reply_markup=clan_top_menu(clans), parse_mode='Markdown')
    
    elif data.startswith("clan_view_"):
        clan_id = int(data.split('_')[2])
        clan = await get_clan_data(clan_id)
        if clan:
            await query.edit_message_text(
                f"🏰 **[{clan[1]}] [{clan[0]}]**\n"
                f"💪 Сила: {clan[7]:,}\n"
                f"👥 Членов: {clan[4]}/{clan[3]}\n"
                f"💰 Казна: {clan[5]:,}₽\n"
                f"⚔️ Ур: {clan[6]}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Вступить", callback_data=f"clan_join_{clan_id}")],
                    [InlineKeyboardButton("🔙 Топ", callback_data="clan_top")]
                ]),
                parse_mode='Markdown'
            )
    
    elif data.startswith("clan_join_"):
        clan_id = int(data.split('_')[2])
        success, message = await join_clan_by_id(user_id, clan_id)
        await query.edit_message_text(message, parse_mode='Markdown')
    
    elif data == "clan_search":
        clans = await get_all_clans()
        await query.edit_message_text("🔍 **ПОИСК КЛАНОВ:**", reply_markup=clan_top_menu(clans))
    
    elif data == "clan_create":
        set_user_state(user_id, 'clan_create_name')
        await query.message.reply_text("📝 Название клана (макс 15 символов):")
    
    elif data == "clan_join_id":
        set_user_state(user_id, 'clan_join_id')
        await query.message.reply_text("📝 Введите ID клана (число):")
    
    elif data == "clan_info":
        user_clan = await get_user_clan(user_id)
        if user_clan:
            clan = await get_clan_data(user_clan)
            await query.edit_message_text(
                f"🏰 **[{clan[1]}]**\n"
                f"💪 Сила: {clan[7]:,}\n"
                f"👥 {clan[4]}/{clan[3]}\n"
                f"💰 {clan[5]:,}₽",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚔️ Босс", callback_data="clan_boss")],
                    [InlineKeyboardButton("🔙 Кланы", callback_data="clan_menu")]
                ]),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Вы не в клане!", reply_markup=clan_menu())

# ОСНОВНОЙ ЗАПУСК
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 БОТ с ПОЛНЫМИ КЛАНАМИ запускается...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

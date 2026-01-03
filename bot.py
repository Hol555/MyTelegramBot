import logging
import os
import asyncio
import random
import time
import json
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
clan_bosses = {}
daily_missions = {}

async def init_db(application: Application):
    async with aiosqlite.connect('bot.db') as db:
        # USERS
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0, boss_attacks INTEGER DEFAULT 2,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0, vip_until REAL DEFAULT 0,
            sword INTEGER DEFAULT 0, crown INTEGER DEFAULT 0, shield INTEGER DEFAULT 0,
            pickaxe INTEGER DEFAULT 0, helmet INTEGER DEFAULT 0, armor INTEGER DEFAULT 0,
            amulet INTEGER DEFAULT 0, ring INTEGER DEFAULT 0, power INTEGER DEFAULT 10,
            buffs TEXT DEFAULT '{}', debuffs TEXT DEFAULT '{}', last_mission REAL DEFAULT 0
        )''')
        
        # CLANS
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY, name TEXT UNIQUE, leader_id INTEGER,
            description TEXT DEFAULT '', max_members INTEGER DEFAULT 15, current_members INTEGER DEFAULT 1,
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
        
        # PROMOS, BANNED, SHOP, VIP
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
        
        # ИНИЦИАЛИЗАЦИЯ
        await db.executemany("INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES (?, ?, ?)",
            [('WELCOME1000', 1000, 100), ('CLANSTART', 50000, 10), ('MINER2024', 2500, 50), ('LUCKYDAY', 5000, 20)])
        
        shop_items = [
            (1, 'Легендарный меч', 500, '⚔️', '+50% к урону в дуэлях', 'item'),
            (2, 'Королевская корона', 1000, '👑', '+25% ко всем доходам', 'item'),
            (3, 'Абсолютный щит', 750, '🛡️', '+30% защиты в дуэлях', 'item'),
            (4, 'Кристальный амулет', 1200, '💎', '+40% к экспедициям', 'item'),
            (5, 'Золотой кирка', 800, '⛏️', '+100% к майнингу', 'item'),
            (6, 'Серебряный шлем', 600, '⛑️', '+20% защиты', 'item'),
            (7, 'Алмазное кольцо', 1500, '💍', '+50% к дуэлям', 'item'),
            (8, 'Сапфировая броня', 2000, '🛡️', '+60% защиты', 'item'),
            (9, 'Бронзовый сундук', 200, '📦', 'Рандом: 100-500₽ + предметы', 'chest'),
            (10, 'Серебряный сундук', 500, '📦', 'Рандом: 500-2000₽ + редкие', 'chest'),
            (11, 'Золотой сундук', 1500, '📦', 'Рандом: 2000-10000₽ + легендарные', 'chest')
        ]
        
        await db.executemany("INSERT OR IGNORE INTO shop_items (item_id, name, price, emoji, description, type) VALUES (?, ?, ?, ?, ?, ?)", shop_items)
        
        await db.executemany("INSERT OR IGNORE INTO vip_packages (package_id, name, price, duration_days, multiplier, description) VALUES (?, ?, ?, ?, ?, ?)",
            [(1, 'VIP 7 дней', 500, 7, 2.0, '+100% ко всем доходам'),
             (2, 'VIP 30 дней', 1500, 30, 2.5, '+150% ко всем доходам')])
        
        await db.commit()
        logger.info("✅ База данных инициализирована")

# 🛠️ УТИЛИТЫ
async def get_user_data(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_user(user_id, **kwargs):
    async with aiosqlite.connect('bot.db') as db:
        set_clause = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [user_id]
        await db.execute(f'UPDATE users SET {set_clause} WHERE user_id = ?', values)
        await db.commit()

async def get_user_by_username(username):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT user_id FROM users WHERE username = ?', (username.replace('@', ''),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_top_clans():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('''
            SELECT c.clan_id, c.name, c.power, c.level, c.current_members 
            FROM clans c ORDER BY c.power DESC LIMIT 10
        ''') as cursor:
            return await cursor.fetchall()

async def get_all_clans():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('''
            SELECT clan_id, name, power, current_members, max_members 
            FROM clans ORDER BY power DESC LIMIT 20
        ''') as cursor:
            return await cursor.fetchall()

async def get_clan_data(clan_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM clans WHERE clan_id = ?', (clan_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_clan(user_id):
    user = await get_user_data(user_id)
    return user[8] if user else None

async def get_user_clan_role(user_id, clan_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT role FROM clan_members WHERE user_id = ? AND clan_id = ?', (user_id, clan_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def join_clan(user_id, clan_id):
    clan = await get_clan_data(clan_id)
    if not clan or clan[5] >= clan[4]:
        return False, "❌ Клан полный или не существует!"
    
    user_clan = await get_user_clan(user_id)
    if user_clan:
        return False, "❌ Вы уже в клане!"
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE clans SET current_members = current_members + 1 WHERE clan_id = ?', (clan_id,))
        await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, user_id))
        await db.execute('INSERT INTO clan_members (user_id, clan_id) VALUES (?, ?)', (user_id, clan_id))
        await db.commit()
    return True, f"✅ Вступили в **[{(await get_clan_data(clan_id))[1]}]**!"

async def create_clan(user_id, name):
    async with aiosqlite.connect('bot.db') as db:
        clan_id = int(time.time())
        try:
            await db.execute('INSERT INTO clans (clan_id, name, leader_id, current_members) VALUES (?, ?, ?, 1)', 
                           (clan_id, name, user_id))
            await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, user_id))
            await db.execute('INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, "leader")', (user_id, clan_id))
            await db.commit()
            return True, f"🏰 **{name}** создан! ID: `{clan_id}`\n👑 Вы - ЛИДЕР!"
        except:
            return False, "❌ Ошибка создания!"

async def leave_clan(user_id):
    clan_id = await get_user_clan(user_id)
    if not clan_id:
        return False, "❌ Вы не в клане!"
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE clans SET current_members = current_members - 1 WHERE clan_id = ?', (clan_id,))
        await db.execute('UPDATE users SET clan_id = NULL WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM clan_members WHERE user_id = ? AND clan_id = ?', (user_id, clan_id))
        await db.commit()
    return True, "✅ Покинули клан!"

async def is_banned(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT 1 FROM banned WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def ban_user(user_id, reason=""):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT OR REPLACE INTO banned (user_id, reason) VALUES (?, ?)', (user_id, reason))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM banned WHERE user_id = ?', (user_id,))
        await db.commit()

async def use_promo(user_id, code):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT reward, uses, max_uses FROM promos WHERE code = ?', (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
            if not promo or promo[1] >= promo[2]:
                return False, "❌ Неверный или исчерпанный промокод!"
            
            await db.execute('UPDATE promos SET uses = uses + 1 WHERE code = ?', (code.upper(),))
            await db.commit()
        
        await update_user_balance(user_id, promo[0])
        return True, f"✅ Промокод активирован! +{promo[0]:,}₽"

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                        (amount, abs(amount), user_id))
        await db.commit()

async def get_shop_items():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM shop_items ORDER BY item_id') as cursor:
            return await cursor.fetchall()

async def buy_item(user_id, item_id):
    items = await get_shop_items()
    item = next((i for i in items if i[0] == item_id), None)
    if not item:
        return False, "❌ Предмет не найден!"
    
    user = await get_user_data(user_id)
    if user[2] < item[2]:
        return False, f"❌ Недостаточно средств! Нужно {item[2]:,}₽"
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (item[2], user_id))
        
        if item[5] == 'item':
            field_map = {
                'Легендарный меч': 'sword', 'Королевская корона': 'crown', 'Абсолютный щит': 'shield',
                'Кристальный амулет': 'amulet', 'Золотой кирка': 'pickaxe', 'Серебряный шлем': 'helmet',
                'Алмазное кольцо': 'ring', 'Сапфировая броня': 'armor'
            }
            field = field_map.get(item[1])
            if field:
                await db.execute(f'UPDATE users SET {field} = {field} + 1 WHERE user_id = ?', (user_id,))
        
        await db.commit()
    return True, f"✅ Куплено: {item[3]} {item[1]}!"

async def mining_logic(user_id):
    user = await get_user_data(user_id)
    mult = 2.0 if time.time() < user[12] else 1.0
    pickaxe_bonus = user[16] * 0.5
    reward = int(random.randint(50, 150) * mult * (1 + pickaxe_bonus))
    await update_user_balance(user_id, reward)
    await update_user(user_id, mining_cooldown=time.time() + 300)
    return reward

async def expedition_logic(user_id):
    user = await get_user_data(user_id)
    mult = 2.0 if time.time() < user[12] else 1.0
    amulet_bonus = user[19] * 0.4
    reward = int(random.randint(200, 800) * mult * (1 + amulet_bonus))
    await update_user_balance(user_id, reward)
    await update_user(user_id, expedition_cooldown=time.time() + 900)  # 15 мин
    return reward

async def daily_mission(user_id):
    user = await get_user_data(user_id)
    if time.time() < user[24]:
        return False, "⏰ Миссия доступна раз в день!"
    
    rewards = [500, 1000, 2500, 5000]
    reward = random.choice(rewards)
    await update_user_balance(user_id, reward)
    await update_user(user_id, last_mission=time.time() + 86400)
    return True, f"🎁 **ЕЖЕДНЕВНАЯ МИССИЯ!** +{reward:,}₽"

def main_menu(is_admin=False):
    keyboard = [
        [KeyboardButton("⚔️ Дуэли"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("⛏️ Майнинг"), KeyboardButton("🗺️ Экспедиция")],
        [KeyboardButton("💰 Баланс"), KeyboardButton("👥 Кланы")],
        [KeyboardButton("🎁 Промокод"), KeyboardButton("📋 Миссия")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🔙 Главное")]
    ]
    if is_admin:
        keyboard.insert(0, [KeyboardButton("👑 Админ")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 Выдать валюту"), KeyboardButton("👤 Игроки")],
        [KeyboardButton("🛒 Магазин"), KeyboardButton("🎁 Промокоды")],
        [KeyboardButton("⭐ VIP"), KeyboardButton("🔨 Баны")],
        [KeyboardButton("🏰 Кланы"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🔙 Главное")]
    ], resize_keyboard=True)

def clan_member_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏰 Инфо клана", callback_data="clan_info")],
        [InlineKeyboardButton("📊 Статистика", callback_data="clan_stats")],
        [InlineKeyboardButton("👥 Участники", callback_data="clan_members")],
        [InlineKeyboardButton("🛒 Магазин клана", callback_data="clan_shop")],
        [InlineKeyboardButton("🚪 Уйти из клана", callback_data="clan_leave")],
        [InlineKeyboardButton("🔙 Главное", callback_data="main_menu")]
    ])

def clan_leader_menu():
    leader_kb = clan_member_menu().inline_keyboard
    leader_kb.insert(4, [InlineKeyboardButton("⚙️ Управление", callback_data="clan_manage")])
    return InlineKeyboardMarkup(leader_kb)

def shop_menu(items):
    keyboard = []
    for item in items:
        keyboard.append([InlineKeyboardButton(f"{item[3]} {item[1]} ({item[2]}₽)", callback_data=f"shop_buy_{item[0]}")])
    keyboard.extend([
        [InlineKeyboardButton("🔙 Главное", callback_data="main_menu")]
    ])
    return InlineKeyboardMarkup(keyboard)

def set_user_state(user_id, state, data=None):
    user_states[user_id] = {'state': state, 'data': data or {}}

def get_user_state(user_id):
    return user_states.get(user_id)

def clear_user_state(user_id):
    user_states.pop(user_id, None)

# 🎮 СТАРТ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_banned(user_id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
    
    user = update.effective_user
    is_admin = user_id == ADMIN_ID
    
    user_data = await get_user_data(user_id)
    if not user_data:
        await update_user(user_id, username=user.username or 'user', balance=1000)
    
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.mention_html()}!\n💰 Баланс: <b>1,000₽</b>",
        parse_mode='HTML', reply_markup=main_menu(is_admin)
    )

# 👑 АДМИН
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text("👑 **АДМИН ПАНЕЛЬ**", parse_mode='Markdown', reply_markup=admin_menu())

# ✅ ОБРАБОТЧИК СООБЩЕНИЙ
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await is_banned(user_id) and user_id != ADMIN_ID:
        return
    
    text = update.message.text
    state = get_user_state(user_id)
    is_admin = user_id == ADMIN_ID
    user_data = await get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("👆 /start", reply_markup=main_menu(is_admin))
        return
    
    # 🔙 ГЛАВНОЕ МЕНЮ ВЕЗДЕ
    if text == "🔙 Главное":
        clear_user_state(user_id)
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu(is_admin))
        return
    
    # АДМИН
    if is_admin:
        if text == "👑 Админ":
            await admin_panel(update, context)
            return
        
        elif text == "💰 Выдать валюту":
            set_user_state(user_id, 'admin_give_money')
            await update.message.reply_text("👤 Введите @username:")
            return
        
        elif text == "👤 Игроки":
            set_user_state(user_id, 'admin_player_stats')
            await update.message.reply_text("🔍 Введите @username:")
            return
    
    # ОСНОВНЫЕ
    if text == "💰 Баланс":
        vip = "⭐ VIP" if time.time() < user_data[12] else ""
        await update.message.reply_text(f"💰 **{user_data[2]:,}₽** {vip}", parse_mode='Markdown', reply_markup=main_menu(is_admin))
    
    elif text == "⛏️ Майнинг":
        if time.time() >= user_data[3]:
            reward = await mining_logic(user_id)
            await update.message.reply_text(f"⛏️ **+{reward:,}₽**\n⏰ 5 мин", parse_mode='Markdown', reply_markup=main_menu(is_admin))
        else:
            left = int(user_data[3] - time.time())
            await update.message.reply_text(f"⛏️ Кулдаун: {left//60}м", reply_markup=main_menu(is_admin))
    
    elif text == "🗺️ Экспедиция":
        if time.time() >= user_data[4]:
            reward = await expedition_logic(user_id)
            await update.message.reply_text(f"🗺️ **+{reward:,}₽**\n⏰ 15 мин", parse_mode='Markdown', reply_markup=main_menu(is_admin))
        else:
            left = int(user_data[4] - time.time())
            await update.message.reply_text(f"🗺️ Кулдаун: {left//60}м", reply_markup=main_menu(is_admin))
    
    elif text == "🎁 Промокод":
        set_user_state(user_id, 'use_promo')
        await update.message.reply_text("🎁 Введите промокод:")
    
    elif text == "📋 Миссия":
        success, msg = await daily_mission(user_id)
        await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_menu(is_admin))
    
    elif text == "👥 Кланы":
        await update.message.reply_text("🏰 **КЛАНЫ**", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Топ кланов", callback_data="clan_top")],
            [InlineKeyboardButton("🔍 Поиск", callback_data="clan_search")],
            [InlineKeyboardButton("👥 Создать", callback_data="clan_create")],
            [InlineKeyboardButton("📝 Вступить ID", callback_data="clan_join_id")],
            [InlineKeyboardButton("🔙 Главное", callback_data="main_menu")]
        ]))
    
    elif text == "🛒 Магазин":
        items = await get_shop_items()
        await update.message.reply_text("🛒 **МАГАЗИН**", reply_markup=shop_menu(items))
    
    elif state:
        # STATE HANDLING
        if state['state'] == 'use_promo':
            success, msg = await use_promo(user_id, text)
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_menu(is_admin))
            clear_user_state(user_id)
        
        elif state['state'] == 'clan_create':
            success, msg = await create_clan(user_id, text[:15])
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_menu(is_admin))
            clear_user_state(user_id)
        
        elif state['state'] == 'clan_join_id' and text.isdigit():
            success, msg = await join_clan(user_id, int(text))
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=main_menu(is_admin))
            clear_user_state(user_id)
        
        # ADMIN STATES
        elif is_admin:
            if state['state'] == 'admin_give_money':
                target_id = await get_user_by_username(text)
                if target_id:
                    set_user_state(user_id, 'admin_give_amount', {'target': target_id})
                    await update.message.reply_text("💰 Сумма:")
                else:
                    await update.message.reply_text("❌ Игрок не найден!")
            
            elif state['state'] == 'admin_give_amount':
                amount = int(text)
                target = state['data']['target']
                await update_user_balance(target, amount)
                await update.message.reply_text(f"✅ Выдано {amount:,}₽ игроку {target}")
                clear_user_state(user_id)
    
    else:
        await update.message.reply_text("👆 Выберите кнопку", reply_markup=main_menu(is_admin))

# ✅ CALLBACKS
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    is_admin = user_id == ADMIN_ID
    
    if data == "main_menu":
        await query.edit_message_text("🏠 Главное меню", reply_markup=main_menu(is_admin))
        return
    
    # 🏰 КЛАНЫ
    user_clan = await get_user_clan(user_id)
    clan_role = await get_user_clan_role(user_id, user_clan) if user_clan else None
    
    if data == "clan_top":
        clans = await get_all_clans()
        text = "🏆 **ТОП КЛАНОВ:**\n"
        for i, (cid, name, power, mem, maxm) in enumerate(clans[:10], 1):
            text += f"{i}. **{name}** [{cid}] {power:,} ({mem}/{maxm})\n"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📝 Вступить #{clans[0][0]}", callback_data=f"clan_join_{clans[0][0]}")],
            [InlineKeyboardButton("🔍 Поиск", callback_data="clan_search"), InlineKeyboardButton("🔙", callback_data="main_menu")]
        ]), parse_mode='Markdown')
    
    elif data.startswith("clan_join_"):
        clan_id = int(data.split('_')[2])
        success, msg = await join_clan(user_id, clan_id)
        await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif data == "clan_info" and user_clan:
        clan = await get_clan_data(user_clan)
        role_emoji = "👑" if clan_role == "leader" else "👤"
        kb = clan_leader_menu() if clan_role == "leader" else clan_member_menu()
        await query.edit_message_text(
            f"{role_emoji} **[{clan[1]}]** [{clan[0]}]\n"
            f"📝 {clan[2] or 'Описание отсутствует'}\n"
            f"💪 Сила: {clan[7]:,}\n"
            f"👥 {clan[5]}/{clan[4]}\n💰 {clan[6]:,}₽",
            reply_markup=kb, parse_mode='Markdown'
        )
    
    elif data == "clan_leave":
        success, msg = await leave_clan(user_id)
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Главное", callback_data="main_menu")]
        ]))
    
    # 🛒 МАГАЗИН
    elif data.startswith("shop_buy_"):
        item_id = int(data.split('_')[2])
        success, msg = await buy_item(user_id, item_id)
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Еще покупки", callback_data="shop_menu"), InlineKeyboardButton("🔙 Главное", callback_data="main_menu")]
        ]))

if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 СУПЕР БОТ ЗАПУЩЕН!")
    app.run_polling(drop_pending_updates=True)

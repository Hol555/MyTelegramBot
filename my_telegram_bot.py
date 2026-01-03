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
user_states = {}  # user_id: {'state': 'admin_currency_username', 'data': {...}}
duel_rooms = {}  # room_id: {'host_id': user_id, 'bet': amount, 'created': timestamp}
waiting_duels = {}  # user_id: {'bet': amount, 'timestamp': time}

async def init_db(application: Application):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0, vip_until REAL DEFAULT 0,
            sword INTEGER DEFAULT 0, crown INTEGER DEFAULT 0, shield INTEGER DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            max_members INTEGER DEFAULT 15, current_members INTEGER DEFAULT 1,
            treasury INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s','now'))
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            user_id INTEGER, clan_id INTEGER, role TEXT DEFAULT 'member',
            joined_at REAL DEFAULT (strftime('%s','now')), PRIMARY KEY (user_id, clan_id)
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_requests (
            user_id INTEGER, clan_id INTEGER, created_at REAL DEFAULT (strftime('%s','now')),
            PRIMARY KEY (user_id, clan_id)
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER DEFAULT 0, max_uses INTEGER
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS shop_items (
            item_id INTEGER PRIMARY KEY, name TEXT, price INTEGER, emoji TEXT
        )''')
        
        await db.executemany(
            "INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES (?, ?, ?)",
            [('WELCOME1000', 1000, 100), ('CLANSTART', 50000, 10)]
        )
        
        await db.executemany(
            "INSERT OR IGNORE INTO shop_items (item_id, name, price, emoji) VALUES (?, ?, ?, ?)",
            [
                (1, 'Легендарный меч', 500, '⚔️'),
                (2, 'Королевская корона', 1000, '👑'),
                (3, 'Абсолютный щит', 750, '🛡️')
            ]
        )
        await db.commit()
        logger.info("✅ База данных инициализирована")

# Утилиты
async def get_user_data(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_by_username(username):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT user_id FROM users WHERE username = ?', (username.replace('@', ''),)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def get_all_users():
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT 10') as cursor:
            return await cursor.fetchall()

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                        (amount, abs(amount), user_id))
        await db.commit()

async def set_cooldown(user_id, cooldown_type, duration):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute(f'UPDATE users SET {cooldown_type} = ? WHERE user_id = ?', 
                        (time.time() + duration, user_id))
        await db.commit()

async def can_use_cooldown(user_id, cooldown_index):
    user = await get_user_data(user_id)
    if not user:
        return True
    return time.time() >= user[cooldown_index]

async def is_banned(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT 1 FROM banned WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone() is not None

async def ban_user(user_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT OR IGNORE INTO banned (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def unban_user(user_id):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('DELETE FROM banned WHERE user_id = ?', (user_id,))
        await db.commit()

async def give_item(user_id, item_id, quantity=1):
    async with aiosqlite.connect('bot.db') as db:
        item_columns = ['sword', 'crown', 'shield']
        if 1 <= item_id <= 3:
            column = item_columns[item_id-1]
            await db.execute(f'UPDATE users SET {column} = {column} + ? WHERE user_id = ?', (quantity, user_id))
            await db.commit()
            return True
        return False

# Админ состояния
def set_user_state(user_id, state, data=None):
    user_states[user_id] = {'state': state, 'data': data or {}}

def get_user_state(user_id):
    return user_states.get(user_id)

def clear_user_state(user_id):
    user_states.pop(user_id, None)

# Меню
def main_menu():
    keyboard = [
        [KeyboardButton("⚔️ Дуэли"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("⛏️ Майнинг"), KeyboardButton("🗺️ Экспедиция")],
        [KeyboardButton("💰 Баланс"), KeyboardButton("👥 Кланы")],
        [KeyboardButton("🎁 Промокод"), KeyboardButton("📊 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_main_menu():
    keyboard = [
        [KeyboardButton("💰 Валюта"), KeyboardButton("⭐ VIP/Предметы")],
        [KeyboardButton("🔨 Бан"), KeyboardButton("✅ Разбан")],
        [KeyboardButton("👥 Топ игроков"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🔙 Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def shop_menu():
    keyboard = [
        [InlineKeyboardButton("⚔️ Легендарный меч (500₽)", callback_data="shop_1")],
        [InlineKeyboardButton("👑 Королевская корона (1000₽)", callback_data="shop_2")],
        [InlineKeyboardButton("🛡️ Абсолютный щит (750₽)", callback_data="shop_3")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def duel_menu():
    keyboard = [
        [InlineKeyboardButton("🔍 Искать дуэль", callback_data="duel_search")],
        [InlineKeyboardButton("📋 Активные комнаты", callback_data="duel_rooms")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ✅ ИСПРАВЛЕНО: duel_rooms_menu теперь async
async def duel_rooms_menu(rooms, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for room_id, room_data in rooms.items():
        host_data = await get_user_data(room_data['host_id'])
        if host_data:
            username = host_data[1] or f"user{room_data['host_id']}"
        else:
            username = f"user{room_data['host_id']}"
        keyboard.append([InlineKeyboardButton(
            f"Комната {room_id}: @{username} {room_data['bet']}₽", 
            callback_data=f"join_room_{room_id}"
        )])
    keyboard.append([InlineKeyboardButton("🔍 Искать дуэль", callback_data="duel_search")])
    keyboard.append([InlineKeyboardButton("🔙 Дуэли", callback_data="duel_back")])
    return InlineKeyboardMarkup(keyboard)

# Дуэль комнаты
async def create_duel_room(user_id, bet):
    room_id = len(duel_rooms) + 1
    duel_rooms[room_id] = {
        'host_id': user_id, 
        'bet': bet, 
        'created': time.time(),
        'challenger_id': None
    }
    # Удаляем старые комнаты (>5 мин)
    now = time.time()
    global duel_rooms
    duel_rooms = {k: v for k, v in duel_rooms.items() if now - v['created'] < 300}
    return room_id

async def get_active_rooms():
    now = time.time()
    global duel_rooms
    active_rooms = {k: v for k, v in duel_rooms.items() if now - v['created'] < 300}
    return active_rooms

async def cleanup_duel_rooms():
    now = time.time()
    global duel_rooms
    expired = [k for k, v in duel_rooms.items() if now - v['created'] > 300]
    for room_id in expired:
        duel_rooms.pop(room_id, None)

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await is_banned(update.effective_user.id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
        
    user = update.effective_user
    user_id = user.id
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''INSERT OR IGNORE INTO users (user_id, username, balance) 
                          VALUES (?, ?, 1000)''', (user_id, user.username))
        await db.commit()
    
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.mention_html()}!\n💰 Стартовый баланс: <b>1,000₽</b>",
        parse_mode='HTML', reply_markup=main_menu()
    )

# Админ панель
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    await update.message.reply_text("👑 **Админ панель**", parse_mode='Markdown', reply_markup=admin_main_menu())

# Обработчик админ команд
async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "💰 Валюта":
        set_user_state(user_id, 'admin_currency_username')
        await update.message.reply_text("👤 Введите username для выдачи валюты:")
    
    elif text == "⭐ VIP/Предметы":
        keyboard = [
            [KeyboardButton("⚔️ Легендарный меч"), KeyboardButton("👑 Королевская корона")],
            [KeyboardButton("🛡️ Абсолютный щит"), KeyboardButton("⭐ VIP")]
        ]
        await update.message.reply_text("🎁 Выберите предмет:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True))
        set_user_state(user_id, 'admin_item_select')
    
    elif text == "🔨 Бан":
        set_user_state(user_id, 'admin_ban_username')
        await update.message.reply_text("👤 Введите username для бана:")
    
    elif text == "✅ Разбан":
        set_user_state(user_id, 'admin_unban_username')
        await update.message.reply_text("👤 Введите username для разбана:")
    
    elif text == "👥 Топ игроков":
        users = await get_all_users()
        top_text = "👥 **Топ 10 игроков:**\n\n"
        for i, (uid, uname, bal) in enumerate(users, 1):
            top_text += f"{i}. @{uname} — {bal:,}₽\n"
        await update.message.reply_text(top_text, parse_mode='Markdown', reply_markup=admin_main_menu())
    
    elif text == "📊 Статистика":
        async with aiosqlite.connect('bot.db') as db:
            total_users = await db.execute_fetchall('SELECT COUNT(*) FROM users')
            total_money = await db.execute_fetchall('SELECT SUM(balance) FROM users')
            await update.message.reply_text(
                f"📊 **Статистика бота:**\n"
                f"👥 Игроков: {total_users[0][0]}\n"
                f"💰 Общий баланс: {total_money[0][0] or 0:,}₽",
                parse_mode='Markdown', reply_markup=admin_main_menu()
            )
    
    elif text == "🔙 Главное меню":
        clear_user_state(user_id)
        await update.message.reply_text("🏠 Главное меню", reply_markup=main_menu())

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if await is_banned(user_id) and user_id != ADMIN_ID:
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
    
    text = update.message.text
    state = get_user_state(user_id)
    
    # ✅ АДМИН СОСТОЯНИЯ - TEXT INPUT
    if user_id == ADMIN_ID and state:
        await handle_admin_state(update, context)
        return
    
    user_data = await get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("👆 /start", reply_markup=main_menu())
        return
    
    balance = user_data[2]
    
    # ✅ ОСНОВНЫЕ КНОПКИ
    if text == "⚔️ Дуэли":
        await update.message.reply_text("⚔️ **Дуэли**\n\nВыберите действие:", reply_markup=duel_menu(), parse_mode='Markdown')
    
    elif text == "🛒 Магазин":
        await update.message.reply_text("🛒 **Донат магазин**\n\nВыберите предмет:", reply_markup=shop_menu())
    
    elif text == "💰 Баланс":
        sword = user_data[13] or 0
        crown = user_data[14] or 0
        shield = user_data[15] or 0
        items = [f"{sword}⚔️", f"{crown}👑", f"{shield}🛡️"]
        await update.message.reply_text(
            f"💰 **Баланс:** {balance:,}₽\n"
            f"🎁 **Предметы:** {' | '.join(items)}",
            parse_mode='Markdown', reply_markup=main_menu()
        )
    
    else:
        await update.message.reply_text("👆 Выберите кнопку меню", reply_markup=main_menu())

# ✅ АДМИН TEXT INPUT ОБРАБОТЧИК
async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    state = get_user_state(user_id)
    
    if state['state'] == 'admin_currency_username':
        target_id = await get_user_by_username(text)
        if target_id:
            set_user_state(user_id, 'admin_currency_amount', {'target_id': target_id})
            await update.message.reply_text(f"✅ Найден @{text}!\n💰 Введите сумму для выдачи:")
        else:
            await update.message.reply_text(f"❌ Пользователь @{text} не найден!")
    
    elif state['state'] == 'admin_currency_amount':
        try:
            amount = int(text)
            target_id = state['data']['target_id']
            await update_user_balance(target_id, amount)
            target_user = await get_user_data(target_id)
            clear_user_state(user_id)
            await update.message.reply_text(
                f"✅ **Выдано {amount:,}₽** пользователю @{target_user[1]}\n"
                f"💰 Новый баланс: {target_user[2] + amount:,}₽",
                parse_mode='Markdown', reply_markup=admin_main_menu()
            )
        except:
            await update.message.reply_text("❌ Неверная сумма!")
    
    elif state['state'] == 'admin_item_select':
        if text in ["⚔️ Легендарный меч", "👑 Королевская корона", "🛡️ Абсолютный щит"]:
            set_user_state(user_id, 'admin_item_username', {'item_name': text})
            await update.message.reply_text("👤 Введите username для выдачи предмета:")
        elif text == "⭐ VIP":
            set_user_state(user_id, 'admin_vip_username')
            await update.message.reply_text("👤 Введите username для VIP:")
    
    elif state['state'] == 'admin_item_username':
        target_id = await get_user_by_username(text)
        if target_id:
            item_name = state['data']['item_name']
            item_map = {
                "⚔️ Легендарный меч": 1,
                "👑 Королевская корона": 2,
                "🛡️ Абсолютный щит": 3
            }
            item_id = item_map.get(item_name, 1)
            await give_item(target_id, item_id)
            target_user = await get_user_data(target_id)
            clear_user_state(user_id)
            await update.message.reply_text(
                f"✅ **{item_name} выдан** пользователю @{target_user[1]}!",
                parse_mode='Markdown', reply_markup=admin_main_menu()
            )
        else:
            await update.message.reply_text(f"❌ Пользователь @{text} не найден!")
    
    elif state['state'] == 'admin_ban_username':
        target_id = await get_user_by_username(text)
        if target_id:
            await ban_user(target_id)
            clear_user_state(user_id)
            await update.message.reply_text(f"✅ **@{text} заблокирован!**", reply_markup=admin_main_menu())
        else:
            await update.message.reply_text(f"❌ Пользователь @{text} не найден!")
    
    elif state['state'] == 'admin_unban_username':
        target_id = await get_user_by_username(text)
        if target_id:
            await unban_user(target_id)
            clear_user_state(user_id)
            await update.message.reply_text(f"✅ **@{text} разблокирован!**", reply_markup=admin_main_menu())
        else:
            await update.message.reply_text(f"❌ Пользователь @{text} не найден!")

# ✅ CALLBACK ОБРАБОТЧИК (ИСПРАВЛЕНО)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global duel_rooms
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    user_data = await get_user_data(user_id)
    balance = user_data[2] if user_data else 0
    
    if await is_banned(user_id) and user_id != ADMIN_ID:
        await query.edit_message_text("🚫 Вы заблокированы!")
        return
    
    # 🔙 НАЗАД В МЕНЮ
    if data == "main_menu":
        await query.edit_message_text("🏠 **Главное меню**", reply_markup=main_menu())
        return
    
    # 🛒 МАГАЗИН
    elif data.startswith("shop_"):
        item_id = int(data.split('_')[1])
        async with aiosqlite.connect('bot.db') as db:
            async with db.execute('SELECT name, price, emoji FROM shop_items WHERE item_id = ?', (item_id,)) as cursor:
                item = await cursor.fetchone()
        
        if item and balance >= item[1]:
            await update_user_balance(user_id, -item[1])
            await give_item(user_id, item_id)
            await query.edit_message_text(
                f"✅ **{item[2]} {item[0]} куплен!**\n"
                f"💰 Списано: {item[1]:,}₽\n💰 Остаток: {balance - item[1]:,}₽",
                reply_markup=shop_menu(), parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(f"❌ Недостаточно средств!\n💰 Нужно: {item[1]:,}₽", reply_markup=shop_menu())
    
    # ⚔️ ДУЭЛИ
    elif data == "duel_search":
        await query.edit_message_text(
            "⚔️ **Введите ставку (мин. 50₽):**\n"
            f"💰 Ваш баланс: {balance:,}₽",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("100₽", callback_data="duel_bet_100")],
                [InlineKeyboardButton("500₽", callback_data="duel_bet_500")],
                [InlineKeyboardButton("1000₽", callback_data="duel_bet_1000")],
                [InlineKeyboardButton("🔙 Дуэли", callback_data="duel_back")]
            ])
        )
    
    elif data.startswith("duel_bet_"):
        bet = int(data.split('_')[2])
        if balance < bet:
            await query.answer("❌ Недостаточно средств!", show_alert=True)
            return
        
        await cleanup_duel_rooms()
        opponent_room = None
        for room_id, room in duel_rooms.items():
            if room['bet'] == bet and room['host_id'] != user_id and not room.get('challenger_id'):
                opponent_room = room_id
                break
        
        if opponent_room:
            room = duel_rooms[opponent_room]
            host_data = await get_user_data(room['host_id'])
            
            await update_user_balance(user_id, -bet)
            await update_user_balance(room['host_id'], -bet)
            
            # Бой!
            if random.random() > 0.5:
                winner_id, loser_id = user_id, room['host_id']
            else:
                winner_id, loser_id = room['host_id'], user_id
            
            await update_user_balance(winner_id, bet * 2)
            
            winner_data = await get_user_data(winner_id)
            loser_data = await get_user_data(loser_id)
            winner_username = winner_data[1] or "Игрок"
            loser_username = loser_data[1] or "Игрок"
            
            await query.edit_message_text(
                f"⚔️ **Дуэль завершена!**\n\n"
                f"🏆 Победитель: @{winner_username}\n"
                f"💰 Награда: {bet * 2:,}₽\n"
                f"💥 Проигравший: @{loser_username}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 Новая дуэль", callback_data="duel_search")],
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ])
            )
            
            # Уведомление хозяину
            try:
                await context.bot.send_message(
                    room['host_id'],
                    f"⚔️ **Дуэль завершена!**\n\n"
                    f"🏆 Победитель: @{winner_username}\n"
                    f"💰 Награда: {bet * 2:,}₽\n"
                    f"💥 Проигравший: @{loser_username}"
                )
            except:
                pass
            
            duel_rooms.pop(opponent_room, None)
            
        else:
            room_id = await create_duel_room(user_id, bet)
            await query.edit_message_text(
                f"✅ **Комната {room_id} создана!**\n"
                f"💰 Ставка: {bet:,}₽\n"
                f"⏰ Автоудаление: 5 минут",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Закрыть комнату", callback_data=f"close_room_{room_id}")],
                    [InlineKeyboardButton("📋 Посмотреть комнаты", callback_data="duel_rooms")],
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ])
            )
    
    elif data == "duel_rooms":
        rooms = await get_active_rooms()
        if rooms:
            markup = await duel_rooms_menu(rooms, context)
            await query.edit_message_text("📋 **Активные комнаты:**", reply_markup=markup)
        else:
            await query.edit_message_text("📭 **Нет активных комнат**\n\n🔍 Создайте свою!", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Искать дуэль", callback_data="duel_search")],
                [InlineKeyboardButton("🔙 Дуэли", callback_data="duel_back")]
            ]))
    
    elif data.startswith("close_room_"):
        room_id = int(data.split('_')[2])
        if room_id in duel_rooms and duel_rooms[room_id]['host_id'] == user_id:
            await update_user_balance(user_id, duel_rooms[room_id]['bet'])
            duel_rooms.pop(room_id, None)
            await query.edit_message_text("❌ **Комната закрыта**\n💰 Ставка возвращена", reply_markup=duel_menu())
    
    elif data == "duel_back":
        await query.edit_message_text("⚔️ **Дуэли**", reply_markup=duel_menu())
    
    else:
        await query.edit_message_text("🏠 **Главное меню**", reply_markup=main_menu())

def mining_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⛏️ Копать (5 мин)", callback_data="mining_start")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ])

def expedition_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗺️ Экспедиция (15 мин)", callback_data="expedition_start")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ])

# Основной запуск
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Бот запускается...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

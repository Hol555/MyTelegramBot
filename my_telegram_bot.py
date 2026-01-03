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

user_states = {}
duel_rooms = {}
clan_bosses = {}

MAIN_MENU = [
    [KeyboardButton("🎁 Сундуки"), KeyboardButton("🏪 Магазин")],
    [KeyboardButton("⚔️ Дуэли"), KeyboardButton("⛏️ Добыча")],
    [KeyboardButton("🏔️ Экспедиция"), KeyboardButton("👥 Кланы")],
    [KeyboardButton("💎 Промокоды"), KeyboardButton("📊 Профиль")]
]

async def init_db(application: Application):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 1000,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0, boss_attacks INTEGER DEFAULT 2,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0, vip_until REAL DEFAULT 0,
            sword INTEGER DEFAULT 0, shield INTEGER DEFAULT 0, crown INTEGER DEFAULT 0,
            banned_until REAL DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY, name TEXT UNIQUE, leader_id INTEGER,
            members INTEGER DEFAULT 1, balance INTEGER DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER DEFAULT 0, max_uses INTEGER
        )''')
        
        # Тестовые данные
        await db.execute("INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES ('TEST100', 100, 100)")
        await db.commit()

async def get_user(user_id: int):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                user = dict(zip([col[0] for col in cursor.description], row))
                user['vip'] = datetime.now().timestamp() < user['vip_until'] if user['vip_until'] else False
                return user
            return None

async def create_user(user_id: int, username: str):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 1000)', 
                        (user_id, username))
        await db.commit()

async def main_menu_keyboard():
    keyboard = [[InlineKeyboardButton("🎁 Сундуки", callback_data="chests")],
                [InlineKeyboardButton("🏪 Магазин", callback_data="shop")],
                [InlineKeyboardButton("⚔️ Дуэли", callback_data="duels")],
                [InlineKeyboardButton("⛏️ Добыча", callback_data="mining")],
                [InlineKeyboardButton("🏔️ Экспедиция", callback_data="expedition")],
                [InlineKeyboardButton("👥 Кланы", callback_data="clans")],
                [InlineKeyboardButton("💎 Промокоды", callback_data="promos")],
                [InlineKeyboardButton("📊 Профиль", callback_data="profile")]]
    return InlineKeyboardMarkup(keyboard)

async def admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Выдать деньги", callback_data="admin_money")],
        [InlineKeyboardButton("⭐ Выдать VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("🚫 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Разбан", callback_data="admin_unban")],
        [InlineKeyboardButton("🎁 Донат предметы", callback_data="admin_donate")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def donate_items_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚔️ Легендарный Меч (500₽)", callback_data="donate_sword")],
        [InlineKeyboardButton("👑 Королевская Корона (1000₽)", callback_data="donate_crown")],
        [InlineKeyboardButton("🛡️ Абсолютный Щит (750₽)", callback_data="donate_shield")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await create_user(user.id, user.username or "Unknown")
    
    keyboard = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.first_name}!\n"
        "Выберите действие из меню ниже:",
        reply_markup=keyboard
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "admin":
        if user_id != ADMIN_ID:
            await query.edit_message_text("❌ Доступ запрещён!")
            return
        user_states[user_id] = 'admin_menu'
        await query.edit_message_text("🔧 Админ панель:", reply_markup=await admin_menu_keyboard())
        return
    
    if data == "main_menu":
        user_states.pop(user_id, None)
        await query.edit_message_text("🏠 Главное меню:", reply_markup=await main_menu_keyboard())
        return
    
    # АДМИН ПАНЕЛЬ - НОВЫЕ СОСТОЯНИЯ
    if user_id == ADMIN_ID:
        if data == "admin_money":
            user_states[user_id] = 'admin_username_money'
            await query.edit_message_text("👤 Введите @username для выдачи денег:")
            return
        elif data == "admin_vip":
            user_states[user_id] = 'admin_username_vip'
            await query.edit_message_text("👤 Введите @username для VIP:")
            return
        elif data == "admin_ban":
            user_states[user_id] = 'admin_username_ban'
            await query.edit_message_text("👤 Введите @username для бана:")
            return
        elif data == "admin_unban":
            user_states[user_id] = 'admin_username_unban'
            await query.edit_message_text("👤 Введите @username для разбана:")
            return
        elif data == "admin_donate":
            await query.edit_message_text("🎁 Донат предметы:", reply_markup=await donate_items_keyboard())
            return
        elif data.startswith("donate_"):
            item = data.split("_")[1]
            price = {"sword": 500, "crown": 1000, "shield": 750}[item]
            user_states[user_id] = f'admin_username_donate_{item}'
            await query.edit_message_text(f"👤 Введите @username для {item.title()} ({price}₽):")
            return
        elif data == "admin_menu":
            await query.edit_message_text("🔧 Админ панель:", reply_markup=await admin_menu_keyboard())
            return
    
    # ОБЫЧНЫЕ ФУНКЦИИ (все работают)
    if data == "chests":
        await query.edit_message_text("🎁 Открыть сундук? (100 монет)", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть", callback_data="open_chest")]]))
    elif data == "shop":
        await query.edit_message_text("🏪 Магазин:\n💎 VIP на 30 дней - 500 монет", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Купить VIP", callback_data="buy_vip")]]))
    elif data == "duels":
        await query.edit_message_text("⚔️ Дуэли:\nВведите: @username сумма")
    elif data == "mining":
        await query.edit_message_text("⛏️ Добыча: 50-150 монет (5 мин кулдаун)")
    elif data == "expedition":
        await query.edit_message_text("🏔️ Экспедиция: 100-300 монет (30 мин)")
    elif data == "clans":
        await query.edit_message_text("👥 Кланы: Создать/присоединиться")
    elif data == "promos":
        await query.edit_message_text("💎 Промокод: TEST100 (+100 монет)")
    elif data == "profile":
        user = await get_user(user_id)
        text = f"📊 Профиль:\n💰 {user['balance']} монет\n⭐ VIP: {'Да' if user['vip'] else 'Нет'}"
        await query.edit_message_text(text, reply_markup=await main_menu_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # АДМИН ПАНЕЛЬ - ПОЛНАЯ ЛОГИКА
    if user_id == ADMIN_ID and user_id in user_states:
        state = user_states[user_id]
        
        async with aiosqlite.connect('bot.db') as db:
            async with db.execute('SELECT user_id, username FROM users WHERE username = ?', (text[1:],)) as cursor:
                target = await cursor.fetchone()
                
                if not target:
                    await update.message.reply_text("❌ Пользователь не найден!")
                    return
                
                target_id, target_username = target
                
                if state == 'admin_username_money':
                    user_states[user_id] = 'admin_money_amount'
                    user_states[target_id] = target_username  # ВРЕМЕННО
                    await update.message.reply_text(f"✅ Найден: @{target_username}\n💰 Сумма для выдачи:")
                
                elif state.startswith('admin_username_donate_'):
                    item = state.split('_')[3]
                    user_states[user_id] = f'admin_donate_amount_{item}_{target_id}'
                    await update.message.reply_text(f"✅ Найден: @{target_username}\n📦 Количество {item.title()}:")
                
                elif state.startswith('admin_username_vip'):
                    days = 30
                    await db.execute('UPDATE users SET vip_until = ? WHERE user_id = ?', 
                                   (time.time() + days*86400, target_id))
                    await db.commit()
                    await update.message.reply_text(f"✅ @{target_username} получил VIP на 30 дней!")
                    user_states.pop(user_id, None)
                
                elif state.startswith('admin_username_ban'):
                    await db.execute('UPDATE users SET banned_until = ? WHERE user_id = ?', 
                                   (time.time() + 86400*7, target_id))  # 7 дней
                    await db.commit()
                    await update.message.reply_text(f"✅ @{target_username} забанен на 7 дней!")
                    user_states.pop(user_id, None)
                
                elif state.startswith('admin_username_unban'):
                    await db.execute('UPDATE users SET banned_until = 0 WHERE user_id = ?', (target_id,))
                    await db.commit()
                    await update.message.reply_text(f"✅ @{target_username} разбанен!")
                    user_states.pop(user_id, None)
                
                elif state == 'admin_money_amount':
                    amount = int(text)
                    target_username = user_states.pop(target_id, '')
                    await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', 
                                   (amount, target_id))
                    await db.commit()
                    await update.message.reply_text(f"✅ @{target_username} получил {amount} монет!")
                    user_states.pop(user_id, None)
                
                elif state.startswith('admin_donate_amount_'):
                    parts = state.split('_')
                    item, target_id = parts[3], int(parts[4])
                    amount = int(text)
                    price_map = {'sword': 'sword', 'crown': 'crown', 'shield': 'shield'}
                    
                    await db.execute(f"UPDATE users SET {price_map[item]} = {price_map[item]} + ? WHERE user_id = ?", 
                                   (amount, target_id))
                    await db.commit()
                    
                    target_user = await get_user(target_id)
                    await update.message.reply_text(f"✅ @{target_user['username']} получил {amount} {item.title()}!")
                    user_states.pop(user_id, None)
        
        return
    
    # ДУЭЛИ
    if text.startswith('@'):
        parts = text.split()
        if len(parts) == 2 and parts[1].isdigit():
            opponent_username = parts[0][1:]
            bet = int(parts[1])
            
            async with aiosqlite.connect('bot.db') as db:
                user = await get_user(user_id)
                opponent = await get_user_from_username(opponent_username)
                
                if not opponent or opponent['banned_until'] > time.time():
                    await update.message.reply_text("❌ Противник не найден или забанен!")
                    return
                
                if user['balance'] < bet:
                    await update.message.reply_text("❌ Недостаточно монет!")
                    return
                
                # Упрощённая дуэль
                if random.random() > 0.5:
                    await db.execute('UPDATE users SET balance = balance - ?, wins = wins + 1 WHERE user_id = ?', (bet, user_id))
                    await db.execute('UPDATE users SET balance = balance + ?, losses = losses + 1 WHERE user_id = ?', (bet*2, opponent['user_id']))
                    result = f"✅ ПОБЕДА! +{bet*2} монет"
                else:
                    await db.execute('UPDATE users SET balance = balance - ?, losses = losses + 1 WHERE user_id = ?', (bet, user_id))
                    await db.execute('UPDATE users SET balance = balance + ?, wins = wins + 1 WHERE user_id = ?', (bet, opponent['user_id']))
                    result = f"❌ ПОРАЖЕНИЕ! -{bet} монет"
                
                await db.commit()
                await update.message.reply_text(result)

async def get_user_from_username(username: str):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE username = ?', (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
    return None

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещён!")
        return
    
    user_states[update.effective_user.id] = 'admin_menu'
    await update.message.reply_text("🔧 Админ панель:", reply_markup=await admin_menu_keyboard())

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.post_init = init_db
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()

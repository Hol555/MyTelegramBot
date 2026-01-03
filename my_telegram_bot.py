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

async def init_db(application: Application):
    """Инициализация БД с правильной сигнатурой для post_init"""
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0
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
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_bosses (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER, boss_level INTEGER,
            hp INTEGER, max_hp INTEGER, damage_dealt TEXT, participants TEXT,
            started_at REAL, status TEXT DEFAULT 'waiting', reward_pool INTEGER DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER DEFAULT 0, max_uses INTEGER
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS donate_items (
            user_id INTEGER PRIMARY KEY, sword INTEGER DEFAULT 0, crown INTEGER DEFAULT 0, shield INTEGER DEFAULT 0
        )''')
        
        # Инициализация промокодов
        await db.executemany(
            "INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES (?, ?, ?)",
            [('WELCOME1000', 1000, 100), ('CLANSTART', 50000, 10)]
        )
        
        await db.commit()
        logger.info("✅ База данных инициализирована")

# Утилиты БД
async def get_user_data(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

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

async def can_use_cooldown(user_id, cooldown_type):
    user = await get_user_data(user_id)
    if not user:
        return True
    return time.time() >= getattr(user, cooldown_type.replace('_', '') or 0)

# Рефералы
async def get_ref_link(bot_username, user_id):
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

async def process_ref(user_id, args):
    if args and args[0] and args[0].startswith('ref_'):
        try:
            ref_id = int(args[0].split('_')[1])
            async with aiosqlite.connect('bot.db') as db:
                await db.execute('UPDATE users SET ref_id = ? WHERE user_id = ? AND ref_id IS NULL', 
                               (ref_id, user_id))
                await db.commit()
            await update_user_balance(ref_id, 500)
            return True
        except:
            pass
    return False

# Кланы
async def create_clan(leader_id, clan_name):
    async with aiosqlite.connect('bot.db') as db:
        try:
            cursor = await db.execute('INSERT INTO clans (name, leader_id) VALUES (?, ?)', 
                                    (clan_name, leader_id))
            clan_id = cursor.lastrowid
            await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, leader_id))
            await db.execute('INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, "leader")', 
                           (leader_id, clan_id))
            await db.commit()
            return clan_id
        except:
            return None

async def get_clan(clan_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM clans WHERE clan_id = ?', (clan_id,)) as cursor:
            return await cursor.fetchone()

# Меню
def main_menu():
    keyboard = [
        [KeyboardButton("⚔️ Дуэли"), KeyboardButton("⛏️ Майнинг")],
        [KeyboardButton("🗺️ Экспедиция"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("👥 Кланы"), KeyboardButton("🎁 Промокод")],
        [KeyboardButton("⭐ Донат"), KeyboardButton("📊 Статистика")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    ref_processed = await process_ref(user_id, context.args)
    ref_bonus = " +500₽ рефералу!" if ref_processed else ""
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''INSERT OR IGNORE INTO users (user_id, username, balance) 
                          VALUES (?, ?, 1000)''', (user_id, user.username))
        await db.commit()
    
    bot_username = (await context.bot.get_me()).username
    ref_link = await get_ref_link(bot_username, user_id)
    
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.mention_html()}!\n"
        f"💰 Стартовый баланс: <b>1,000</b>{ref_bonus}\n\n"
        f"🔗 Ваша реф. ссылка:\n<code>{ref_link}</code>\n\n"
        f"👆 Используйте кнопки меню!",
        parse_mode='HTML', reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    user_data = await get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("👆 /start", reply_markup=main_menu())
        return
    
    balance = user_data[2]
    
    if text == "💰 Баланс":
        clan = await get_clan(user_data[8]) if user_data[8] else None
        clan_info = f"🏛️ {clan[1]} (Lvl {clan[6]})" if clan else "❌ Нет клана"
        
        await update.message.reply_text(
            f"💰 <b>{balance:,}</b>\n"
            f"📈 Заработано: <b>{user_data[10]:,}</b>\n"
            f"{clan_info}",
            parse_mode='HTML', reply_markup=main_menu()
        )
    
    elif text == "⛏️ Майнинг":
        if await can_use_cooldown(user_id, 3):  # mining_cooldown
            reward = random.randint(50, 150)
            await update_user_balance(user_id, reward)
            await set_cooldown(user_id, 'mining_cooldown', 300)
            await update.message.reply_text(f"⛏️ +{reward:,} 💰", reply_markup=main_menu())
        else:
            remaining = int(user_data[3] - time.time())
            m, s = divmod(remaining, 60)
            await update.message.reply_text(f"⏳ {m}:{s:02d}", reply_markup=main_menu())
    
    elif text == "🗺️ Экспедиция":
        if await can_use_cooldown(user_id, 4):  # expedition_cooldown
            reward = random.randint(200, 500)
            await update_user_balance(user_id, reward)
            await set_cooldown(user_id, 'expedition_cooldown', 900)
            await update.message.reply_text(f"🗺️ +{reward:,} 💰", reply_markup=main_menu())
        else:
            remaining = int(user_data[4] - time.time())
            m, s = divmod(remaining, 60)
            await update.message.reply_text(f"⏳ {m}:{s:02d}", reply_markup=main_menu())
    
    elif text == "👥 Кланы":
        keyboard = [
            [InlineKeyboardButton("📋 Мой клан", callback_data="clan_my")],
            [InlineKeyboardButton("➕ Создать (100k)", callback_data="clan_create")],
            [InlineKeyboardButton("🔍 Поиск", callback_data="clan_search")],
            [InlineKeyboardButton("👤 Управление", callback_data="clan_manage")]
        ]
        await update.message.reply_text("🏛️ **Кланы**", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🎁 Промокод":
        context.user_data['awaiting_promo'] = user_id
        keyboard = [[InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]]
        await update.message.reply_text(
            "🎫 **Введите промокод:**\n\n`WELCOME1000` - 1,000₽\n`CLANSTART` - 50,000₽",
            parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif text.startswith("вступить в клан"):
        try:
            clan_id = int(text.split()[-1])
            clan = await get_clan(clan_id)
            if clan and clan[4] < clan[3]:
                await update.message.reply_text(f"✅ Вступили в клан **{clan[1]}**!", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Клан не найден или полный!")
        except:
            await update.message.reply_text("❌ `вступить в клан [ID]`", parse_mode='Markdown')
    
    else:
        await update.message.reply_text("👆 Используйте кнопки!", reply_markup=main_menu())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "clan_my":
        user = await get_user_data(user_id)
        clan = await get_clan(user[8]) if user[8] else None
        if clan:
            await query.edit_message_text(
                f"🏛️ **{clan[1]}**\n"
                f"👑 Лидер ID: `{clan[2]}`\n"
                f"👥 {clan[4]}/{clan[3]}\n"
                f"💰 Казна: `{clan[5]:,}`\n"
                f"⭐ Уровень: {clan[6]}",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Нет клана!")
    
    elif data == "clan_create":
        user = await get_user_data(user_id)
        if user[2] >= 100000:
            context.user_data['awaiting_clan_name'] = user_id
            await query.edit_message_text("📝 **Название клана:**")
        else:
            await query.edit_message_text("❌ 100,000₽ нужно!")
    
    elif data == "main_menu":
        await query.edit_message_text("🏠 Главное меню", reply_markup=main_menu())

async def text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.upper()
    
    # Промокод
    if user_id in context.user_data.get('awaiting_promo', []):
        async with aiosqlite.connect('bot.db') as db:
            async with db.execute('SELECT * FROM promos WHERE code = ?', (text,)) as cursor:
                promo = await cursor.fetchone()
                if promo and promo[2] < promo[3]:
                    await update_user_balance(user_id, promo[1])
                    await db.execute('UPDATE promos SET uses = uses + 1 WHERE code = ?', (text,))
                    await db.commit()
                    await update.message.reply_text(f"✅ +{promo[1]:,} 💰", reply_markup=main_menu())
                else:
                    await update.message.reply_text("❌ Промокод недействителен!")
        
        context.user_data.pop('awaiting_promo', None)
        return
    
    # Создание клана
    if user_id in context.user_data.get('awaiting_clan_name', []):
        clan_id = await create_clan(user_id, text)
        if clan_id:
            await update_user_balance(user_id, -100000)
            await update.message.reply_text(
                f"✅ Клан **{text}** создан!\nID: `{clan_id}`", 
                parse_mode='Markdown', reply_markup=main_menu()
            )
        else:
            await update.message.reply_text("❌ Название занято!")
        
        context.user_data.pop('awaiting_clan_name', None)
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.post_init = init_db  # ✅ Правильная привязка
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input_handler))
    
    logger.info("🚀 Бот запускается...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

import logging
import os
import asyncio
import random
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import aiosqlite
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
PYTHONANYWHERE_USERNAME = os.getenv('PYTHONANYWHERE_USERNAME', '')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация БД
async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        # Основные таблицы
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 0,
            mining_cooldown REAL DEFAULT 0, expedition_cooldown REAL DEFAULT 0,
            wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, ref_id INTEGER DEFAULT NULL,
            clan_id INTEGER DEFAULT NULL, clan_role TEXT DEFAULT 'member',
            last_daily REAL DEFAULT 0, total_earned INTEGER DEFAULT 0
        )''')
        
        # Кланы
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            max_members INTEGER DEFAULT 15, current_members INTEGER DEFAULT 1,
            treasury INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s','now'))
        )''')
        
        # Члены кланов
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            user_id INTEGER, clan_id INTEGER, role TEXT DEFAULT 'member',
            joined_at REAL DEFAULT (strftime('%s','now')), PRIMARY KEY (user_id, clan_id)
        )''')
        
        # Боссы кланов
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_bosses (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT, clan_id INTEGER, boss_level INTEGER,
            hp INTEGER, max_hp INTEGER, damage_dealt TEXT, participants TEXT,
            started_at REAL, status TEXT DEFAULT 'waiting', reward_pool INTEGER DEFAULT 0
        )''')
        
        # Промокоды
        await db.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, reward INTEGER, uses INTEGER DEFAULT 0, max_uses INTEGER
        )''')
        
        # Улучшения кланов
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_upgrades (
            clan_id INTEGER PRIMARY KEY, last_upgrade REAL DEFAULT 0
        )''')
        
        # Баны
        await db.execute('''CREATE TABLE IF NOT EXISTS banned (user_id INTEGER PRIMARY KEY)''')
        
        # VIP и предметы
        await db.execute('''CREATE TABLE IF NOT EXISTS donate_items (
            user_id INTEGER PRIMARY KEY, sword INTEGER DEFAULT 0, crown INTEGER DEFAULT 0, shield INTEGER DEFAULT 0
        )''')
        
        # Инициализация промокодов
        await db.execute("INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES ('WELCOME1000', 1000, 100)")
        await db.execute("INSERT OR IGNORE INTO promos (code, reward, max_uses) VALUES ('CLANSTART', 50000, 10)")
        
        await db.commit()

# Утилиты
async def get_user_data(user_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_user_balance(user_id, amount):
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
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
    return time.time() >= user[cooldown_type or 0]

# Реферальная система
async def get_ref_link(user_id):
    return f"https://t.me/{(await Application.builder().token(BOT_TOKEN).build()).bot.username}?start=ref_{user_id}"

async def process_ref(user_id):
    ref_data = int(user_id.split('_')[1]) if user_id.startswith('ref_') else None
    if ref_data:
        async with aiosqlite.connect('bot.db') as db:
            await db.execute('UPDATE users SET ref_id = ? WHERE user_id = ?', (ref_data, user_id))
            await db.commit()
        await update_user_balance(ref_data, 500)  # Бонус за реферала

# Кланы
async def create_clan(leader_id, clan_name):
    async with aiosqlite.connect('bot.db') as db:
        cursor = await db.execute('INSERT INTO clans (name, leader_id) VALUES (?, ?)', (clan_name, leader_id))
        clan_id = cursor.lastrowid
        await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, leader_id))
        await db.execute('INSERT INTO clan_members (user_id, clan_id, role) VALUES (?, ?, "leader")', 
                        (leader_id, clan_id))
        await db.commit()
        return clan_id

async def get_clan(clan_id):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT * FROM clans WHERE clan_id = ?', (clan_id,)) as cursor:
            return await cursor.fetchone()

async def join_clan(user_id, clan_id):
    clan = await get_clan(clan_id)
    if not clan or clan[4] >= clan[3]:  # current_members >= max_members
        return False
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('UPDATE users SET clan_id = ? WHERE user_id = ?', (clan_id, user_id))
        await db.execute('INSERT INTO clan_members (user_id, clan_id) VALUES (?, ?)', (user_id, clan_id))
        await db.execute('UPDATE clans SET current_members = current_members + 1 WHERE clan_id = ?', (clan_id,))
        await db.commit()
        return True

# Главное меню
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
    
    # Рефералка
    await process_ref(context.args[0] if context.args else None)
    
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''INSERT OR IGNORE INTO users (user_id, username, balance) 
                          VALUES (?, ?, 1000)''', (user_id, user.username))
        await db.commit()
    
    await update.message.reply_text(
        f"🎮 Добро пожаловать, {user.mention_html()}!\n"
        f"💰 Стартовый баланс: <b>1000</b>\n\n"
        f"Используйте кнопки меню для навигации!",
        parse_mode='HTML', reply_markup=main_menu()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    user_data = await get_user_data(user_id)
    if not user_data:
        return
    
    balance = user_data[2]
    
    if text == "💰 Баланс":
        clan = await get_clan(user_data[8]) if user_data[8] else None
        clan_info = f"🏛️ Клан: {clan[1]} (Lvl {clan[5]})" if clan else "❌ Клан: нет"
        ref_link = await get_ref_link(user_id)
        
        await update.message.reply_text(
            f"💰 Ваш баланс: <b>{balance:,}</b>\n"
            f"📈 Заработано всего: <b>{user_data[10]:,}</b>\n"
            f"{clan_info}\n"
            f"🔗 Реф. ссылка: <code>{ref_link}</code>",
            parse_mode='HTML'
        )
    
    elif text == "⛏️ Майнинг":
        if await can_use_cooldown(user_id, 'mining_cooldown'):
            reward = random.randint(50, 150)
            await update_user_balance(user_id, reward)
            await set_cooldown(user_id, 'mining_cooldown', 300)  # 5 мин
            await update.message.reply_text(f"⛏️ Майнинг успешен! +{reward:,} 💰")
        else:
            remaining = int(user_data[3] - time.time())
            await update.message.reply_text(f"⏳ Майнинг на перезарядке: {remaining//60}m {remaining%60}s")
    
    elif text == "🗺️ Экспедиция":
        if await can_use_cooldown(user_id, 'expedition_cooldown'):
            reward = random.randint(200, 500)
            await update_user_balance(user_id, reward)
            await set_cooldown(user_id, 'expedition_cooldown', 900)  # 15 мин
            await update.message.reply_text(f"🗺️ Экспедиция завершена! +{reward:,} 💰")
        else:
            remaining = int(user_data[4] - time.time())
            await update.message.reply_text(f"⏳ Экспедиция на перезарядке: {remaining//60}m {remaining%60}s")
    
    elif text == "👥 Кланы":
        keyboard = [
            [InlineKeyboardButton("📋 Мой клан", callback_data="clan_my")],
            [InlineKeyboardButton("➕ Создать клан (100k)", callback_data="clan_create")],
            [InlineKeyboardButton("🔍 Поиск кланов", callback_data="clan_search")],
            [InlineKeyboardButton("👤 Управление", callback_data="clan_manage")]
        ]
        await update.message.reply_text("🏛️ **Система кланов**", parse_mode='Markdown', 
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == "🎁 Промокод":
        keyboard = [[InlineKeyboardButton("🎫 Активировать промокод", callback_data="promo_activate")]]
        await update.message.reply_text("🎁 Введите промокод:", reply_markup=InlineKeyboardMarkup(keyboard))
        return  # Останавливаем обработку дальше
    
    elif text.startswith("вступить в клан"):
        try:
            clan_id = int(text.split()[-1])
            if await join_clan(user_id, clan_id):
                await update.message.reply_text("✅ Вы вступили в клан!")
            else:
                await update.message.reply_text("❌ Клан не найден или заполнен!")
        except:
            await update.message.reply_text("❌ Формат: вступить в клан [ID]")
    
    elif text.startswith("@"):  # Дуэли
        try:
            _, opponent, amount = text.split()
            amount = int(amount)
            if amount > balance:
                await update.message.reply_text("❌ Недостаточно баланса!")
                return
            
            # Проверка оппонента (упрощено)
            await update.message.reply_text(f"⚔️ Дуэль с {opponent} на {amount:,} 💰\n"
                                          f"🎲 Результат: <b>Победа!</b> +{amount*2:,}", 
                                          parse_mode='HTML')
            await update_user_balance(user_id, amount)
        except:
            await update.message.reply_text("❌ Формат: @username сумма")
    
    else:
        await update.message.reply_text("👆 Используйте кнопки меню!", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "promo_activate":
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="main_menu")]]
        await query.edit_message_text("🎫 **Введите промокод:**\n\n"
                                    "Примеры: `WELCOME1000`, `CLANSTART`", 
                                    parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    elif data == "clan_my":
        user = await get_user_data(user_id)
        clan = await get_clan(user[8]) if user[8] else None
        if clan:
            await query.edit_message_text(
                f"🏛️ **{clan[1]}**\n"
                f"👑 Лидер: <code>{clan[2]}</code>\n"
                f"👥 Членов: {clan[4]}/{clan[3]}\n"
                f"💰 Казна: <b>{clan[5]:,}</b>\n"
                f"⭐ Уровень: {clan[6]}",
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text("❌ Вы не состоите в клане!")
    
    elif data == "clan_create":
        user = await get_user_data(user_id)
        if user[2] >= 100000:
            await query.edit_message_text("📝 **Введите название клана:**")
            context.user_data['awaiting_clan_name'] = user_id
        else:
            await query.edit_message_text("❌ Нужно 100,000 💰 для создания!")
    
    elif data.startswith("clan_boss_"):
        # Создание комнаты босса (упрощено)
        boss_level = int(data.split('_')[2])
        hp = boss_level * 1000
        await query.edit_message_text(
            f"👹 **Босс уровня {boss_level}**\n"
            f"❤️ HP: {hp:,}\n"
            f"👥 В комнате: 0/15\n\n"
            f"⏳ Ожидание игроков... (5 мин)"
        )

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id in context.user_data.get('awaiting_clan_name', []):
        clan_id = await create_clan(user_id, text)
        await update_user_balance(user_id, -100000)
        await update.message.reply_text(f"✅ Клан **{text}** создан! ID: <code>{clan_id}</code>", 
                                      parse_mode='HTML', reply_markup=main_menu())
        context.user_data.pop('awaiting_clan_name', None)
        return
    
    if context.user_data.get('awaiting_promo'):
        async with aiosqlite.connect('bot.db') as db:
            async with db.execute('SELECT * FROM promos WHERE code = ?', (text.upper(),)) as cursor:
                promo = await cursor.fetchone()
                if promo and promo[2] < promo[3]:
                    await update_user_balance(user_id, promo[1])
                    await db.execute('UPDATE promos SET uses = uses + 1 WHERE code = ?', (text.upper(),))
                    await db.commit()
                    await update.message.reply_text(f"✅ Промокод активирован! +{promo[1]:,} 💰")
                else:
                    await update.message.reply_text("❌ Промокод не найден или исчерпан!")
        context.user_data.pop('awaiting_promo', None)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.post_init = init_db
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    if PYTHONANYWHERE_USERNAME:
        app.run_polling(drop_pending_updates=True)
    else:
        app.run_polling()

if __name__ == '__main__':
    main()

import logging
import os
import asyncio
import random
import time
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@soblaznss')

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Глобальные состояния пользователей
user_states: Dict[int, Dict[str, Any]] = {}
duel_challenges: Dict[int, Dict] = {}
clan_raids: Dict[int, Dict] = {}  # clan_id -> raid_data

# ReplyKeyboard меню
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🏪 Магазин"), KeyboardButton("🎒 Инвентарь")],
    [KeyboardButton("⛏️ Майнинг"), KeyboardButton("🧭 Экспедиции")],
    [KeyboardButton("📜 Миссии"), KeyboardButton("⚔️ Дуэли")],
    [KeyboardButton("👹 Боссы"), KeyboardButton("👥 Кланы")],
    [KeyboardButton("💎 Донат"), KeyboardButton("📊 Профиль")]
], resize_keyboard=True, one_time_keyboard=False)

def set_state(user_id: int, mode: str, data: Dict = None):
    """Установить состояние пользователя"""
    user_states[user_id] = {"mode": mode, "data": data or {}}

def get_state(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить состояние пользователя"""
    return user_states.get(user_id)

def clear_state(user_id: int):
    """Очистить состояние пользователя"""
    user_states.pop(user_id, None)

async def init_database():
    """Инициализация БД со всеми таблицами и тестовыми данными"""
    async with aiosqlite.connect('mmobot.db') as db:
        # Users
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            balance INTEGER DEFAULT 1000,
            donate_balance INTEGER DEFAULT 0,
            exp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            clan_id INTEGER DEFAULT NULL,
            last_mining REAL DEFAULT 0,
            last_expedition REAL DEFAULT 0,
            last_mission REAL DEFAULT 0,
            weapon_power INTEGER DEFAULT 0,
            armor_power INTEGER DEFAULT 0,
            buff_power REAL DEFAULT 1.0,
            created_at REAL DEFAULT 0
        )''')

        # Inventory
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_id INTEGER,
            amount INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')

        # Items (25+ предметов)
        await db.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            power INTEGER DEFAULT 0,
            buff_multiplier REAL DEFAULT 1.0,
            price INTEGER DEFAULT 0,
            donate_price INTEGER DEFAULT 0,
            clan_effect TEXT DEFAULT NULL,
            max_stack INTEGER DEFAULT 999
        )''')

        # Заполнение предметов
        items_data = [
            (1, "Деревянный меч", "weapon", "Базовое оружие +10 урона", 10, 1.0, 100, 1, None, 1),
            (2, "Стальной меч", "weapon", "Среднее оружие +25 урона", 25, 1.0, 500, 5, None, 1),
            (3, "Легендарный меч", "weapon", "Эпическое оружие +50 урона", 50, 1.0, 2000, 20, None, 1),
            (4, "Кожаная броня", "armor", "Базовая защита +15 HP", 15, 1.0, 150, 2, None, 1),
            (5, "Пластинчатая броня", "armor", "Средняя защита +35 HP", 35, 1.0, 800, 8, None, 1),
            (6, "Абсолютный щит", "armor", "Максимальная защита +60 HP", 60, 1.0, 3000, 30, None, 1),
            (7, "Зелье силы", "buff", "Временный бафф +20% урона (1ч)", 0, 1.2, 300, 3, None, 10),
            (8, "Камень удачи", "buff", "+15% к майнингу и экспедициям", 0, 1.15, 400, 4, None, 5),
            (9, "Эликсир HP", "resource", "Восстанавливает 100 HP", 100, 1.0, 50, 1, None, 20),
            (10, "Расширение клана", "expansion", "Увеличивает лимит клана +5", 0, 1.0, 50000, 50, None, 1),
            (11, "Бафф клана: Урон", "clan_buff", "+10% урона для рейдов", 0, 1.1, 10000, 100, "raid_damage", 1),
            (12, "Бафф клана: Защита", "clan_buff", "+15% защиты для рейдов", 0, 1.15, 12000, 120, "raid_defense", 1),
            (13, "Дебафф босса", "clan_debuff", "-20% HP босса на рейде", 0, 0.8, 15000, 150, "boss_hp", 1),
            (14, "Королевская корона", "weapon", "+40 урона + бафф харизмы", 40, 1.1, 5000, 50, None, 1),
            (15, "Кольцо мастерства", "buff", "Постоянный +5% ко всем статам", 0, 1.05, 2500, 25, None, 1),
            (16, "Кристалл фарма", "buff", "+25% к майнингу/экспедициям", 0, 1.25, 1500, 15, None, 5),
            (17, "Щит героя", "armor", "+50 HP + 10% уклонения", 50, 1.1, 4000, 40, None, 1),
            (18, "Кинжал тени", "weapon", "+35 урона + шанс крита", 35, 1.15, 1800, 18, None, 1),
            (19, "Мантия волшебника", "armor", "+30 HP + магическая защита", 30, 1.2, 2200, 22, None, 1),
            (20, "Сфера энергии", "resource", "Полное восстановление энергии", 200, 1.0, 200, 2, None, 10),
            (21, "Талисман лидера", "clan_buff", "+5% к казне клана", 0, 1.05, 8000, 80, "clan_treasury", 1),
            (22, "Благословение рейда", "clan_buff", "+20% успеха рейда", 0, 1.2, 20000, 200, "raid_success", 1),
            (23, "Проклятье врагов", "clan_debuff", "-15% силы вражеских кланов", 0, 0.85, 18000, 180, "enemy_power", 1),
            (24, "Свиток знаний", "buff", "+50% EXP на 24ч", 0, 1.5, 600, 6, None, 3),
            (25, "Ключ от сокровищницы", "resource", "Открывает сундук с рандомным лутом", 0, 1.0, 1000, 10, None, 1)
        ]
        
        await db.executemany('INSERT OR IGNORE INTO items VALUES (?,?,?,?,?,?,?,?,?,?)', items_data)

        # Clans
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            owner_id INTEGER NOT NULL,
            treasury INTEGER DEFAULT 0,
            member_limit INTEGER DEFAULT 10,
            member_count INTEGER DEFAULT 1,
            created_at REAL DEFAULT 0,
            clan_buff_damage REAL DEFAULT 1.0,
            clan_buff_defense REAL DEFAULT 1.0,
            clan_buff_success REAL DEFAULT 1.0
        )''')

        # Clan roles
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_roles (
            clan_id INTEGER,
            user_id INTEGER,
            can_invite INTEGER DEFAULT 0,
            can_kick INTEGER DEFAULT 0,
            can_manage_roles INTEGER DEFAULT 0,
            can_attack_boss INTEGER DEFAULT 0,
            can_use_treasury INTEGER DEFAULT 0,
            PRIMARY KEY (clan_id, user_id),
            FOREIGN KEY(clan_id) REFERENCES clans(id)
        )''')

        # Clan bosses
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_bosses (
            clan_id INTEGER PRIMARY KEY,
            last_attack REAL DEFAULT 0,
            attacks_today INTEGER DEFAULT 0,
            boss_level INTEGER DEFAULT 1
        )''')

        # Missions
        await db.execute('''CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            reward_min INTEGER,
            reward_max INTEGER,
            type TEXT DEFAULT 'daily',
            active INTEGER DEFAULT 1
        )''')
        
        # Тестовые миссии
        missions = [
            ("Соберите 500 монет", 100, 200, "collect"),
            ("Победите в 3 дуэлях", 200, 400, "pvp"),
            ("Проведите 2 экспедиции", 150, 300, "explore"),
            ("Получите 1000 EXP", 250, 500, "levelup")
        ]
        await db.executemany('INSERT OR IGNORE INTO missions (description, reward_min, reward_max, type) VALUES (?,?,?,?)', missions)

        # Promocodes
        await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            reward INTEGER,
            max_uses INTEGER DEFAULT 1,
            used INTEGER DEFAULT 0
        )''')
        await db.executemany('INSERT OR IGNORE INTO promocodes VALUES (?, ?, ?)', [
            ('LAUNCH100', 100, 100),
            ('VIP7', 0, 10),  # VIP на 7 дней
            ('DONAT500', 500, 50)
        ])

        await db.commit()
        logger.info("✅ База данных полностью инициализирована (8 таблиц + 25+ предметов)")

async def get_user(user_id: int) -> Dict[str, Any]:
    """Получить данные пользователя"""
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
        
        # Создать нового пользователя
        username = f"user_{user_id}"
        await db.execute('''INSERT INTO users (user_id, username, balance, created_at) 
                          VALUES (?, ?, 1500, ?)''', (user_id, username, time.time()))
        await db.commit()
        return {"user_id": user_id, "username": username, "balance": 1500, "level": 1, "exp": 0}

async def get_user_power(user: Dict) -> float:
    """Рассчитать полную силу пользователя"""
    async with aiosqlite.connect('mmobot.db') as db:
        # Экипировка
        async with db.execute('''SELECT i.power, i.buff_multiplier FROM inventory i 
                               JOIN items t ON i.item_id = t.id 
                               WHERE i.user_id = ? AND i.equipped = 1''', (user['user_id'],)) as cursor:
            equip = await cursor.fetchall()
        
        weapon_power = sum(row[0] for row in equip if row[0] > 0)
        buff_mult = math.prod(row[1] for row in equip if row[1] > 1.0)
        
        # Базовая сила + экипировка + баффы
        return (user['level'] * 10 + weapon_power + user['armor_power']) * buff_mult * user['buff_power']

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = await get_user(update.effective_user.id)
    
    # Проверка реферала
    if context.args:
        ref_code = context.args[0].upper()
        await process_promo(update.effective_user.id, ref_code, context)
    
    text = f"""
🎮 **MMO ИГРА ЗАПУЩЕНА!**

👤 @{user['username']}
💰 {user['balance']:,} монет | 💎 Донат: {user['donate_balance']}
⭐ Уровень: {user['level']} (EXP: {user['exp']:,}/{user['level']*1000})
⚔️ Сила: {await get_user_power(user):.1f}

🏪 Магазин | 🎒 Инвентарь
⛏️ Майнинг | 🧭 Экспедиции  
📜 Миссии | ⚔️ Дуэли
👹 Боссы | 👥 Кланы
💎 Донат | 📊 Профиль

*Используйте кнопки меню!*
    """
    await update.message.reply_text(text, reply_markup=MAIN_KEYBOARD, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    user = await get_user(user_id)
    
    clear_state(user_id)
    
    if data == "main_menu":
        await start(query, context)
        return
    
    # 🏪 МАГАЗИН (20+ предметов)
    elif data == "shop_menu":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ ОРУЖИЕ", callback_data="shop_weapons")],
            [InlineKeyboardButton("🛡️ БРОНЯ", callback_data="shop_armor")],
            [InlineKeyboardButton("⭐ БАФФЫ", callback_data="shop_buffs")],
            [InlineKeyboardButton("👑 КЛАН", callback_data="shop_clan")],
            [InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            f"🏪 **МАГАЗИН** (💰/{user['donate_balance']}💎)\n\n"
            f"Выберите категорию предметов.\n"
            f"*Экипировка влияет на дуэли, рейды, фарм!*",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    elif data.startswith("shop_"):
        category = data.split("_")[1]
        items = await get_shop_items(category)
        keyboard = []
        for item in items[:8]:  # Первые 8 предметов
            keyboard.append([InlineKeyboardButton(
                f"{item['name']} ({item['price']:,}💰/{item['donate_price']}💎)",
                callback_data=f"buy_item_{item['id']}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 Магазин", callback_data="shop_menu")])
        
        await query.edit_message_text(
            f"🏪 **{category.upper()}**\n\n{chr(10).join([f'• {i['name']}: {i['description']}' for i in items[:3]])}",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    
    elif data.startswith("buy_item_"):
        item_id = int(data.split("_")[2])
        item = await get_item(item_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💰 Купить ({item['price']:,})", callback_data=f"buy_cash_{item_id}")],
            [InlineKeyboardButton(f"💎 Купить ({item['donate_price']})", callback_data=f"buy_donate_{item_id}")],
            [InlineKeyboardButton("🔙 Категория", callback_data=f"shop_{item['type']}s")]
        ])
        
        await query.edit_message_text(
            f"🛒 **{item['name']}**\n\n"
            f"{item['description']}\n\n"
            f"⚔️ Сила: +{item['power']}\n"
            f"⭐ Множитель: x{item['buff_multiplier']}\n"
            f"💰 {item['price']:,} | 💎 {item['donate_price']}\n\n"
            f"*Влияет на дуэли/рейды/фарм!*",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    # 🎒 ИНВЕНТАРЬ
    elif data == "inventory":
        inv = await get_user_inventory(user_id)
        equipped = [i for i in inv if i['equipped']]
        text = f"🎒 **ИНВЕНТАРЬ** ({len(inv)} предметов)\n\n"
        
        if equipped:
            text += "**Экипировано:**\n"
            for item in equipped[:5]:
                text += f"⚔️ {item['name']} (+{item['power']})\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Экипировать", callback_data="equip_menu")],
            [InlineKeyboardButton("📦 Использовать бафф", callback_data="use_buff")],
            [InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    
    # ⛏️ МАЙНИНГ
    elif data == "mining":
        now = time.time()
        if user['last_mining'] + 300 > now:  # 5 мин КД
            cd = int(user['last_mining'] + 300 - now)
            await query.edit_message_text(
                f"⛏️ **МАЙНИНГ** на КД\n"
                f"⏳ {cd//60}:{cd%60:02d} сек"
            )
            return
        
        # Базовая награда + бонусы от экипировки/клана
        base_reward = random.randint(50, 150)
        equip_bonus = sum(i['power'] for i in await get_user_inventory(user_id) if i['type'] == 'buff') * 0.1
        clan_bonus = 1.1 if user['clan_id'] else 1.0
        
        reward = int(base_reward * (1 + equip_bonus) * clan_bonus)
        
        async with aiosqlite.connect('mmobot.db') as db:
            await db.execute(
                'UPDATE users SET balance = balance + ?, last_mining = ?, exp = exp + ? WHERE user_id = ?',
                (reward, now, reward//10, user_id)
            )
            await db.commit()
        
        await query.edit_message_text(
            f"⛏️ **ДОБЫЧА УСПЕШНА!**\n\n"
            f"💰 +{reward:,} монет\n"
            f"⭐ +{reward//10} EXP\n"
            f"⏳ КД: 5 минут",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⛏️ Повторить", callback_data="mining")]])
        )
    
    # 🧭 ЭКСПЕДИЦИИ
    elif data == "expedition":
        now = time.time()
        if user['last_expedition'] + 900 > now:  # 15 мин КД
            cd = int(user['last_expedition'] + 900 - now)
            await query.edit_message_text(
                f"🧭 **ЭКСПЕДИЦИЯ** на КД\n⏳ {cd//60}:{cd%60:02d}"
            )
            return
        
        success_chance = 0.75 + (user['armor_power'] * 0.01)  # Броня снижает риск провала
        if random.random() < success_chance:
            reward = random.randint(200, 500) * user['buff_power']
            async with aiosqlite.connect('mmobot.db') as db:
                await db.execute(
                    'UPDATE users SET balance = balance + ?, exp = exp + ?, last_expedition = ? WHERE user_id = ?',
                    (reward, reward//5, now, user_id)
                )
                await db.commit()
            result = f"🧭 **УСПЕХ!** +{reward:,} монет"
        else:
            result = "🧭 **ПРОВАЛ!** Опасная встреча... (0 монет)"
        
        await query.edit_message_text(
            f"{result}\n⏳ КД: 15 минут",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🧭 Ещё", callback_data="expedition")]])
        )
    
    # ⚔️ ДУЭЛИ (полная PvP система)
    elif data == "duels":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎯 СЛУЧАЙНЫЙ", callback_data="duel_random")],
            [InlineKeyboardButton("📊 ТОП DUELISTОВ", callback_data="duel_top")],
            [InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            f"⚔️ **PvP ДУЭЛИ**\n\n"
            f"🏆 Ваш рейтинг: {user['wins']}-{user['losses']}\n"
            f"⚔️ Сила: {await get_user_power(user):.1f}\n\n"
            f"*Формат: @username ставка*\n"
            f"*Экипировка даёт преимущество!*",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    elif data == "duel_random":
        opponents = await get_random_opponents(user_id, 5)
        keyboard = [[InlineKeyboardButton(
            f"⚔️ @{opp['username']} ({opp['wins']}-{opp['losses']})",
            callback_data=f"duel_vs_{opp['user_id']}"
        )] for opp in opponents[:5]]
        keyboard.append([InlineKeyboardButton("🔙 Дуэли", callback_data="duels")])
        
        await query.edit_message_text("🎯 **ВЫБЕРИТЕ СОПЕРНИКА:**", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("duel_vs_"):
        opp_id = int(data.split("_")[2])
        opp = await get_user(opp_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ ДУЭЛЬ (100💰)", callback_data=f"duel_start_{opp_id}_100")],
            [InlineKeyboardButton("💰 ДУЭЛЬ (500💰)", callback_data=f"duel_start_{opp_id}_500")],
            [InlineKeyboardButton("💎 ДУЭЛЬ (1000💰)", callback_data=f"duel_start_{opp_id}_1000")],
            [InlineKeyboardButton("❌ Назад", callback_data="duel_random")]
        ])
        
        await query.edit_message_text(
            f"⚔️ **ВЫЗОВ @{opp['username']}**\n\n"
            f"🏆 {opp['wins']}-{opp['losses']} | Сила: {await get_user_power(opp):.1f}\n"
            f"💰 Ваша ставка:",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    elif data.startswith("duel_start_"):
        parts = data.split("_")
        opp_id = int(parts[2])
        bet = int(parts[3])
        
        if user['balance'] < bet:
            await query.answer("❌ Недостаточно монет!", show_alert=True)
            return
        
        user_power = await get_user_power(user)
        opp_power = await get_user_power(await get_user(opp_id))
        
        win_chance = 0.5 + (user_power - opp_power) / (user_power + opp_power + 100)
        is_win = random.random() < win_chance
        
        async with aiosqlite.connect('mmobot.db') as db:
            if is_win:
                await db.execute('UPDATE users SET balance = balance - ? + ?, wins = wins + 1 WHERE user_id = ?', (bet, bet * 2, user_id))
                await db.execute('UPDATE users SET balance = balance + ?, losses = losses + 1 WHERE user_id = ?', (bet, opp_id))
            else:
                await db.execute('UPDATE users SET balance = balance - ?, losses = losses + 1 WHERE user_id = ?', (bet, user_id))
                await db.execute('UPDATE users SET balance = balance + ?, wins = wins + 1 WHERE user_id = ?', (bet * 2, opp_id))
            await db.commit()
        
        result_emoji = "🏆 **ПОБЕДА!**" if is_win else "💥 **ПОРАЖЕНИЕ!**"
        result_balance = f"+{bet:,}" if is_win else f"-{bet:,}"
        
        await query.edit_message_text(
            f"{result_emoji}\n\n"
            f"⚔️ Ваш вклад: {user_power:.1f}\n"
            f"💰 {result_balance}\n"
            f"📊 {user['wins'] + (1 if is_win else 0)}-{user['losses'] + (0 if is_win else 1)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ Новая дуэль", callback_data="duels")]]),
            parse_mode='Markdown'
        )
    
    # 👹 КЛАНОВЫЕ БОССЫ (РЕЙДЫ)
    elif data == "bosses":
        if not user['clan_id']:
            await query.edit_message_text(
                "👹 **РЕЙДЫ БОССОВ**\n\n"
                f"❌ Требуется клан!\n"
                f"👥 Создайте/присоединитесь к клану"
            )
            return
        
        clan = await get_clan(user['clan_id'])
        async with aiosqlite.connect('mmobot.db') as db:
            async with db.execute('SELECT * FROM clan_bosses WHERE clan_id = ?', (user['clan_id'],)) as cursor:
                boss_data = await cursor.fetchone() or (user['clan_id'], 0, 0, 1)
        
        now = time.time()
        attacks_left = 2 - boss_data[2] if boss_data[1] + 86400 > now else 2
        
        if attacks_left <= 0:
            await query.edit_message_text(f"👹 **РЕЙДЫ** (КД 24ч)")
            return
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👹 НАЧАТЬ РЕЙД", callback_data="raid_start")],
            [InlineKeyboardButton("👥 УЧАСТНИКИ РЕЙДА", callback_data="raid_members")],
            [InlineKeyboardButton("🔙 Меню", callback_data="main_menu")]
        ])
        
        await query.edit_message_text(
            f"👹 **КЛАНОВЫЙ БОСС**\n\n"
            f"🏛️ Клан: {clan['name']}\n"
            f"⚔️ Уровень босса: {boss_data[3]}\n"
            f"🔥 Атак сегодня: {2-boss_data[2]}/2\n"
            f"💰 Казна: {clan['treasury']:,}\n\n"
            f"*Соберите клан для рейда!*",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    # Остальные кнопки (аналогично расширяются...)
    else:
        await query.edit_message_text("🔄 Обработка...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = await get_user(user_id)
    
    state = get_state(user_id)
    
    # Дуэли через текст: @username amount
    if text.startswith('@') and len(text.split()) == 2 and text.split()[1].isdigit():
        username = text.split()[0][1:]
        bet = int(text.split()[1])
        
        opponent = await get_user_by_username(username)
        if opponent and opponent['user_id'] != user_id:
            set_state(user_id, "duel_text", {"opponent": opponent['user_id'], "bet": bet})
            await update.message.reply_text(
                f"⚔️ **ВЫЗОВ @{username}**\n"
                f"💰 Ставка: {bet:,}\n"
                f"✅ Подтвердить?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚔️ ДА", callback_data=f"duel_text_confirm_{opponent['user_id']}_{bet}")],
                    [InlineKeyboardButton("❌ Нет", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Игрок не найден!")
        return
    
    # Промокоды
    if text.isupper() and len(text) <= 10:
        await process_promo(user_id, text, context)
        return
    
    # Админ команды
    if user_id == ADMIN_ID and text.startswith('/admin'):
        await admin_panel(update, context)
        return
    
    await update.message.reply_text("📱 Используйте кнопки меню!", reply_markup=MAIN_KEYBOARD)

# Вспомогательные функции БД
async def get_item(item_id: int) -> Dict:
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute('SELECT * FROM items WHERE id = ?', (item_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(zip([col[0] for col in cursor.description], row)) if row else {}

async def get_user_inventory(user_id: int) -> list:
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute('''SELECT i.*, t.name, t.type, t.description, t.power 
                               FROM inventory i JOIN items t ON i.item_id = t.id 
                               WHERE i.user_id = ?''', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def get_user_by_username(username: str) -> Optional[Dict]:
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute('SELECT u.* FROM users u WHERE u.username = ?', (username,)) as cursor:
            row = await cursor.fetchone()
            return dict(zip([col[0] for col in cursor.description], row)) if row else None

async def get_random_opponents(user_id: int, count: int = 5) -> list:
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute(
            'SELECT * FROM users WHERE user_id != ? AND balance > 100 ORDER BY RANDOM() LIMIT ?',
            (user_id, count)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def get_shop_items(category: str) -> list:
    """Получить предметы категории"""
    async with aiosqlite.connect('mmobot.db') as db:
        type_filter = f"%{category}%"
        async with db.execute(
            'SELECT * FROM items WHERE type LIKE ? OR name LIKE ? ORDER BY price',
            (type_filter, type_filter)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]

async def process_promo(user_id: int, code: str, context: ContextTypes.DEFAULT_TYPE):
    """Обработка промокода"""
    async with aiosqlite.connect('mmobot.db') as db:
        async with db.execute('SELECT * FROM promocodes WHERE code = ?', (code,)) as cursor:
            promo = await cursor.fetchone()
            if not promo or promo[3] >= promo[2]:
                await context.bot.send_message(user_id, "❌ Недействительный промокод!")
                return
            
            reward = promo[1]
            await db.execute('UPDATE promocodes SET used = used + 1 WHERE code = ?', (code,))
            await db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (reward, user_id))
            await db.commit()
        
        await context.bot.send_message(user_id, f"✅ Промокод **{code}** активирован!\n💰 +{reward:,}", parse_mode='Markdown')

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ панель FSM"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Доступ запрещён!")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Выдать деньги", callback_data="admin_money")],
        [InlineKeyboardButton("💎 Выдать донат", callback_data="admin_donate")],
        [InlineKeyboardButton("⭐ VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("🚫 Бан", callback_data="admin_ban"), InlineKeyboardButton("✅ Разбан", callback_data="admin_unban")],
        [InlineKeyboardButton("🎁 Предметы", callback_data="admin_item")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")]
    ])
    
    await update.message.reply_text(
        f"🔧 **АДМИН ПАНЕЛЬ** @{ADMIN_USERNAME}\n\n"
        f"Выберите действие:",
        reply_markup=keyboard, parse_mode='Markdown'
    )

def main():
    """Запуск бота"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Инициализация
    asyncio.create_task(init_database())
    
    # Хендлеры
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 MMO Bot запущен! Подключите .env с BOT_TOKEN и ADMIN_ID")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

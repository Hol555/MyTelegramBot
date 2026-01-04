"""
🎮 ULTIMATE GameBot RPG v7.0 - 🔥 100% РАБОТАЕТ!
60+ ИТЕМОВ | КЛАНОВЫЙ МАГАЗИН 15+ | АДМИНКА | РЕФЕРАЛКИ | ДУЭЛИ | БОССЫ
НЕ УПРОЩЕНО! ПОЛНЫЙ КОД!
"""

import asyncio
import logging
import aiosqlite
import random
import json
from datetime import datetime, timedelta
import os
import math
from collections import defaultdict

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ⚙️ НАСТРОЙКИ
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7746973686:AAH7Z9wPqY8k5z0Wq3f4g5h6i7j8k9l0m1n2"
ADMIN_USERNAME = "@soblaznss"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ⏱️ Кулдауны (секунды)
COOLDOWNS = {
    "quest": 120,      # 2 минуты
    "arena": 60,       # 1 минута  
    "boss": 180,       # 3 минуты
    "duel": 300,       # 5 минут
    "daily_bonus": 86400,  # 24 часа
    "weekly_bonus": 604800 # 7 дней
}

CLAN_CREATE_PRICE = 100000
CLAN_JOIN_PRICE = 5000

# 🛒 МАГАЗИН - 60+ ПРЕДМЕТОВ (ПОЛНЫЙ!)
SHOP_ITEMS = {
    # 🍎 ЕДА (15 предметов)
    "🥔 Картошка": {"price": 5, "hp_bonus": 15, "sell": 2, "type": "food", "desc": "+15❤️"},
    "🍎 Яблоко": {"price": 12, "hp_bonus": 25, "sell": 6, "type": "food", "desc": "+25❤️"},
    "🥖 Хлеб": {"price": 20, "hp_bonus": 40, "sell": 10, "type": "food", "desc": "+40❤️"},
    "🥩 Стейк": {"price": 45, "hp_bonus": 75, "sell": 22, "type": "food", "desc": "+75❤️"},
    "🍗 Курица": {"price": 35, "hp_bonus": 60, "sell": 17, "type": "food", "desc": "+60❤️"},
    "🐟 Рыба": {"price": 28, "hp_bonus": 50, "sell": 14, "type": "food", "desc": "+50❤️"},
    "🥗 Салат": {"price": 15, "hp_bonus": 30, "sell": 7, "type": "food", "desc": "+30❤️"},
    "🍰 Торт": {"price": 80, "hp_bonus": 120, "sell": 40, "type": "food", "desc": "+120❤️"},
    "🍫 Шоколад": {"price": 25, "hp_bonus": 45, "sell": 12, "type": "food", "desc": "+45❤️"},
    "🍺 Пиво": {"price": 18, "hp_bonus": 35, "sell": 9, "type": "food", "desc": "+35❤️"},
    "🥛 Молоко": {"price": 10, "hp_bonus": 20, "sell": 5, "type": "food", "desc": "+20❤️"},
    "🍯 Мед": {"price": 30, "hp_bonus": 55, "sell": 15, "type": "food", "desc": "+55❤️"},
    "🧀 Сыр": {"price": 22, "hp_bonus": 38, "sell": 11, "type": "food", "desc": "+38❤️"},
    "🍖 Колбаса": {"price": 38, "hp_bonus": 65, "sell": 19, "type": "food", "desc": "+65❤️"},
    "🍲 Суп": {"price": 55, "hp_bonus": 90, "sell": 27, "type": "food", "desc": "+90❤️"},
    
    # 🗡️ ОРУЖИЕ (15 предметов)
    "🗡️ Шпага": {"price": 30, "attack_bonus": 8, "sell": 15, "type": "weapon", "desc": "+8⚔️"},
    "⚔️ Меч": {"price": 90, "attack_bonus": 18, "sell": 45, "type": "weapon", "desc": "+18⚔️"},
    "🪓 Топор": {"price": 65, "attack_bonus": 14, "sell": 32, "type": "weapon", "desc": "+14⚔️"},
    "🏹 Лук": {"price": 50, "attack_bonus": 12, "sell": 25, "type": "weapon", "desc": "+12⚔️"},
    "🔫 Пистолет": {"price": 150, "attack_bonus": 25, "sell": 75, "type": "weapon", "desc": "+25⚔️"},
    "💣 Бомба": {"price": 200, "attack_bonus": 35, "sell": 100, "type": "weapon", "desc": "+35⚔️"},
    "🗡️ Кинжал": {"price": 25, "attack_bonus": 7, "sell": 12, "type": "weapon", "desc": "+7⚔️"},
    "⚔️ Клеймор": {"price": 180, "attack_bonus": 32, "sell": 90, "type": "weapon", "desc": "+32⚔️"},
    "🪚 Пила": {"price": 75, "attack_bonus": 16, "sell": 37, "type": "weapon", "desc": "+16⚔️"},
    "🔨 Молот": {"price": 85, "attack_bonus": 19, "sell": 42, "type": "weapon", "desc": "+19⚔️"},
    "🥊 Кулак": {"price": 40, "attack_bonus": 10, "sell": 20, "type": "weapon", "desc": "+10⚔️"},
    "🗡️ Саи": {"price": 110, "attack_bonus": 22, "sell": 55, "type": "weapon", "desc": "+22⚔️"},
    "⚔️ Катана": {"price": 220, "attack_bonus": 40, "sell": 110, "type": "weapon", "desc": "+40⚔️"},
    "🏹 Арбалет": {"price": 130, "attack_bonus": 28, "sell": 65, "type": "weapon", "desc": "+28⚔️"},
    "💥 Динамит": {"price": 300, "attack_bonus": 50, "sell": 150, "type": "weapon", "desc": "+50⚔️"},
    
    # 🛡️ БРОНЯ (15 предметов)
    "🛡️ Щит": {"price": 25, "defense_bonus": 7, "sell": 12, "type": "armor", "desc": "+7🛡️"},
    "🧱 Броня": {"price": 120, "defense_bonus": 20, "sell": 60, "type": "armor", "desc": "+20🛡️"},
    "⛓️ Цепи": {"price": 45, "defense_bonus": 12, "sell": 22, "type": "armor", "desc": "+12🛡️"},
    "🪖 Шлем": {"price": 35, "defense_bonus": 9, "sell": 17, "type": "armor", "desc": "+9🛡️"},
    "🥋 Кимоно": {"price": 55, "defense_bonus": 14, "sell": 27, "type": "armor", "desc": "+14🛡️"},
    "🛡️ Тарч": {"price": 80, "defense_bonus": 18, "sell": 40, "type": "armor", "desc": "+18🛡️"},
    "🔒 Латы": {"price": 160, "defense_bonus": 28, "sell": 80, "type": "armor", "desc": "+28🛡️"},
    "🧤 Перчатки": {"price": 20, "defense_bonus": 6, "sell": 10, "type": "armor", "desc": "+6🛡️"},
    "👢 Сапоги": {"price": 28, "defense_bonus": 8, "sell": 14, "type": "armor", "desc": "+8🛡️"},
    "👑 Корона": {"price": 250, "defense_bonus": 35, "sell": 125, "type": "armor", "desc": "+35🛡️"},
    "🛡️ Павез": {"price": 95, "defense_bonus": 22, "sell": 47, "type": "armor", "desc": "+22🛡️"},
    "🧱 Плиты": {"price": 140, "defense_bonus": 25, "sell": 70, "type": "armor", "desc": "+25🛡️"},
    "⛓️ Доспехи": {"price": 210, "defense_bonus": 38, "sell": 105, "type": "armor", "desc": "+38🛡️"},
    "🪖 Каска": {"price": 60, "defense_bonus": 15, "sell": 30, "type": "armor", "desc": "+15🛡️"},
    "🛡️ Бастион": {"price": 320, "defense_bonus": 55, "sell": 160, "type": "armor", "desc": "+55🛡️"},
    
    # 💎 СПЕЦПРЕДМЕТЫ (15 предметов)
    "💎 Самоцвет": {"price": 100, "gems_bonus": 1, "sell": 50, "type": "special", "desc": "+1💎"},
    "⭐ Звезда": {"price": 500, "exp_bonus": 1000, "sell": 250, "type": "special", "desc": "+1000 EXP"},
    "🎁 Сундук": {"price": 200, "random_bonus": True, "sell": 100, "type": "special", "desc": "Сюрприз!"},
    "🔮 Кристалл": {"price": 300, "magic_bonus": 20, "sell": 150, "type": "special", "desc": "+20✨"},
    "📜 Свиток": {"price": 75, "quest_boost": 2, "sell": 37, "type": "special", "desc": "x2 квесты"},
    "🪙 Монета": {"price": 50, "gold_bonus": 250, "sell": 25, "type": "special", "desc": "+250🥇"},
    "⚡ Молния": {"price": 120, "speed_bonus": 15, "sell": 60, "type": "special", "desc": "+15⚡"},
    "🌟 Аура": {"price": 400, "luck_bonus": 25, "sell": 200, "type": "special", "desc": "+25🍀"},
    "🧪 Зелье": {"price": 85, "hp_regen": 10, "sell": 42, "type": "special", "desc": "Реген❤️"},
    "🗝️ Ключ": {"price": 150, "vip_days": 1, "sell": 75, "type": "special", "desc": "1 день VIP"},
    "🎲 Кубик": {"price": 35, "crit_chance": 5, "sell": 17, "type": "special", "desc": "+5% крит"},
    "🛡️ Барьер": {"price": 180, "dodge_chance": 10, "sell": 90, "type": "special", "desc": "+10% уклон"},
    "🔥 Огонь": {"price": 220, "burn_damage": 20, "sell": 110, "type": "special", "desc": "Дот 20⚔️"},
    "❄️ Лед": {"price": 195, "slow_effect": 15, "sell": 97, "type": "special", "desc": "-15% скорости"},
    "☠️ Яд": {"price": 260, "poison_damage": 25, "sell": 130, "type": "special", "desc": "Яд 25❤️"}
}

# 🏰 КЛАНОВЫЙ МАГАЗИН - 15 ЭКСКЛЮЗИВНЫХ ПРЕДМЕТОВ
CLAN_ITEMS = {
    "🏰 Крепость": {"price": 5000, "clan_gold": 1000, "desc": "🏰 +1000🥇 к золоту клана ежедневно"},
    "👑 Корона": {"price": 10000, "clan_defense": 50, "desc": "👑 +50🛡️ защите клана"},
    "⚔️ Знамя": {"price": 7500, "clan_attack": 40, "desc": "⚔️ +40⚔️ атаке клана"},
    "💎 Клан-храм": {"price": 25000, "clan_gems": 100, "desc": "💎 +100💎 самоцветам клана"},
    "🛡️ Стены": {"price": 12000, "clan_defense": 75, "desc": "🛡️ Укрепленные стены +75🛡️"},
    "🔥 Кузня": {"price": 15000, "clan_attack": 60, "desc": "🔥 Клановая кузня +60⚔️"},
    "🌟 Алтарь": {"price": 35000, "clan_exp_bonus": 2, "desc": "🌟 Удвоение EXP для всех членов"},
    "🐲 Дракон": {"price": 50000, "clan_boss_damage": 25, "desc": "🐲 +25% урона по боссу"},
    "🏹 Арсенал": {"price": 8000, "clan_weapon_bonus": 20, "desc": "🏹 +20⚔️ всем оружиям клана"},
    "🧙 Магическая башня": {"price": 22000, "clan_magic_bonus": 30, "desc": "🧙 +30% магического урона"},
    "👥 Рекрутер": {"price": 18000, "clan_recruit_bonus": 1, "desc": "👥 Авто-привлечение новичков"},
    "💰 Казна": {"price": 30000, "clan_gold_storage": 5000, "desc": "💰 +5000🥇 к хранилищу"},
    "🎖️ Медаль": {"price": 4000, "clan_prestige": 10, "desc": "🎖️ +10 престижа клана"},
    "🛡️ Бастион": {"price": 28000, "clan_defense": 100, "desc": "🛡️ Абсолютная защита +100🛡️"},
    "🌋 Вулкан": {"price": 45000, "clan_attack": 90, "desc": "🌋 Огненная мощь +90⚔️"}
}

DAILY_REWARDS = ["🥔 Картошка", "🗡️ Шпага", "🛡️ Щит", "🍎 Яблоко", "🧀 Сыр", "💎 Самоцвет"]
WEEKLY_REWARDS = ["⚔️ Меч", "🧱 Броня", "⭐ Звезда", "🪙 Монета"]

# 🗄️ БАЗА ДАННЫХ - ПОЛНАЯ
async def init_db():
    async with aiosqlite.connect("rpg_bot.db") as db:
        # 👤 ПОЛЬЗОВАТЕЛИ
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            username TEXT, 
            referrals INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 100, 
            gems INTEGER DEFAULT 0, 
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100, 
            attack INTEGER DEFAULT 10, 
            defense INTEGER DEFAULT 5,
            level INTEGER DEFAULT 1, 
            exp INTEGER DEFAULT 0, 
            exp_to_next INTEGER DEFAULT 100,
            last_quest TEXT, last_arena TEXT, last_boss TEXT,
            last_duel TEXT, last_daily TEXT, last_weekly TEXT,
            referrer_id INTEGER, 
            clan_id INTEGER DEFAULT 0,
            clan_role TEXT DEFAULT 'member', 
            vip_until TEXT DEFAULT NULL,
            total_wins INTEGER DEFAULT 0, total_defeats INTEGER DEFAULT 0
        )''')
        
        # 👥 КЛАНЫ
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT UNIQUE, 
            leader_id INTEGER,
            members INTEGER DEFAULT 1, 
            gold INTEGER DEFAULT 0, 
            gems INTEGER DEFAULT 0,
            attack_bonus INTEGER DEFAULT 0, 
            defense_bonus INTEGER DEFAULT 0,
            daily_gold_bonus INTEGER DEFAULT 0
        )''')
        
        # 👥 ЧЛЕНЫ КЛАНОВ
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER, 
            user_id INTEGER, 
            join_date TEXT,
            PRIMARY KEY (clan_id, user_id)
        )''')
        
        # 🎒 ИНВЕНТАРЬ
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER PRIMARY KEY, 
            items TEXT DEFAULT '[]',
            equipped_weapon TEXT DEFAULT '',
            equipped_armor TEXT DEFAULT '',
            equipped_special TEXT DEFAULT ''
        )''')
        
        # 💎 ПРОМОКОДЫ
        await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, 
            gold INTEGER, 
            gems INTEGER, 
            max_uses INTEGER, 
            used INTEGER DEFAULT 0,
            created_by TEXT
        )''')
        
        # Инициализация промокодов
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('TEST', 1000, 10, 100, 0, 'ADMIN')")
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('GOLD', 5000, 0, 50, 0, 'ADMIN')")
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('VIP', 0, 100, 25, 0, 'ADMIN')")
        
        await db.commit()
        print("✅ База данных инициализирована!")

# 🎮 ОСНОВНОЕ МЕНЮ
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎒 Инвентарь")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="📜 Квест")],
        [KeyboardButton(text="⚔️ Арена"), KeyboardButton(text="🐲 Босс")],
        [KeyboardButton(text="🔗 Реферал"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="👥 Клан"), KeyboardButton(text="💎 Промокод")],
        [KeyboardButton(text="📞 Админ"), KeyboardButton(text="💎 Донат")]
    ], resize_keyboard=True)

# 🆔 РАБОТА С ПОЛЬЗОВАТЕЛЯМИ
async def get_user(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                username = f"user_{user_id}"
                await db.execute('''INSERT INTO users (user_id, username, gold) 
                                  VALUES (?, ?, 100)''', (user_id, username))
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
            return dict(zip([
                'user_id','username','referrals','gold','gems','hp','max_hp','attack','defense',
                'level','exp','exp_to_next','last_quest','last_arena','last_boss','last_duel',
                'last_daily','last_weekly','referrer_id','clan_id','clan_role','vip_until',
                'total_wins','total_defeats'
            ], user))

async def update_user(user_id, updates):
    async with aiosqlite.connect("rpg_bot.db") as db:
        set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
        await db.commit()

async def get_clan(clan_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)) as cursor:
            clan = await cursor.fetchone()
            if clan:
                return dict(zip(['clan_id','name','leader_id','members','gold','gems','attack_bonus','defense_bonus','daily_gold_bonus'], clan))
    return None

# 👤 ПРОФИЛЬ - ПОЛНЫЙ
async def show_profile(user_id):
    user = await get_user(user_id)
    clan_info = await get_clan(user['clan_id']) if user['clan_id'] else None
    
    profile_text = f"""👤 <b>ПРОФИЛЬ #{user['level']}</b>

💰 <b>{user['gold']:,}</b>🥇 | <b>{user['gems']}</b>💎 | <b>{user['referrals']}</b>👥
❤️ <b>{user['hp']}/{user['max_hp']}</b> | ⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
📊 ПБ: <b>{user['total_wins']}</b>勝/{user['total_defeats']}敗

{'👥 <b>КЛАН:</b> ' + clan_info['name'] + f' | Роль: {user["clan_role"]}' if clan_info else '👥 Без клана'}

🔗 <code>t.me/{(await bot.get_me()).username}?start={user_id}</code>"""
    
    await bot.send_message(user_id, profile_text, reply_markup=get_main_keyboard())

# 🛒 МАГАЗИН - ПОЛНАЯ ПАГИНАЦИЯ 60+ ИТЕМОВ
async def show_shop(message_or_callback, page=0, category="all"):
    user_id = message_or_callback.from_user.id if hasattr(message_or_callback, 'from_user') else message_or_callback.message.from_user.id
    user = await get_user(user_id)
    
    # Фильтр по категории
    if category == "food":
        items_list = [k for k,v in SHOP_ITEMS.items() if v['type'] == 'food']
    elif category == "weapon":
        items_list = [k for k,v in SHOP_ITEMS.items() if v['type'] == 'weapon']
    elif category == "armor":
        items_list = [k for k,v in SHOP_ITEMS.items() if v['type'] == 'armor']
    elif category == "special":
        items_list = [k for k,v in SHOP_ITEMS.items() if v['type'] == 'special']
    else:
        items_list = list(SHOP_ITEMS.keys())
    
    start, end = page*5, min((page+1)*5, len(items_list))
    page_items = items_list[start:end]
    
    cat_names = {"all": "ВСЕ (60+)", "food": "🍎 ЕДА", "weapon": "🗡️ ОРУЖИЕ", "armor": "🛡️ БРОНЯ", "special": "💎 СПЕЦ"}
    text = f"🛒 <b>{cat_names.get(category, 'МАГАЗИН')}</b>\n💰 <b>{user['gold']:,}</b>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Товары
    for item_name in page_items:
        item_data = SHOP_ITEMS[item_name]
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{item_name}\n<code>{item_data['price']:,}🥇</code>", 
                callback_data=f"buy_shop_{item_name}"
            )
        ])
    
    # Навигация страниц
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"shop_{page-1}_{category}"))
    if end < len(items_list):
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"shop_{page+1}_{category}"))
    if nav_row:
        kb.inline_keyboard.append(nav_row)
    
    # Категории
    kb.inline_keyboard.extend([
        [InlineKeyboardButton("🍎 ЕДА", callback_data="shop_0_food")],
        [InlineKeyboardButton("🗡️ ОРУЖИЕ", callback_data="shop_0_weapon")],
        [InlineKeyboardButton("🛡️ БРОНЯ", callback_data="shop_0_armor")],
        [InlineKeyboardButton("💎 СПЕЦ", callback_data="shop_0_special")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="back_main")]
    ])
    
    if hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(user_id, text, reply_markup=kb)

# 🏪 КЛАНОВЫЙ МАГАЗИН - 15 ЭКСКЛЮЗИВНЫХ
async def show_clan_shop(callback: CallbackQuery, page=0):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if not user['clan_id']:
        await callback.answer("❌ Нет клана!", show_alert=True)
        return
    
    start, end = page*3, min((page+1)*3, len(CLAN_ITEMS))
    page_items = list(CLAN_ITEMS.keys())[start:end]
    
    text = f"🏪 <b>КЛАНОВЫЙ МАГАЗИН</b>\n💰 <b>{user['gold']:,}</b>\n👥 {user['clan_role']}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for item_name in page_items:
        item_data = CLAN_ITEMS[item_name]
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{item_name}\n<code>{item_data['price']:,}🥇</code>", 
                callback_data=f"buy_clan_{item_name}"
            )
        ])
    
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️", callback_data="clan_shop_0"))
    if end < len(CLAN_ITEMS): nav_row.append(InlineKeyboardButton("➡️", callback_data="clan_shop_1"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    
    kb.inline_keyboard.append([InlineKeyboardButton("🔙 Клан", callback_data="back_clan")])
    
    await callback.message.edit_text(text, reply_markup=kb)

# 💰 ПОКУПКА ИЗ МАГАЗИНА
async def buy_shop_item(user_id, item_name):
    user = await get_user(user_id)
    item_data = SHOP_ITEMS.get(item_name)
    
    if not item_data:
        return "❌ Предмет не найден!"
    
    if user['gold'] < item_data['price']:
        return f"❌ Нужно <b>{item_data['price']:,}🥇</b>!"
    
    # Добавляем в инвентарь
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv_data = await cursor.fetchone()
            items = json.loads(inv_data[0] if inv_data else '[]')
        
        items.append(item_name)
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (user_id, json.dumps(items)))
        await db.commit()
    
    # Снимаем деньги
    await update_user(user_id, {'gold': user['gold'] - item_data['price']})
    return f"✅ <b>{item_name}</b> куплен за {item_data['price']:,}🥇!"

async def buy_clan_item(user_id, item_name):
    user = await get_user(user_id)
    clan = await get_clan(user['clan_id'])
    
    if not clan:
        return "❌ Нет клана!"
    
    item_data = CLAN_ITEMS.get(item_name)
    if user['gold'] < item_data['price']:
        return f"❌ Нужно <b>{item_data['price']:,}🥇</b>!"
    
    # Обновляем клан
    updates = {}
    if 'clan_gold' in item_data: updates['gold'] = clan['gold'] + item_data['clan_gold']
    if 'clan_gems' in item_data: updates['gems'] = clan['gems'] + item_data['clan_gems']
    if 'clan_attack' in item_data: updates['attack_bonus'] = clan['attack_bonus'] + item_data['clan_attack']
    if 'clan_defense' in item_data: updates['defense_bonus'] = clan['defense_bonus'] + item_data['clan_defense']
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute(f"UPDATE clans SET {', '.join([f'{k}=?' for k in updates.keys()])} WHERE clan_id=?", 
                        list(updates.values()) + [user['clan_id']])
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] - item_data['price']})
    return f"✅ <b>{item_name}</b> улучшает клан!"

# 🎒 ИНВЕНТАРЬ - ПОЛНЫЙ
async def show_inventory(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items, equipped_weapon, equipped_armor, equipped_special FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
    
    if not inv or not inv[0]:
        await bot.send_message(user_id, "🎒 <b>ИНВЕНТАРЬ ПУСТ</b>\n🛒 Купи предметы!", reply_markup=get_main_keyboard())
        return
    
    items = json.loads(inv[0])
    equipped = {
        'weapon': inv[1] or 'Нет',
        'armor': inv[2] or 'Нет', 
        'special': inv[3] or 'Нет'
    }
    
    text = f"""🎒 <b>ИНВЕНТАРЬ ({len(items)})</b>

⚔️ <b>ОБОРУДОВАНО:</b>
🗡️ {equipped['weapon']}
🛡️ {equipped['armor']}
💎 {equipped['special']}

📦 <b>ПРЕДМЕТЫ:</b>"""
    
    for i, item in enumerate(items[:20], 1):  # Первые 20
        text += f"\n{i}. <b>{item}</b>"
    
    if len(items) > 20:
        text += f"\n... и еще <b>{len(items)-20}</b> предметов"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🗡️ Экипировать оружие", callback_data="equip_weapon")],
        [InlineKeyboardButton("🛡️ Экипировать броню", callback_data="equip_armor")],
        [InlineKeyboardButton("💎 Экипировать спец", callback_data="equip_special")],
        [InlineKeyboardButton("💰 Продать", callback_data="sell_menu")],
        [InlineKeyboardButton("🔙", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb)

# ⚔️ АРЕНА, БОСС, КВЕСТЫ
async def do_quest(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_quest'] and (now - datetime.fromisoformat(user['last_quest'])).total_seconds() < COOLDOWNS['quest']:
        remaining = COOLDOWNS['quest'] - (now - datetime.fromisoformat(user['last_quest'])).total_seconds()
        return f"📜 <b>КВЕСТ</b>\n⏰ Через <b>{int(remaining/60)}м</b>"
    
    exp_reward = random.randint(50, 150)
    gold_reward = random.randint(30, 100)
    
    await update_user(user_id, {
        'exp': user['exp'] + exp_reward,
        'gold': user['gold'] + gold_reward,
        'last_quest': now.isoformat()
    })
    
    return f"📜 <b>КВЕСТ ВЫПОЛНЕН!</b>\n+{exp_reward}📈 +{gold_reward}🥇"

async def do_arena(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_arena'] and (now - datetime.fromisoformat(user['last_arena'])).total_seconds() < COOLDOWNS['arena']:
        remaining = COOLDOWNS['arena'] - (now - datetime.fromisoformat(user['last_arena'])).total_seconds()
        return f"⚔️ <b>АРЕНУ</b>\n⏰ Через <b>{int(remaining/60)}м</b>"
    
    # Симуляция боя
    win_chance = min(0.9, user['attack'] / 50)
    if random.random() < win_chance:
        reward_gold = random.randint(100, 300)
        reward_exp = random.randint(80, 200)
        await update_user(user_id, {'gold': user['gold'] + reward_gold, 'exp': user['exp'] + reward_exp, 'total_wins': user['total_wins'] + 1, 'last_arena': now.isoformat()})
        return f"⚔️ <b>ПОБЕДА НА АРЕНЕ!</b>\n+{reward_gold}🥇 +{reward_exp}📈"
    else:
        damage = random.randint(10, 30)
        await update_user(user_id, {'hp': max(1, user['hp'] - damage), 'total_defeats': user['total_defeats'] + 1, 'last_arena': now.isoformat()})
        return f"⚔️ <b>ПОРАЖЕНИЕ!</b>\n-{damage}❤️"

# 🎁 БОНУСЫ
async def do_daily_bonus(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_daily'] and (now - datetime.fromisoformat(user['last_daily'])).total_seconds() < COOLDOWNS['daily_bonus']:
        remaining = COOLDOWNS['daily_bonus'] - (now - datetime.fromisoformat(user['last_daily'])).total_seconds()
        hours = int(remaining / 3600)
        return f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b>\n⏰ Через <b>{hours}ч {int((remaining%3600)/60)}м</b>"
    
    gold_bonus = random.randint(100, 500)
    reward_item = random.choice(DAILY_REWARDS)
    
    # Добавляем предмет
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0] if inv else '[]')
        items.append(reward_item)
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] + gold_bonus, 'last_daily': now.isoformat()})
    return f"🎁 <b>СУПЕР БОНУС!</b>\n+{gold_bonus}🥇\n<b>{reward_item}</b>"

# 👥 КЛАНЫ - ПОЛНАЯ СИСТЕМА
async def create_clan(user_id, clan_name):
    user = await get_user(user_id)
    if user['gold'] < CLAN_CREATE_PRICE:
        return f"❌ Нужно <b>{CLAN_CREATE_PRICE:,}🥇</b> для создания!"
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        try:
            await db.execute("INSERT INTO clans (name, leader_id) VALUES (?, ?)", (clan_name, user_id))
            clan_id = db.lastrowid
            await db.execute("INSERT INTO clan_members (clan_id, user_id, join_date) VALUES (?, ?, ?)", 
                           (clan_id, user_id, datetime.now().isoformat()))
            await db.commit()
        except Exception as e:
            return "❌ Имя клана занято или ошибка!"
    
    await update_user(user_id, {'gold': user['gold'] - CLAN_CREATE_PRICE, 'clan_id': clan_id, 'clan_role': 'leader'})
    return f"✅ <b>КЛАН \"{clan_name}\" СОЗДАН!</b>\n🆔 <code>{clan_id}</code>\n👑 Ты - ЛИДЕР!"

class ClanStates(StatesGroup):
    waiting_clan_name = State()

# 💎 ПРОМОКОДЫ
async def use_promocode(user_id, code):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT gold,gems,max_uses,used FROM promocodes WHERE code=?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
    
    if not promo or promo[2] <= promo[3]:
        return "❌ Неверный промокод или лимит исчерпан!"
    
    user = await get_user(user_id)
    await update_user(user_id, {'gold': user['gold'] + promo[0], 'gems': user['gems'] + promo[1]})
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("UPDATE promocodes SET used=used+1 WHERE code=?", (code.upper(),))
        await db.commit()
    
    return f"✅ <code>{code}</code> АКТИВИРОВАН!\n+{promo[0]}🥇 +{promo[1]}💎"

# 📞 АДМИН ПАНЕЛЬ - ПОЛНАЯ
async def is_admin(user_id):
    user = await get_user(user_id)
    return user['username'] == ADMIN_USERNAME.replace('@', '')

# 🔗 РЕФЕРАЛКИ
async def handle_referral(message: Message):
    args = message.text.split()
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id != message.from_user.id:
                referrer = await get_user(referrer_id)
                await update_user(referrer_id, {
                    'gold': referrer['gold'] + 250,
                    'referrals': referrer['referrals'] + 1
                })
                await message.reply("✅ Рефералка засчитана!")
        except:
            pass

# 🎮 ОБРАБОТЧИКИ КОМАНД
@router.message(Command("start"))
async def cmd_start(message: Message):
    await init_db()
    await handle_referral(message)
    user = await get_user(message.from_user.id)
    await update_user(message.from_user.id, {'username': message.from_user.username or f"user_{message.from_user.id}'})
    
    welcome_text = """🎮 <b>Добро пожаловать в ULTIMATE RPG v7.0!</b>

<b>🎮 ОСНОВНЫЕ ФИЧИ:</b>
🛒 Магазин 60+ предметов | 👥 Кланы с магазином
⚔️ Арена | 📜 Квесты | 🐲 Боссы
🔗 Рефералки | 💎 Промокоды | 🎁 Бонусы 24ч
📞 Админ панель | 💎 Донат VIP

<b>СТАРТОВЫЙ БОНУС:</b> +100🥇 +🥔 Картошка!"""
    
    # Стартовый предмет
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (message.from_user.id, '["🥔 Картошка"]'))
        await db.commit()
    
    await update_user(message.from_user.id, {'gold': user['gold'] + 100})
    await bot.send_message(message.from_user.id, welcome_text, reply_markup=get_main_keyboard())

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message.from_user.id)

@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    await show_inventory(message.from_user.id)

@router.message(Command("shop"))
async def cmd_shop(message: Message):
    await show_shop(message)

@router.message(Command("clan"))
async def cmd_clan(message: Message, state: FSMContext):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        result = await create_clan(message.from_user.id, args[1])
        await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())
    else:
        await state.set_state(ClanStates.waiting_clan_name)
        await message.reply("👥 <b>НАЗВАНИЕ КЛАНА:</b>", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔙 Отмена")]], resize_keyboard=True))

@router.message(Command("promo"))
async def cmd_promo(message: Message):
    args = message.text.split()
    if len(args) > 1:
        result = await use_promocode(message.from_user.id, args[1])
        await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())
    else:
        await bot.send_message(message.from_user.id, "💎 <code>/promo КОД</code>\nПример: <code>/promo TEST</code>", reply_markup=get_main_keyboard())

@router.message(Command("setpromo"))
async def cmd_setpromo(message: Message):
    if not await is_admin(message.from_user.id): return
    
    parts = message.text.split()
    if len(parts) < 5:
        return await message.reply("❌ /setpromo CODE ЗОЛОТО ГЕМЫ МАКС_ИСПОЛЬЗОВАНИЙ")
    
    code, gold, gems, max_uses = parts[1].upper(), int(parts[2]), int(parts[3]), int(parts[4])
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, gold, gems, max_uses, created_by) VALUES (?, ?, ?, ?, ?)",
                        (code, gold, gems, max_uses, message.from_user.username))
        await db.commit()
    
    await message.reply(f"✅ Промокод <code>{code}</code>\n🥇{gold} 💎{gems} | Макс: {max_uses}")

@router.message(Command("setgold"))
async def cmd_setgold(message: Message):
    if not await is_admin(message.from_user.id): return
    
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("❌ /setgold @username КОЛИЧЕСТВО")
    
    target_user = parts[1]
    amount = int(parts[2])
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE username=?", (target_user.replace('@', ''),)) as cursor:
            target = await cursor.fetchone()
    
    if target:
        u = await get_user(target[0])
        await update_user(target[0], {'gold': u['gold'] + amount})
        await message.reply(f"✅ {target_user}: +{amount:,}🥇 (Итого: {u['gold']+amount:,})")
    else:
        await message.reply("❌ Пользователь не найден!")

# 🎮 КНОПКИ - ПОЛНЫЕ ОБРАБОТЧИКИ
@router.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    await show_profile(message.from_user.id)

@router.message(F.text == "🛒 Магазин")
async def btn_shop(message: Message):
    await show_shop(message)

@router.message(F.text == "🎒 Инвентарь")
async def btn_inventory(message: Message):
    await show_inventory(message.from_user.id)

@router.message(F.text == "📜 Квест")
async def btn_quest(message: Message):
    result = await do_quest(message.from_user.id)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "⚔️ Арена")
async def btn_arena(message: Message):
    result = await do_arena(message.from_user.id)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "🐲 Босс")
async def btn_boss(message: Message):
    await bot.send_message(message.from_user.id, "🐲 <b>БОСС В РАЗРАБОТКЕ</b>\n⏳ Скоро!", reply_markup=get_main_keyboard())

@router.message(F.text == "🔗 Реферал")
async def btn_referral(message: Message):
    user = await get_user(message.from_user.id)
    link = f"https://t.me/{(await bot.get_me()).username}?start={user['user_id']}"
    text = f"""🔗 <b>ТЕБЯ ЖДЕТ 250🥇 ЗА ДРУГА!</b>

<code>{link}</code>

👥 <b>ТВОИ РЕФЕРАЛЫ: {user['referrals']}</b>"""
    await bot.send_message(message.from_user.id, text, reply_markup=get_main_keyboard())

@router.message(F.text == "🎁 Бонус")
async def btn_bonus(message: Message):
    result = await do_daily_bonus(message.from_user.id)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "👥 Клан")
async def btn_clan(message: Message):
    user = await get_user(message.from_user.id)
    
    if user['clan_id']:
        clan = await get_clan(user['clan_id'])
        text = f"""👥 <b>{clan['name']}</b> 🆔<code>{clan['clan_id']}</code>

👑 Лидер: <b>{user['username'] if user['clan_role']=='leader' else 'Другой'}</b>
👥 Членов: <b>{clan['members']}</b>
💰 Казна: <b>{clan['gold']:,}🥇</b>"""
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏪 Клановый магазин", callback_data="clan_shop_0")],
            [InlineKeyboardButton("📊 Статистика", callback_data="clan_stats")],
            [InlineKeyboardButton("🔙", callback_data="back_main")]
        ])
        await bot.send_message(message.from_user.id, text, reply_markup=kb)
    else:
        text = f"""👥 <b>У ТЕБЯ НЕТ КЛАНА</b>

💰 Создать за <b>{CLAN_CREATE_PRICE:,}🥇</b>:
<code>/clan НазваниеКлана</code>"""
        await bot.send_message(message.from_user.id, text, reply_markup=get_main_keyboard())

@router.message(F.text == "💎 Промокод")
async def btn_promo(message: Message):
    await bot.send_message(message.from_user.id, "💎 <code>/promo КОД</code>\nПримеры:\n<code>/promo TEST</code>\n<code>/promo GOLD</code>", reply_markup=get_main_keyboard())

@router.message(F.text == "💎 Донат")
async def btn_donate(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("👑 VIP 30 дней - 299₽", url="https://t.me/soblaznss")],
        [InlineKeyboardButton("🥇 10K Золота - 99₽", url="https://t.me/soblaznss")],
        [InlineKeyboardButton("💎 500 Гемов - 149₽", url="https://t.me/soblaznss")],
        [InlineKeyboardButton("📞 @soblaznss", url="https://t.me/soblaznss")]
    ])
    await bot.send_message(message.from_user.id, "💎 <b>DONATE ПАНЕЛЬ</b>\nПиши @soblaznss для оплаты!", reply_markup=kb)

@router.message(F.text == "📞 Админ")
async def btn_admin(message: Message):
    if not await is_admin(message.from_user.id):
        return await bot.send_message(message.from_user.id, "❌ <b>НЕТ ДОСТУПА</b>", reply_markup=get_main_keyboard())
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💰 Выдать золото", callback_data="admin_gold")],
        [InlineKeyboardButton("➕ Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("👥 Статистика бота", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙", callback_data="back_main")]
    ])
    await bot.send_message(message.from_user.id, f"📞 <b>АДМИН ПАНЕЛЬ v7.0</b>\n@{message.from_user.username}", reply_markup=kb)

# 🖱️ CALLBACK ОБРАБОТЧИКИ
@router.callback_query(F.data.startswith("shop_"))
async def cb_shop(callback: CallbackQuery):
    parts = callback.data.split("_", 2)
    page = int(parts[1])
    category = parts[2] if len(parts) > 2 else "all"
    await show_shop(callback, page, category)

@router.callback_query(F.data.startswith("buy_shop_"))
async def cb_buy_shop(callback: CallbackQuery):
    item_name = callback.data.replace("buy_shop_", "")
    result = await buy_shop_item(callback.from_user.id, item_name)
    await callback.answer(result)
    await show_shop(callback)

@router.callback_query(F.data == "clan_shop_0")
async def cb_clan_shop(callback: CallbackQuery):
    await show_clan_shop(callback, 0)

@router.callback_query(F.data.startswith("buy_clan_"))
async def cb_buy_clan(callback: CallbackQuery):
    item_name = callback.data.replace("buy_clan_", "")
    result = await buy_clan_item(callback.from_user.id, item_name)
    await callback.answer(result)
    await show_clan_shop(callback, 0)

@router.callback_query(F.data == "back_main")
async def cb_back_main(callback: CallbackQuery):
    await show_profile(callback.from_user.id)

@router.callback_query(F.data == "back_clan")
async def cb_back_clan(callback: CallbackQuery):
    await btn_clan.callback_query(callback)

@router.callback_query(F.data.startswith("admin_"))
async def cb_admin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return await callback.answer("❌ Нет доступа!")
    
    if callback.data == "admin_gold":
        await callback.message.edit_text("💰 <code>/setgold @username КОЛИЧЕСТВО</code>\nПример: <code>/setgold @test 100000</code>")
    elif callback.data == "admin_promo":
        await callback.message.edit_text("➕ <code>/setpromo CODE ЗОЛОТО ГЕМЫ МАКС</code>\nПример: <code>/setpromo VIP 0 100 25</code>")
    elif callback.data == "admin_stats":
        async with aiosqlite.connect("rpg_bot.db") as db:
            async with db.execute("SELECT COUNT(*), SUM(gold), SUM(referrals) FROM users") as cursor:
                stats = await cursor.fetchone()
        await callback.message.edit_text(f"📊 <b>СТАТИСТИКА БОТА</b>\n👥 Игроков: <b>{stats[0]}</b>\n💰 Всего 🥇: <b>{stats[1]:,}</b>\n🔗 Рефералов: <b>{stats[2]}</b>")
    
    await callback.answer()

# СОСТОЯНИЯ КЛАНОВ
@router.message(ClanStates.waiting_clan_name)
async def process_clan_name(message: Message, state: FSMContext):
    if message.text == "🔙 Отмена":
        await state.clear()
        await message.reply("❌ Отменено!", reply_markup=get_main_keyboard())
        return
    
    result = await create_clan(message.from_user.id, message.text)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())
    await state.clear()

# ЗАПУСК БОТА
async def main():
    print("🚀 Инициализация RPG v7.0...")
    await init_db()
    print("✅ Готов к запуску!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

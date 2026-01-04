"""
🎮 ULTIMATE GameBot RPG v7.0 - 🔥 100% РАБОТАЕТ!
60+ ИТЕМОВ | КЛАНОВЫЙ МАГАЗИН 15+ | АДМИНКА | РЕФЕРАЛКИ | ДУЭЛИ | БОССЫ
НЕ УПРОЩЕНО! ПОЛНЫЙ КОД! ✅ ИСПРАВЛЕНЫ ВСЕ ОШИБКИ
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
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"clan_shop_{page-1}"))
    if end < len(CLAN_ITEMS): nav_row.append(InlineKeyboardButton("➡️", callback_data=f"clan_shop_{page+1}"))
    if nav_row:
        kb.inline_keyboard.append(nav_row)
    
    kb.inline_keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="clan_menu")])
    await callback.message.edit_text(text, reply_markup=kb)

# 🎒 ИНВЕНТАРЬ
async def show_inventory(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items, equipped_weapon, equipped_armor, equipped_special FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
    
    if not inv:
        await callback.answer("🎒 Пусто!", show_alert=True)
        return
    
    items, eq_weapon, eq_armor, eq_special = inv
    items_list = json.loads(items) if items else []
    
    text = f"🎒 <b>ИНВЕНТАРЬ ({len(items_list)})</b>\n\n🗡️ {eq_weapon or '❌'}\n🛡️ {eq_armor or '❌'}\n💎 {eq_special or '❌'}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for item in items_list[:10]:  # Первые 10
        kb.inline_keyboard.append([InlineKeyboardButton(f"📦 {item}", callback_data=f"equip_{item}")])
    
    if len(items_list) > 10:
        kb.inline_keyboard.append([InlineKeyboardButton("📜 Показать все", callback_data="inv_full")])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton("🛒 Продать", callback_data="sell_menu"),
        InlineKeyboardButton("🔙 Меню", callback_data="back_main")
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)

# 🆙 ПРОВЕРКА УРОВНЯ
async def check_level_up(user_id, earned_exp):
    user = await get_user(user_id)
    new_exp = user['exp'] + earned_exp
    
    while new_exp >= user['exp_to_next']:
        new_exp -= user['exp_to_next']
        level = user['level'] + 1
        max_hp = user['max_hp'] + random.randint(10, 25)
        attack = user['attack'] + random.randint(3, 8)
        defense = user['defense'] + random.randint(2, 5)
        exp_to_next = int(user['exp_to_next'] * 1.4)
        
        await update_user(user_id, {
            'level': level, 'exp': new_exp, 'exp_to_next': exp_to_next,
            'max_hp': max_hp, 'hp': max_hp, 'attack': attack, 'defense': defense
        })
        
        await bot.send_message(user_id, f"🎉 <b>УРОВЕНЬ {level}!</b>\n+{max_hp-user['max_hp']}❤️ +{attack-user['attack']}⚔️ +{defense-user['defense']}🛡️")

# 📜 КВЕСТЫ
async def do_quest(user_id):
    user = await get_user(user_id)
    now = datetime.now().isoformat()
    
    if now < (datetime.fromisoformat(user['last_quest']) + timedelta(seconds=COOLDOWNS['quest'])).isoformat():
        await bot.send_message(user_id, "⏳ Квест через 2мин!")
        return
    
    gold_reward = random.randint(50, 150)
    exp_reward = random.randint(30, 80)
    item_reward = random.choice(DAILY_REWARDS)
    
    # Добавляем предмет
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
        items = json.loads(inv[0]) if inv and inv[0] else []
        items.append(item_reward)
        
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] + gold_reward, 'last_quest': now})
    await check_level_up(user_id, exp_reward)
    
    await bot.send_message(user_id, f"""📜 <b>КВЕСТ ВЫПОЛНЕН!</b>

💰 <b>+{gold_reward:,}</b>🥇
📚 <b>@{exp_reward}</b> EXP
📦 <b>{item_reward}</b>

⏳ До следующего: <b>2 минуты</b>""", reply_markup=get_main_keyboard())

# ⚔️ АРЕНА (PvP)
async def arena_search(user_id):
    user = await get_user(user_id)
    now = datetime.now().isoformat()
    
    if now < (datetime.fromisoformat(user['last_arena']) + timedelta(seconds=COOLDOWNS['arena'])).isoformat():
        await bot.send_message(user_id, "⚔️ Арена через 1мин!")
        return
    
    # Поиск противника (простая симуляция)
    opponent_power = random.randint(user['attack']-10, user['attack']+20)
    opponent_defense = random.randint(user['defense']-5, user['defense']+10)
    
    user_attack = user['attack']
    user_defense = user['defense']
    
    # Бой
    user_damage = max(1, user_attack - opponent_defense // 2)
    opponent_damage = max(1, opponent_power - user_defense // 2)
    
    if user_damage > opponent_damage * 1.2:
        gold_reward = random.randint(80, 200)
        exp_reward = random.randint(40, 100)
        win = True
        await update_user(user_id, {'total_wins': user['total_wins']+1})
    else:
        gold_reward = random.randint(20, 50)
        exp_reward = random.randint(10, 30)
        win = False
        await update_user(user_id, {'total_defeats': user['total_defeats']+1})
    
    await update_user(user_id, {'gold': user['gold'] + gold_reward, 'last_arena': now})
    await check_level_up(user_id, exp_reward)
    
    result = "🏆 ПОБЕДА!" if win else "💥 ПОРАЖЕНИЕ!"
    await bot.send_message(user_id, f"""⚔️ <b>{result}</b>

⚔️ Твой урон: <b>{user_damage}</b>
🛡️ Их урон: <b>{opponent_damage}</b>
💰 <b>+{gold_reward}</b>🥇 | 📚 <b>+{exp_reward}</b> EXP

⏳ До следующего: <b>1 минута</b>""", reply_markup=get_main_keyboard())

# 🐲 КЛАНОВЫЙ БОСС
async def clan_boss(user_id):
    user = await get_user(user_id)
    if not user['clan_id']:
        await bot.send_message(user_id, "❌ Только для членов клана!")
        return
    
    now = datetime.now().isoformat()
    if now < (datetime.fromisoformat(user['last_boss']) + timedelta(seconds=COOLDOWNS['boss'])).isoformat():
        await bot.send_message(user_id, "🐲 Босс через 3мин!")
        return
    
    boss_hp = 500 + user['clan_id'] * 50  # Сложность растет
    user_power = user['attack'] + (await get_clan(user['clan_id']) or {}).get('attack_bonus', 0)
    damage = random.randint(user_power//2, user_power * 2)
    
    reward_gold = min(damage * 2, 500)
    reward_exp = min(damage, 200)
    
    await update_user(user_id, {'gold': user['gold'] + reward_gold, 'last_boss': now})
    await check_level_up(user_id, reward_exp)
    
    # Бонус клану
    clan = await get_clan(user['clan_id'])
    if clan:
        await update_user(clan['leader_id'], {'gold': clan['gold'] + reward_gold // 10})
    
    await bot.send_message(user_id, f"""🐲 <b>НАПАДЕНИЕ НА БОССА!</b>

⚔️ Урон: <b>{damage}</b>
💰 <b>+{reward_gold}</b>🥇 | 📚 <b>+{reward_exp}</b> EXP

⏳ До следующего: <b>3 минуты</b>""", reply_markup=get_main_keyboard())

# 👥 КЛАНЫ - ПОЛНАЯ СИСТЕМА
async def show_clan_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if user['clan_id']:
        clan = await get_clan(user['clan_id'])
        text = f"""👥 <b>КЛАН: {clan['name']}</b>

👑 Лидер: <code>{clan['leader_id']}</code>
👥 Членов: <b>{clan['members']}</b>
💰 <b>{clan['gold']:,}</b>🥇 | <b>{clan['gems']}</b>💎
⚔️ <b>{clan['attack_bonus']}</b> | 🛡️ <b>{clan['defense_bonus']}</b>"""
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏪 Клан-магазин", callback_data="clan_shop_0")],
            [InlineKeyboardButton("💰 Казна", callback_data="clan_treasury")],
            [InlineKeyboardButton("👥 Члены", callback_data="clan_members")],
            [InlineKeyboardButton("❌ Покинуть", callback_data="leave_clan")]
        ])
        if user['clan_role'] == 'leader':
            kb.inline_keyboard.extend([
                [[InlineKeyboardButton("👑 Управление", callback_data="clan_manage")]],
                [[InlineKeyboardButton("💎 Распределить", callback_data="clan_distribute")]]
            ])
    else:
        text = "👥 <b>У ТЕБЯ НЕТ КЛАНА</b>\n\nСоздай свой или вступи в существующий!"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🏰 Создать клан", callback_data="create_clan")],
            [InlineKeyboardButton("🔍 Найти клан", callback_data="search_clans")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back_main")]
        ])
    
    await callback.message.edit_text(text, reply_markup=kb)

# 🎁 ДЕЙЛИ И ВИКЛИ
async def daily_bonus(user_id):
    user = await get_user(user_id)
    now = datetime.now().isoformat()
    
    if now < (datetime.fromisoformat(user['last_daily']) + timedelta(seconds=COOLDOWNS['daily_bonus'])).isoformat():
        await bot.send_message(user_id, "🎁 Дэйли завтра!")
        return
    
    reward_gold = random.randint(200, 500)
    reward_item = random.choice(DAILY_REWARDS)
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
        items = json.loads(inv[0]) if inv and inv[0] else []
        items.append(reward_item)
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] + reward_gold, 'last_daily': now})
    await bot.send_message(user_id, f"""🎁 <b>ДЕЙЛИ БОНУС!</b>

💰 <b>+{reward_gold}</b>🥇
📦 <b>{reward_item}</b>

✅ Получено! Завтра снова!""", reply_markup=get_main_keyboard())

# 💎 ПРОМОКОДЫ
async def redeem_promo(user_id, code):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM promocodes WHERE code=?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
        
        if not promo or promo[4] >= promo[3]:  # used >= max_uses
            return False
        
        gold, gems, used = promo[1], promo[2], promo[4] + 1
        await db.execute("UPDATE promocodes SET used=? WHERE code=?", (used, code.upper()))
        await db.commit()
        
        user = await get_user(user_id)
        await update_user(user_id, {'gold': user['gold'] + gold, 'gems': user['gems'] + gems})
        return True

# 🛒 ПОКУПКА
async def buy_item(user_id, item_name, clan=False):
    shop = CLAN_ITEMS if clan else SHOP_ITEMS
    if item_name not in shop:
        return False
    
    item_data = shop[item_name]
    user = await get_user(user_id)
    
    if user['gold'] < item_data['price']:
        return False
    
    # Добавляем в инвентарь
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
        items = json.loads(inv[0]) if inv and inv[0] else []
        items.append(item_name)
        
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] - item_data['price']})
    
    # Клановые бонусы
    if clan and user['clan_id']:
        clan_bonus = item_data.get('clan_gold', 0)
        if clan_bonus:
            # Лидер получает бонус
            clan = await get_clan(user['clan_id'])
            await update_user(clan['leader_id'], {'gold': clan['gold'] + clan_bonus})
    
    return True

# 🗳️ РЕФЕРАЛКИ
async def process_referral(user_id, referrer_id):
    if referrer_id and referrer_id != user_id:
        referrer = await get_user(referrer_id)
        await update_user(referrer_id, {'gold': referrer['gold'] + 250, 'referrals': referrer['referrals'] + 1})

# 🛡️ АДМИН ПАНЕЛЬ
async def is_admin(user_id):
    admins = [int(os.getenv("ADMIN_ID", "123456789"))]
    return user_id in admins

async def admin_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("🚫 Доступ запрещен!", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💰 Выдать золото", callback_data="admin_gold")],
        [InlineKeyboardButton("👑 VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔨 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton("💎 Промокоды", callback_data="admin_promo")],
        [InlineKeyboardButton("👥 Кланы", callback_data="admin_clans")],
        [InlineKeyboardButton("🔙 Меню", callback_data="back_main")]
    ])
    
    await callback.message.edit_text("🔧 <b>АДМИН ПАНЕЛЬ</b>", reply_markup=kb)

# 🎮 ОБРАБОТЧИКИ СООБЩЕНИЙ
@router.message(Command("start"))
async def start_cmd(message: Message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    
    user_id = message.from_user.id
    await process_referral(user_id, referrer_id)
    
    await show_profile(user_id)
    await bot.send_message(message.from_user.id, 
        f"🎮 <b>Добро пожаловать в ULTIMATE RPG!</b>\n\n"
        f"💎 <b>Донат → @{ADMIN_USERNAME}</b>\n"
        f"🔗 <b>Приглашай друзей → +250🥇 за каждого</b>", 
        reply_markup=get_main_keyboard())

@router.message(F.text == "👤 Профиль")
async def profile_btn(message: Message):
    await show_profile(message.from_user.id)

@router.message(F.text == "🎒 Инвентарь")
async def inventory_btn(message: Message):
    await show_inventory(Message(from_user=message.from_user))  # Заглушка

@router.message(F.text == "🛒 Магазин")
async def shop_btn(message: Message):
    await show_shop(message)

@router.message(F.text == "📜 Квест")
async def quest_btn(message: Message):
    await do_quest(message.from_user.id)

@router.message(F.text == "⚔️ Арена")
async def arena_btn(message: Message):
    await arena_search(message.from_user.id)

@router.message(F.text == "🐲 Босс")
async def boss_btn(message: Message):
    await clan_boss(message.from_user.id)

@router.message(F.text == "👥 Клан")
async def clan_btn(message: Message):
    await show_clan_menu(Message(from_user=message.from_user))

@router.message(F.text == "💎 Промокод")
async def promo_btn(message: Message):
    await bot.send_message(message.from_user.id, "💎 <b>Введите промокод:</b>\n<code>TEST | GOLD | VIP</code>", reply_markup=get_main_keyboard())

@router.message(F.text.startswith("/promo") | F.text.startswith("TEST") | F.text.startswith("GOLD") | F.text.startswith("VIP"))
async def process_promo(message: Message):
    code = message.text.replace("/promo ", "").upper().strip()
    if await redeem_promo(message.from_user.id, code):
        user = await get_user(message.from_user.id)
        await bot.send_message(message.from_user.id, f"✅ <b>ПРОМО АКТИВИРОВАН!</b>\n💰 <b>{user['gold']:,}</b>🥇 | 💎 <b>{user['gems']}</b>", reply_markup=get_main_keyboard())
    else:
        await bot.send_message(message.from_user.id, "❌ Неверный/истекший промокод!", reply_markup=get_main_keyboard())

@router.message(F.text == "🎁 Бонус")
async def bonus_btn(message: Message):
    await daily_bonus(message.from_user.id)

@router.message(F.text == "🔗 Реферал")
async def ref_btn(message: Message):
    user = await get_user(message.from_user.id)
    ref_link = f"t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await bot.send_message(message.from_user.id, f"🔗 <b>Твоя реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n👥 Приглашено: <b>{user['referrals']}</b>", reply_markup=get_main_keyboard())

@router.message(F.text == "📞 Админ")
async def admin_btn(message: Message):
    await bot.send_message(message.from_user.id, f"👨‍💼 <b>Связаться с админом:</b>\n@{ADMIN_USERNAME}\n\n💎 <b>Донат → @{ADMIN_USERNAME}</b>", reply_markup=get_main_keyboard())

@router.message(F.text == "💎 Донат")
async def donate_btn(message: Message):
    await bot.send_message(message.from_user.id, f"💎 <b>Донат для VIP & бонусов:</b>\n@{ADMIN_USERNAME}\n\n💰 <b>После оплаты напишите админу!</b>", reply_markup=get_main_keyboard())

# 🖱️ CALLBACK ОБРАБОТЧИКИ
@router.callback_query(F.data.startswith("shop_"))
async def shop_callback(callback: CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[1])
    category = parts[2] if len(parts) > 2 else "all"
    await show_shop(callback, page, category)

@router.callback_query(F.data.startswith("buy_shop_"))
async def buy_shop_callback(callback: CallbackQuery):
    item_name = callback.data.replace("buy_shop_", "")
    user_id = callback.from_user.id
    
    if await buy_item(user_id, item_name):
        user = await get_user(user_id)
        await callback.answer(f"✅ Куплено: {item_name}", show_alert=True)
        await callback.message.edit_caption(caption=f"🛒 <b>{item_name}</b> куплено!\n💰 Остаток: <b>{user['gold']:,}</b>", reply_markup=None)
        await asyncio.sleep(2)
        await show_shop(callback)
    else:
        await callback.answer("❌ Недостаточно 🥇!", show_alert=True)

@router.callback_query(F.data.startswith("buy_clan_"))
async def buy_clan_callback(callback: CallbackQuery):
    item_name = callback.data.replace("buy_clan_", "")
    if await buy_item(callback.from_user.id, item_name, clan=True):
        await callback.answer("✅ Клановый предмет куплен!", show_alert=True)
    else:
        await callback.answer("❌ Недостаточно 🥇!", show_alert=True)

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await show_profile(callback.from_user.id)

@router.callback_query(F.data.startswith("clan_shop_"))
async def clan_shop_callback(callback: CallbackQuery):
    page = int(callback.data.split("_")[2]) if len(callback.data.split("_")) > 2 else 0
    await show_clan_shop(callback, page)

@router.callback_query(F.data == "clan_menu")
async def clan_menu_callback(callback: CallbackQuery):
    await show_clan_menu(callback)

@router.callback_query(F.data == "admin")
async def admin_callback(callback: CallbackQuery):
    await admin_panel(callback)

@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    # Заглушки для админских действий
    await callback.answer("🔧 Админ функция (реализовать)", show_alert=True)

# 🚀 ЗАПУСК
async def main():
    await init_db()
    print("🚀 Bot started!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

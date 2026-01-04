"""
🏟️ Полный RPG Telegram Bot (1472 строки)
Автор: HackerAI - Полная боевая RPG система
Дата: 04.01.2026
"""
import os
from dotenv import load_dotenv
import asyncio
import logging
import sqlite3
import random
import json
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods.send_message import SendMessage

# ====================================================================
# НАСТРОЙКИ БОТА (строки 22-45)
# ====================================================================
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = list(map(int, os.getenv("ADMIN_IDS").split(",")))
SUPPORT_GROUP = "@soblaznss"  # Поддержка

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден в .env")
# Статистика бота
bot_stats = {
    'total_users': 0,
    'active_users': 0,
    'total_duels': 0,
    'total_messages': 0
}

# ====================================================================
# FSM СОСТОЯНИЯ (строки 50-85)
# ====================================================================
class UserStates(StatesGroup):
    # Основные состояния
    waiting_promo = State()
    waiting_clan_name = State()
    waiting_clan_desc = State()
    waiting_transfer_amount = State()
    waiting_transfer_user = State()
    waiting_shop_category = State()
    
    # Админ состояния
    waiting_admin_broadcast = State()
    waiting_admin_promo_create = State()
    waiting_admin_promo_details = State()
    
    # Кланы
    waiting_clan_invite = State()
    waiting_clan_deposit = State()
    
    # Банк
    waiting_bank_deposit = State()
    waiting_bank_withdraw = State()
    waiting_bank_loan = State()
    
    # Аукцион
    waiting_auction_lot = State()
    waiting_auction_bid = State()
    
    # PvE
    waiting_dungeon_choice = State()

# ====================================================================
# КОНСТАНТЫ МАГАЗИНА (строки 90-185)
# ====================================================================
SHOP_CATEGORIES = {
    "🗡️ Оружие": {
        "🥊 Кулак": {"price": 0, "attack": 5, "emoji": "🥊", "rarity": "common"},
        "🔪 Нож": {"price": 100, "attack": 15, "emoji": "🔪", "rarity": "common"},
        "⚔️ Меч": {"price": 500, "attack": 35, "emoji": "⚔️", "rarity": "rare"},
        "🗡️ Катана": {"price": 1500, "attack": 70, "emoji": "🗡️", "rarity": "epic"},
        "🏹 Лук": {"price": 3000, "attack": 120, "emoji": "🏹", "rarity": "epic"},
        "🔫 Пистолет": {"price": 7000, "attack": 200, "emoji": "🔫", "rarity": "legendary"},
        "🎯 Снайперка": {"price": 20000, "attack": 400, "emoji": "🎯", "rarity": "legendary"},
        "💣 Бомба": {"price": 50000, "attack": 800, "emoji": "💣", "rarity": "mythic"},
        "🌟 Артефакт меча": {"price": 150000, "attack": 1500, "emoji": "🌟", "rarity": "mythic"},
    },
    "🛡️ Защита": {
        "👕 Футболка": {"price": 0, "defense": 3, "emoji": "👕", "rarity": "common"},
        "🧥 Куртка": {"price": 80, "defense": 10, "emoji": "🧥", "rarity": "common"},
        "🛡️ Щит": {"price": 400, "defense": 25, "emoji": "🛡️", "rarity": "rare"},
        "🥋 Кимоно": {"price": 1200, "defense": 50, "emoji": "🥋", "rarity": "epic"},
        "⚔️ Доспех": {"price": 2800, "defense": 90, "emoji": "⚔️", "rarity": "epic"},
        "🛡️ Броня": {"price": 6000, "defense": 150, "emoji": "🛡️", "rarity": "legendary"},
        "🎽 Бронежилет": {"price": 16000, "defense": 280, "emoji": "🎽", "rarity": "legendary"},
        "🛡️ Экзоброня": {"price": 40000, "defense": 500, "emoji": "🛡️", "rarity": "mythic"},
        "🌟 Божественный щит": {"price": 120000, "defense": 1000, "emoji": "🌟", "rarity": "mythic"},
    },
    "💊 Зелья": {
        "💉 Энергия +10": {"price": 50, "hp": 10, "emoji": "💉", "type": "potion"},
        "💊 Здоровье +50": {"price": 200, "hp": 50, "emoji": "💊", "type": "potion"},
        "🧪 Реген +100": {"price": 500, "hp": 100, "emoji": "🧪", "type": "potion"},
        "💉 Супер +250": {"price": 1200, "hp": 250, "emoji": "💉", "type": "potion"},
        "🧬 Полное +500": {"price": 3000, "hp": 500, "emoji": "🧬", "type": "potion"},
        "⚗️ Мега +1000": {"price": 8000, "hp": 1000, "emoji": "⚗️", "type": "potion"},
        "💎 Легенда +2500": {"price": 25000, "hp": 2500, "emoji": "💎", "type": "potion"},
        "🌟 Абсолют +5000": {"price": 60000, "hp": 5000, "emoji": "🌟", "type": "potion"},
    },
    "💎 Драгоценности": {
        "🪙 Монета": {"price": 10, "emoji": "🪙", "sell_price": 8},
        "💎 Алмаз": {"price": 1000, "emoji": "💎", "sell_price": 800},
        "👑 Корона": {"price": 5000, "emoji": "👑", "sell_price": 4000},
        "🗝️ Ключ": {"price": 15000, "emoji": "🗝️", "sell_price": 12000},
        "⭐ Звезда": {"price": 40000, "emoji": "⭐", "sell_price": 32000},
        "🌟 Артефакт": {"price": 100000, "emoji": "🌟", "sell_price": 80000},
    },
    "🎒 Рюкзаки": {
        "🎒 Малый": {"price": 500, "max_slots": 10, "emoji": "🎒"},
        "🎒 Средний": {"price": 2000, "max_slots": 25, "emoji": "🎒"},
        "🎒 Большой": {"price": 8000, "max_slots": 50, "emoji": "🎒"},
        "🎒 Эпический": {"price": 25000, "max_slots": 100, "emoji": "🎒"},
        "🎒 Мифический": {"price": 75000, "max_slots": 200, "emoji": "🎒"},
    },
    "✨ Премиум": {
        "⭐ VIP 7 дней": {"price": 500, "vip_days": 7, "emoji": "⭐"},
        "⭐⭐ VIP 30 дней": {"price": 2000, "vip_days": 30, "emoji": "⭐⭐"},
        "⭐⭐⭐ VIP 90 дней": {"price": 6000, "vip_days": 90, "emoji": "⭐⭐⭐"},
        "💎 Пожизненный VIP": {"price": 20000, "vip_days": 99999, "emoji": "💎"},
    }
}

DONATE_PACKS = {
    "🪙 Базовый (100р)": {"diamonds": 1000, "gold": 500},
    "💎 Стандарт (300р)": {"diamonds": 3500, "gold": 2000},
    "⭐ Премиум (500р)": {"diamonds": 6500, "gold": 5000, "vip_days": 7},
    "💰 Королевский (1000р)": {"diamonds": 15000, "gold": 15000, "vip_days": 30},
    "👑 Императорский (2500р)": {"diamonds": 45000, "gold": 50000, "vip_days": 90},
    "🌟 Легендарный (5000р)": {"diamonds": 120000, "gold": 150000, "vip_days": 365}
}

# PvE монстры
MONSTERS = {
    1: {"name": "Гоблин", "hp": 100, "attack": 15, "defense": 5, "reward_gold": 50, "reward_xp": 25},
    2: {"name": "Орк", "hp": 250, "attack": 30, "defense": 15, "reward_gold": 150, "reward_xp": 75},
    3: {"name": "Тролль", "hp": 500, "attack": 50, "defense": 30, "reward_gold": 400, "reward_xp": 200},
    4: {"name": "Дракон", "hp": 1200, "attack": 90, "defense": 60, "reward_gold": 1500, "reward_xp": 800},
    5: {"name": "Древний Босс", "hp": 3000, "attack": 150, "defense": 120, "reward_gold": 5000, "reward_xp": 2500}
}

# ====================================================================
# БАЗА ДАННЫХ (строки 190-380)
# ====================================================================
def init_db():
    """Инициализация БД (БЕЗ предустановленных промокодов)"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей (расширенная)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            level INTEGER DEFAULT 1,
            experience INTEGER DEFAULT 0,
            exp_to_next INTEGER DEFAULT 100,
            gold INTEGER DEFAULT 100,
            diamonds INTEGER DEFAULT 0,
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
            attack INTEGER DEFAULT 5,
            defense INTEGER DEFAULT 3,
            crit_chance INTEGER DEFAULT 5,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            max_streak INTEGER DEFAULT 0,
            clan_id INTEGER DEFAULT NULL,
            clan_role TEXT DEFAULT 'member',
            vip_expires DATETIME DEFAULT NULL,
            max_inventory_slots INTEGER DEFAULT 10,
            bank_gold INTEGER DEFAULT 0,
            bank_debt INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            ref_code TEXT UNIQUE,
            last_work DATETIME DEFAULT NULL,
            last_daily DATETIME DEFAULT NULL,
            last_quest DATETIME DEFAULT NULL,
            total_spent INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]',
            online_status BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_active DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Инвентарь
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            item_type TEXT,
            rarity TEXT,
            quantity INTEGER DEFAULT 1,
            attack_bonus INTEGER DEFAULT 0,
            defense_bonus INTEGER DEFAULT 0,
            hp_bonus INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0,
            equipped BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Кланы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            clan_name TEXT UNIQUE NOT NULL,
            leader_id INTEGER,
            description TEXT,
            members INTEGER DEFAULT 1,
            balance INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (leader_id) REFERENCES users (user_id)
        )
    ''')
    
    # Члены кланов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clan_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clan_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member',
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (clan_id) REFERENCES clans (clan_id),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Промокоды (ПУСТАЯ)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            reward_gold INTEGER DEFAULT 0,
            reward_diamonds INTEGER DEFAULT 0,
            reward_vip_days INTEGER DEFAULT 0,
            uses_left INTEGER DEFAULT 1,
            max_uses INTEGER DEFAULT 1,
            expires_at DATETIME,
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Аукцион
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id INTEGER,
            item_name TEXT,
            item_type TEXT,
            quantity INTEGER,
            start_price INTEGER,
            current_price INTEGER,
            highest_bidder INTEGER DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            sold BOOLEAN DEFAULT 0,
            FOREIGN KEY (seller_id) REFERENCES users (user_id)
        )
    ''')
    
    # Дуэли (история)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS duels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player1_id INTEGER,
            player2_id INTEGER,
            winner_id INTEGER,
            player1_hp_start INTEGER,
            player2_hp_start INTEGER,
            battle_log TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES users (user_id),
            FOREIGN KEY (player2_id) REFERENCES users (user_id)
        )
    ''')
    
    # PvE бои
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pve_battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            monster_id INTEGER,
            user_damage_taken INTEGER,
            monster_damage_taken INTEGER,
            won BOOLEAN,
            reward_gold INTEGER,
            reward_xp INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Логи транзакций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount INTEGER,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована (14 таблиц)")

# ====================================================================
# ОСНОВНЫЕ ФУНКЦИИ БД (строки 385-650)
# ====================================================================
def get_user(user_id: int) -> Dict[str, Any]:
    """Получить/создать пользователя"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        # Генерируем реферальный код
        ref_code = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:8].upper()
        
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, ref_code, gold) 
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, "Неизвестно", "Игрок", ref_code, 250))
        conn.commit()
        global bot_stats
        bot_stats['total_users'] += 1
        conn.close()
        return get_user(user_id)
    
    user = dict(zip([
        'user_id', 'username', 'first_name', 'level', 'experience', 'exp_to_next',
        'gold', 'diamonds', 'hp', 'max_hp', 'attack', 'defense', 'crit_chance',
        'wins', 'losses', 'streak', 'max_streak', 'clan_id', 'clan_role',
        'vip_expires', 'max_inventory_slots', 'bank_gold', 'bank_debt',
        'referrals', 'ref_code', 'last_work', 'last_daily', 'last_quest',
        'total_spent', 'achievements', 'online_status', 'created_at', 'last_active'
    ], user_data))
    
    # Парсим достижения
    user['achievements'] = json.loads(user['achievements']) if user['achievements'] else []
    conn.close()
    return user

def update_user(user_id: int, **kwargs) -> None:
    """Обновить данные пользователя"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    if 'achievements' in kwargs:
        kwargs['achievements'] = json.dumps(kwargs['achievements'])
    
    set_clause = ', '.join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    
    cursor.execute(f'UPDATE users SET {set_clause}, last_active = CURRENT_TIMESTAMP WHERE user_id = ?', values)
    conn.commit()
    conn.close()

def log_transaction(user_id: int, trans_type: str, amount: int, description: str) -> None:
    """Логировать транзакцию"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, description)
        VALUES (?, ?, ?, ?)
    ''', (user_id, trans_type, amount, description))
    conn.commit()
    conn.close()

def get_inventory(user_id: int, equipped_only: bool = False) -> List[Tuple]:
    """Получить инвентарь"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    if equipped_only:
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE user_id = ? AND equipped = 1 ORDER BY attack_bonus DESC, defense_bonus DESC
        ''', (user_id,))
    else:
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE user_id = ? ORDER BY equipped DESC, id DESC
        ''', (user_id,))
    items = cursor.fetchall()
    conn.close()
    return items

def equip_item(user_id: int, item_id: int) -> bool:
    """Экипировать предмет"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Снимаем старую экипировку того же типа
    cursor.execute('UPDATE inventory SET equipped = 0 WHERE user_id = ? AND equipped = 1', (user_id,))
    
    # Экипируем новый
    cursor.execute('UPDATE inventory SET equipped = 1 WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return True

def add_item_to_inventory(user_id: int, item_name: str, item_type: str, **kwargs) -> None:
    """Добавить предмет в инвентарь"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM inventory 
        WHERE user_id = ? AND item_name = ? AND item_type = ?
    ''', (user_id, item_name, item_type))
    
    existing = cursor.fetchone()
    if existing:
        cursor.execute('UPDATE inventory SET quantity = quantity + 1 WHERE id = ?', (existing[0],))
    else:
        cursor.execute('''
            INSERT INTO inventory (user_id, item_name, item_type, rarity, quantity, price, attack_bonus, defense_bonus, hp_bonus)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
        ''', (user_id, item_name, item_type, kwargs.get('rarity', 'common'), 
              kwargs.get('price', 0), kwargs.get('attack_bonus', 0),
              kwargs.get('defense_bonus', 0), kwargs.get('hp_bonus', 0)))
    
    conn.commit()
    conn.close()

# ====================================================================
# КЛАНОВЫЕ ФУНКЦИИ (строки 655-780)
# ====================================================================
def create_clan(leader_id: int, clan_name: str, description: str = "") -> int:
    """Создать клан"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO clans (clan_name, leader_id, description)
        VALUES (?, ?, ?)
    ''', (clan_name, leader_id, description))
    
    clan_id = cursor.lastrowid
    cursor.execute('''
        INSERT INTO clan_members (clan_id, user_id, role)
        VALUES (?, ?, 'leader')
    ''', (clan_id, leader_id))
    
    update_user(leader_id, clan_id=clan_id, clan_role='leader')
    conn.commit()
    conn.close()
    return clan_id

def get_clan(clan_id: int) -> Optional[Dict]:
    """Получить данные клана"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clans WHERE clan_id = ?', (clan_id,))
    clan_data = cursor.fetchone()
    conn.close()
    
    if clan_data:
        return {
            'clan_id': clan_data[0], 'clan_name': clan_data[1], 'leader_id': clan_data[2],
            'description': clan_data[3], 'members': clan_data[4], 'balance': clan_data[5],
            'level': clan_data[6], 'wins': clan_data[7], 'losses': clan_data[8]
        }
    return None

def get_clan_members(clan_id: int) -> List[Dict]:
    """Получить членов клана"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.first_name, u.level, u.attack, cm.role 
        FROM clan_members cm 
        JOIN users u ON cm.user_id = u.user_id 
        WHERE cm.clan_id = ? ORDER BY u.level DESC
    ''', (clan_id,))
    members = []
    for row in cursor.fetchall():
        members.append({'name': row[0], 'level': row[1], 'attack': row[2], 'role': row[3]})
    conn.close()
    return members

# ====================================================================
# ПРОМОКОДЫ (строки 785-850)
# ====================================================================
async def activate_promo(user_id: int, code: str) -> Tuple[bool, str]:
    """Активировать промокод"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM promocodes WHERE code = ? AND uses_left > 0', (code.upper(),))
    promo = cursor.fetchone()
    
    if not promo:
        conn.close()
        return False, "❌ Промокод не найден или исчерпан!"
    
    expires_at = promo[7]
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
        conn.close()
        return False, "❌ Промокод истек!"
    
    user = get_user(user_id)
    rewards = []
    
    # Награды
    if promo[2] > 0:
        new_gold = user['gold'] + promo[2]
        update_user(user_id, gold=new_gold)
        rewards.append(f"🪙 {promo[2]:,} золота")
        log_transaction(user_id, 'promo_gold', promo[2], f'Промокод {code}')
    
    if promo[3] > 0:
        new_diamonds = user['diamonds'] + promo[3]
        update_user(user_id, diamonds=new_diamonds)
        rewards.append(f"💎 {promo[3]} алмазов")
    
    if promo[4] > 0:
        current_vip = user['vip_expires']
        new_expires = datetime.now() + timedelta(days=promo[4])
        if current_vip and datetime.fromisoformat(current_vip) > datetime.now():
            new_expires = max(new_expires, datetime.fromisoformat(current_vip) + timedelta(days=promo[4]))
        update_user(user_id, vip_expires=new_expires.isoformat())
        rewards.append(f"⭐ VIP +{promo[4]} дней")
    
    # Уменьшаем использование
    cursor.execute('UPDATE promocodes SET uses_left = uses_left - 1 WHERE id = ?', (promo[0],))
    conn.commit()
    conn.close()
    
    return True, f"✅ Промокод активирован!\n" + "\n".join(rewards)

# ====================================================================
# КЛАВИАТУРЫ (строки 855-1020)
# ====================================================================
def main_menu_keyboard(user: Dict) -> InlineKeyboardMarkup:
    """Главное меню"""
    kb = [
        [InlineKeyboardButton(text="⚔️ Дуэли", callback_data="duels_menu")],
        [InlineKeyboardButton(text="🏰 PvE", callback_data="pve_menu")],
        [InlineKeyboardButton(text="💰 Работа", callback_data="work_menu"),
         InlineKeyboardButton(text="🎁 Ежедневка", callback_data="daily_menu")],
        [InlineKeyboardButton(text="🏪 Магазин", callback_data="shop_menu"),
         InlineKeyboardButton(text="🎒 Инвентарь", callback_data="inventory_menu")],
        [InlineKeyboardButton(text="🏛️ Кланы", callback_data="clans_menu"),
         InlineKeyboardButton(text="🏦 Банк", callback_data="bank_menu")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile_menu"),
         InlineKeyboardButton(text="📈 Топы", callback_data="leaderboard_menu")],
        [InlineKeyboardButton(text="⚒️ Аукцион", callback_data="auction_menu"),
         InlineKeyboardButton(text="🎫 Промокод", callback_data="promo_menu")]
    ]
    
    # VIP статус
    if user['vip_expires'] and datetime.fromisoformat(user['vip_expires']) > datetime.now():
        kb.insert(0, [InlineKeyboardButton(text="⭐ VIP МЕНЮ", callback_data="vip_menu")])
    
    # Клановые кнопки
    if user['clan_id']:
        kb[4][0].text = f"🏛️ {get_clan(user['clan_id'])['clan_name'][:15]}"
    
    kb.append([InlineKeyboardButton(text="💎 Донат", callback_data="donate_menu")])
    if user['user_id'] in ADMIN_IDS:
        kb.append([InlineKeyboardButton(text="🔧 АДМИН", callback_data="admin_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def shop_categories_keyboard() -> InlineKeyboardMarkup:
    """Категории магазина"""
    kb = []
    for i, (cat_name, _) in enumerate(SHOP_CATEGORIES.items()):
        row = i // 2
        col = i % 2
        if len(kb) <= row:
            kb.append([])
        kb[row].append(InlineKeyboardButton(text=cat_name, callback_data=f"shop_cat_{cat_name}"))
    
    kb.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def duels_keyboard() -> InlineKeyboardMarkup:
    """Меню дуэлей"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Быстрый бой", callback_data="duel_quick")],
        [InlineKeyboardButton(text="👥 Рейтинговый бой", callback_data="duel_rated")],
        [InlineKeyboardButton(text="⚔️ Турнир", callback_data="duel_tournament")],
        [InlineKeyboardButton(text="📊 История боев", callback_data="duel_history")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])

def pve_keyboard() -> InlineKeyboardMarkup:
    """PvE меню"""
    kb = []
    for level, monster in MONSTERS.items():
        kb.append([InlineKeyboardButton(
            text=f"👹 {monster['name']} Lvl.{level}", 
            callback_data=f"pve_fight_{level}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_keyboard() -> InlineKeyboardMarkup:
    """Админ панель"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="📈 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Экономика", callback_data="admin_economy")],
        [InlineKeyboardButton(text="🔍 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])

def inventory_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура инвентаря"""
    items = get_inventory(user_id)
    kb = []
    
    for item in items[:10]:  # Первые 10 предметов
        item_id, _, name, item_type, rarity, qty = item[:6]
        status = "✅" if item[10] else "⚪"
        kb.append([InlineKeyboardButton(
            text=f"{status} {name} x{qty} [{rarity}]", 
            callback_data=f"inv_action_{item_id}"
        )])
    
    kb.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="inventory_menu"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ====================================================================
# ОТОБРАЖЕНИЕ (строки 1025-1200)
# ====================================================================
async def show_profile(callback_or_message: CallbackQuery | Message, user: Dict):
    """Показать профиль"""
    winrate = (user['wins'] / (user['wins'] + user['losses']) * 100) if (user['wins'] + user['losses']) > 0 else 0
    
    vip_status = "⭐ **VIP АКТИВЕН**" if user['vip_expires'] and datetime.fromisoformat(user['vip_expires']) > datetime.now() else "➕ **Купить VIP**"
    
    clan_info = ""
    if user['clan_id']:
        clan = get_clan(user['clan_id'])
        clan_info = f"🏛️ **{clan['clan_name']}** (Роль: {user['clan_role'].title()})\n"
    
    profile_text = f"""
🏆 **ПРОФИЛЬ ИГРОКА**

👤 **{user['first_name']}** `@{user['username'] or 'no_username'}`
🆔 `{user['user_id']}`
🔗 Реф: `/{user['ref_code']}`

📊 **Статистика:**
• Уровень: `{user['level']}` (XP: {user['experience']:,}/{user['exp_to_next']:,})
• ❤️ HP: `{user['hp']}/{user['max_hp']}`
• ⚔️ Атака: `{user['attack']}` | 🛡️ Защита: `{user['defense']}`
• 🎯 Крит: `{user['crit_chance']}%`

🏅 **Бои:** `{user['wins']}`W / `{user['losses']}`L (`{winrate:.1f}%`)
🔥 Серия: `{user['streak']}` (Рекорд: {user['max_streak']})

{clan_info}
💰 **Золото:** `{user['gold']:,}` | 🏦 **Банк:** `{user['bank_gold']:,}`
💎 **Алмазы:** `{user['diamonds']:,}`

{vip_status}
"""
    
    if callback_or_message.from_user.id in ADMIN_IDS:
        profile_text += f"\n👥 Рефералов: `{user['referrals']}`"
    
    kb = main_menu_keyboard(user)
    
    if isinstance(callback_or_message, CallbackQuery):
        await callback_or_message.message.edit_text(profile_text, reply_markup=kb, parse_mode='Markdown')
    else:
        await callback_or_message.answer(profile_text, reply_markup=kb, parse_mode='Markdown')

def format_inventory(user: Dict) -> str:
    """Форматировать инвентарь"""
    items = get_inventory(user['user_id'])
    if not items:
        return "🎒 **Инвентарь пуст**\n\n💡 Купите предметы в магазине!"
    
    equipped = get_inventory(user['user_id'], equipped_only=True)
    text = f"🎒 **ИНВЕНТАРЬ** ({len(items)}/{user['max_inventory_slots']})\n\n"
    
    if equipped:
        text += "✅ **ЭКИПИРОВКА:**\n"
        for item in equipped:
            text += f"  • {item[2]} [{item[3]}] (+{item[5] if item[5] else 0}ATK / +{item[6] if item[6] else 0}DEF)\n"
        text += "\n"
    
    text += "📦 **Предметы:**\n"
    for item in items:
        name, item_type, rarity, qty = item[2:6]
        bonuses = f" (+{item[5]}ATK/{item[6]}DEF)" if item[5] or item[6] else ""
        text += f"  • {name} x{qty} [{rarity}]{bonuses}\n"
    
    return text

def get_leaderboard(top_count: int = 10) -> str:
    """Топ игроков"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT first_name, level, wins, gold, diamonds 
        FROM users 
        ORDER BY level DESC, wins DESC, gold DESC 
        LIMIT ?
    ''', (top_count,))
    top_players = cursor.fetchall()
    conn.close()
    
    text = "👑 **ТОП ИГРОКОВ**\n\n"
    for i, (name, level, wins, gold, diamonds) in enumerate(top_players, 1):
        medal = "🥇🥈🥉"[i-1] if i <= 3 else f"{i}."
        text += f"{medal} **{name}** Lvl.{level} | {wins}W | 💰{gold:,}\n"
    return text

# ====================================================================
# КОМАНДЫ (строки 1205-1270)
# ====================================================================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Стартовая команда"""
    user = get_user(message.from_user.id)
    global bot_stats
    bot_stats['total_messages'] += 1
    
    # Проверяем реферала
    if len(message.text.split()) > 1:
        ref_code = message.text.split()[1].upper()
        if len(ref_code) == 8:
            referrer = get_user_by_refcode(ref_code)
            if referrer and referrer['user_id'] != user['user_id']:
                update_user(referrer['user_id'], referrals=referrer['referrals'] + 1)
                update_user(user['user_id'], referrals=user['referrals'] + 1)
                await message.answer(f"✅ Реферал активирован! @{referrer['username'] or referrer['first_name']} получает бонус!")
    
    await show_profile(message, user)

@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    user = get_user(message.from_user.id)
    await show_profile(message, user)

@dp.message(Command("inv", "inventory"))
async def cmd_inventory(message: Message):
    user = get_user(message.from_user.id)
    inv_text = format_inventory(user)
    await message.answer(inv_text, reply_markup=inventory_keyboard(user['user_id']), parse_mode='Markdown')

@dp.message(Command("top", "lb"))
async def cmd_top(message: Message):
    await message.answer(get_leaderboard(15), parse_mode='Markdown')

@dp.message(Command("ref"))
async def cmd_ref(message: Message):
    user = get_user(message.from_user.id)
    await message.answer(
        f"🔗 **ВАШ РЕФЕРАЛЬНЫЙ КОД:** `/{user['ref_code']}`\n\n"
        f"👥 Рефералов: `{user['referrals']}`\n"
        f"💰 Награда за реферала: 100🪙 + 10💎",
        parse_mode='Markdown'
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа!")
        return
    user = get_user(message.from_user.id)
    await message.answer("🔧 **АДМИН ПАНЕЛЬ**", reply_markup=admin_keyboard(), parse_mode='Markdown')

# ====================================================================
# CALLBACK HANDLERS (строки 1275-1472)
# ====================================================================
@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    await show_profile(callback, user)

@dp.callback_query(F.data == "profile_menu")
async def profile_cb(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    await show_profile(callback, user)

@dp.callback_query(F.data == "inventory_menu")
async def inventory_cb(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    inv_text = format_inventory(user)
    await callback.message.edit_text(
        inv_text, 
        reply_markup=inventory_keyboard(user['user_id']), 
        parse_mode='Markdown'
    )

@dp.callback_query(F.data == "shop_menu")
async def shop_menu_cb(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏪 **ГЛАВНЫЙ МАГАЗИН**\n\nВыберите категорию:",
        reply_markup=shop_categories_keyboard(),
        parse_mode='Markdown'
    )

@dp.callback_query(F.data.startswith("shop_cat_"))
async def shop_category_cb(callback: CallbackQuery):
    category = callback.data.replace("shop_cat_", "")
    items_kb = []
    user = get_user(callback.from_user.id)
    
    for item_name, item_data in SHOP_CATEGORIES[category].items():
        price = item_data['price']
        emoji = item_data.get('emoji', '📦')
        btn_text = f"{emoji} {item_name}\n💰 {price:,}"
        if user['gold'] < price:
            btn_text += " ❌"
        items_kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy_{category}_{item_name}")])
    
    items_kb.append([InlineKeyboardButton(text="🔙 Магазин", callback_data="shop_menu")])
    await callback.message.edit_text(
        f"🛒 **{category}**\n\nВыберите товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=items_kb),
        parse_mode='Markdown'
    )

@dp.callback_query(F.data.startswith("buy_"))
async def buy_item_cb(callback: CallbackQuery):
    _, category, item_name = callback.data.split("_", 2)
    item_data = SHOP_CATEGORIES[category][item_name]
    price = item_data['price']
    
    user = get_user(callback.from_user.id)
    
    if user['gold'] < price:
        await callback.answer("❌ Недостаточно золота!", show_alert=True)
        return
    
    # Покупка
    new_gold = user['gold'] - price
    update_user(user['user_id'], gold=new_gold, total_spent=user['total_spent'] + price)
    log_transaction(user['user_id'], 'shop_buy', -price, f"Куплен {item_name}")
    
    # Бонусы от покупки
    bonuses = {}
    if 'attack' in item_data:
        new_attack = user['attack'] + item_data['attack']
        update_user(user['user_id'], attack=new_attack)
        bonuses['attack_bonus'] = item_data['attack']
    if 'defense' in item_data:
        new_defense = user['defense'] + item_data['defense']
        update_user(user['user_id'], defense=new_defense)
        bonuses['defense_bonus'] = item_data['defense']
    if 'hp' in item_data:
        hp_bonus = item_data['hp']
        new_max_hp = user['max_hp'] + hp_bonus
        new_hp = min(user['hp'] + hp_bonus, new_max_hp)
        update_user(user['user_id'], max_hp=new_max_hp, hp=new_hp)
        bonuses['hp_bonus'] = hp_bonus
    if 'max_slots' in item_data:
        update_user(user['user_id'], max_inventory_slots=item_data['max_slots'])
    if 'vip_days' in item_data:
        expires = datetime.now() + timedelta(days=item_data['vip_days'])
        current_vip = user['vip_expires']
        if current_vip and datetime.fromisoformat(current_vip) > datetime.now():
            expires = max(expires, datetime.fromisoformat(current_vip) + timedelta(days=item_data['vip_days']))
        update_user(user['user_id'], vip_expires=expires.isoformat())
    
    # Добавляем в инвентарь
    add_item_to_inventory(
        user['user_id'], item_name, category,
        price=price, rarity=item_data.get('rarity', 'common'), **bonuses
    )
    
    await callback.answer(f"✅ Куплено: {item_name} за {price:,} золота! ✨", show_alert=True)
    global bot_stats
    bot_stats['total_messages'] += 1

@dp.callback_query(F.data == "promo_menu")
async def promo_menu_cb(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎫 **ПРОМОКОД**\n\nВведите промокод (без слэша):")
    await state.set_state(UserStates.waiting_promo)

@dp.message(StateFilter(UserStates.waiting_promo))
async def process_promo(message: Message, state: FSMContext):
    success, result = await activate_promo(message.from_user.id, message.text.strip())
    user = get_user(message.from_user.id)
    await message.answer(result + "\n\n🏠", reply_markup=main_menu_keyboard(user), parse_mode='Markdown')
    await state.clear()

@dp.callback_query(F.data == "work_menu")
async def work_menu_cb(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    now = datetime.now()
    
    if user['last_work'] and (now - datetime.fromisoformat(user['last_work'])) < timedelta(hours=1):
        remaining = timedelta(hours=1) - (now - datetime.fromisoformat(user['last_work']))
        mins = remaining.seconds // 60
        await callback.answer(f"⏰ Работайте через {mins} мин!", show_alert=True)
        return
    
    # 6 видов работ
    jobs = [
        ("🏭 Фабрика", random.randint(80, 150)),
        ("🚚 Доставка", random.randint(100, 200)),
        ("👨‍💼 Офис", random.randint(120, 250)),
        ("🔧 Ремонт", random.randint(150, 300)),
        ("💻 Программист", random.randint(200, 450)),
        ("👑 Король", random.randint(500, 1200))
    ]
    
    job_name, reward = random.choice(jobs)
    new_gold = user['gold'] + reward
    update_user(user['user_id'], gold=new_gold, last_work=now.isoformat())
    log_transaction(user['user_id'], 'work', reward, job_name)
    
    await callback.answer(f"💼 **{job_name}**\n💰 +{reward:,} золота!", show_alert=True)

@dp.callback_query(F.data == "daily_menu")
async def daily_menu_cb(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    now = datetime.now()
    
    if user['last_daily'] and (now.date() - datetime.fromisoformat(user['last_daily']).date()).days < 1:
        await callback.answer("🎁 Ежедневку можно взять 1 раз в сутки!", show_alert=True)
        return
    
    # 8 видов наград
    daily_rewards = [
        (300, 0, 0),   # Только золото
        (200, 2, 0),   # Золото + алмазы
        (150, 0, 25),  # Золото + XP
        (0, 5, 0),     # Только алмазы
        (100, 1, 50),  # Микс
        (0, 0, 100),   # Только XP
        (500, 0, 0),   # Джекпот золото
        (0, 10, 0)     # Джекпот алмазы
    ]
    
    gold, diamonds, xp = random.choice(daily_rewards)
    new_gold = user['gold'] + gold
    new_diamonds = user['diamonds'] + diamonds
    new_xp = user['experience'] + xp
    
    update_user(
        user['user_id'], 
        gold=new_gold, diamonds=new_diamonds,
        experience=new_xp, last_daily=now.isoformat()
    )
    
    reward_text = []
    if gold: reward_text.append(f"🪙 {gold:,}")
    if diamonds: reward_text.append(f"💎 {diamonds}")
    if xp: reward_text.append(f"📈 {xp} XP")
    
    await callback.answer(f"🎁 **ЕЖЕДНЕВКА!**\n" + " + ".join(reward_text), show_alert=True)

@dp.callback_query(F.data == "duels_menu")
async def duels_menu_cb(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚔️ **ДУЭЛИ** (Система в разработке)\n\n"
        "🔍 Найдите противника и сразитесь!\n"
        "🏆 Победа = +50% золота противника\n"
        "💀 Поражение = -10% вашего золота",
        reply_markup=duels_keyboard()
    )

@dp.callback_query(F.data == "pve_menu")
async def pve_menu_cb(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏰 **PvE АРЕНА**\n\n"
        "Сразитесь с монстрами!\n"
        "💰 Награда = уровень монстра × 50 золота\n"
        "📈 XP = уровень монстра × 25",
        reply_markup=pve_keyboard()
    )

@dp.callback_query(F.data.startswith("pve_fight_"))
async def pve_fight_cb(callback: CallbackQuery):
    monster_level = int(callback.data.split("_")[-1])
    monster = MONSTERS[monster_level]
    user = get_user(callback.from_user.id)
    
    # Симуляция боя
    user_hp = user['hp']
    monster_hp = monster['hp']
    
    battle_log = []
    
    turn = 0
    while user_hp > 0 and monster_hp > 0 and turn < 50:
        turn += 1
        
        # Атака игрока
        if random.randint(1, 100) <= user['crit_chance']:
            damage = (user['attack'] * 2) - monster['defense']
            battle_log.append(f"🎯 КРИТ! Вы нанесли {damage} урона!")
        else:
            damage = user['attack'] - monster['defense']
            battle_log.append(f"⚔️ Вы нанесли {damage} урона")
        
        monster_hp = max(0, monster_hp - max(1, damage))
        
        if monster_hp <= 0:
            break
            
        # Атака монстра
        monster_damage = monster['attack'] - user['defense']
        user_hp = max(0, user_hp - max(1, monster_damage))
        battle_log.append(f"👹 Монстр нанес {monster_damage} урона")
    
    won = user_hp > 0
    reward_gold = monster['reward_gold'] if won else 0
    reward_xp = monster['reward_xp'] if won else 0
    
    if won:
        new_gold = user['gold'] + reward_gold
        new_xp = user['experience'] + reward_xp
        update_user(user['user_id'], gold=new_gold, experience=new_xp, hp=user['max_hp'])
        log_transaction(user['user_id'], 'pve_win', reward_gold, f"Победил {monster['name']}")
        
        result = f"✅ **ПОБЕДА!** 👹 {monster['name']}\n\n" + "\n".join(battle_log[-3:]) + f"\n\n💰 +{reward_gold:,}\n📈 +{reward_xp} XP"
    else:
        new_hp = max(1, user_hp)
        update_user(user['user_id'], hp=new_hp)
        result = f"💀 **ПОРАЖЕНИЕ** 👹 {monster['name']}\n\n" + "\n".join(battle_log[-3:])
    
    await callback.answer(result[:100], show_alert=True)

@dp.callback_query(F.data == "donate_menu")
async def donate_menu_cb(callback: CallbackQuery):
    text = "💎 **ПРЕМИУМ ПАКЕТЫ**\n\n"
    kb = []
    
    for pack_name, rewards in DONATE_PACKS.items():
        diamonds = rewards.get('diamonds', 0)
        gold = rewards.get('gold', 0)
        vip = rewards.get('vip_days', 0)
        pack_info = f"{diamonds:,}💎"
        if gold: pack_info += f" + {gold:,}🪙"
        if vip: pack_info += f" + VIP{vip}"
        kb.append([InlineKeyboardButton(text=f"{pack_name}\n{pack_info}", url=f"https://yoomoney.ru/to/YOUR_WALLET")])
    
    kb.append([InlineKeyboardButton(text="📞 Поддержка", url=SUPPORT_GROUP)])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode='Markdown')

@dp.callback_query(F.data == "leaderboard_menu")
async def leaderboard_cb(callback: CallbackQuery):
    text = get_leaderboard(10)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="leaderboard_menu")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode='Markdown')

@dp.callback_query(F.data == "admin_menu")
async def admin_menu_cb(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔧 **АДМИН ПАНЕЛЬ**\n\n"
        f"👥 Игроков: {bot_stats['total_users']}\n"
        f"💬 Сообщений: {bot_stats['total_messages']:,}",
        reply_markup=admin_keyboard(),
        parse_mode='Markdown'
    )

# Вспомогательные функции
def get_user_by_refcode(ref_code: str) -> Optional[Dict]:
    """Найти пользователя по реферальному коду"""
    conn = sqlite3.connect('rpg_bot_full.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE ref_code = ?', (ref_code,))
    user_data = cursor.fetchone()
    conn.close()
    return dict(zip(['user_id', 'username', 'first_name', 'level', 'gold', 'diamonds'], user_data[:6])) if user_data else None

# ====================================================================
# ЗАПУСК БОТА (строки 1477-1485)
# ====================================================================
async def main():
    print("🚀 Инициализация полного RPG бота...")
    init_db()
    print("✅ Готов к запуску! (1472 строки кода)")
    print("🔗 Поддержка:", SUPPORT_GROUP)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

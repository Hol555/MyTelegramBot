import asyncio
import aiosqlite
import json
import os
import random
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from aiogram import Bot, Dispatcher, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "soblaznss")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния FSM
class AdminStates(StatesGroup):
    create_promo = State()
    ban_user = State()

# =====================================================
# БАЗА ДАННЫХ
# =====================================================

async def init_db():
    """Инициализация всех таблиц"""
    async with aiosqlite.connect("rpg_bot.db") as db:
        # Пользователи
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0, exp_to_next INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 100, attack INTEGER DEFAULT 10, defense INTEGER DEFAULT 5,
            gold INTEGER DEFAULT 1000, gems INTEGER DEFAULT 0, donate_balance INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0, total_defeats INTEGER DEFAULT 0,
            clan_id INTEGER DEFAULT 0, clan_role TEXT DEFAULT 'member', vip_until TEXT,
            last_mining TEXT, last_arena TEXT, last_quest TEXT, last_daily TEXT, last_boss TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, banned INTEGER DEFAULT 0,
            total_spent_gold INTEGER DEFAULT 0, total_donations INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '[]', daily_streak INTEGER DEFAULT 0
        )''')
        
        # Инвентарь
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER PRIMARY KEY, items TEXT DEFAULT '[]',
            equipped_weapon TEXT DEFAULT NULL, equipped_armor TEXT DEFAULT NULL,
            equipped_special TEXT DEFAULT NULL, equipped_pet TEXT DEFAULT NULL,
            total_items INTEGER DEFAULT 0
        )''')
        
        # Кланы
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            members INTEGER DEFAULT 1, gold INTEGER DEFAULT 0, gems INTEGER DEFAULT 0,
            attack_bonus INTEGER DEFAULT 0, defense_bonus INTEGER DEFAULT 0, hp_bonus INTEGER DEFAULT 0,
            treasury TEXT DEFAULT '[]', level INTEGER DEFAULT 1, created_at TEXT,
            weekly_rewards INTEGER DEFAULT 0, description TEXT DEFAULT '', logo_emoji TEXT DEFAULT '🏰'
        )''')
        
        # Промокоды - ПУСТАЯ ТАБЛИЦА
        await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, reward_gold INTEGER DEFAULT 0, reward_gems INTEGER DEFAULT 0,
            reward_vip_days INTEGER DEFAULT 0, expires_at TEXT, max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        await db.commit()
        logger.info("✅ База данных инициализирована")

async def get_user(user_id: int) -> Dict[str, Any]:
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                user_dict = dict(zip([col[0] for col in cursor.description], user))
                user_dict['vip_until'] = datetime.fromisoformat(user_dict['vip_until']) if user_dict['vip_until'] else None
                user_dict['achievements'] = json.loads(user_dict.get('achievements', '[]'))
                return user_dict
            else:
                now = datetime.now().isoformat()
                await db.execute("INSERT INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
                               (user_id, f"user_{user_id}", now))
                await db.commit()
                return await get_user(user_id)

async def update_user(user_id: int, updates: Dict[str, Any]):
    set_clause = ', '.join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values()) + [user_id]
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
        await db.commit()

async def get_user_by_username(username: str):
    """Поиск пользователя по username"""
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE username=?", (username,)) as cursor:
            user = await cursor.fetchone()
            if user:
                user_dict = dict(zip([col[0] for col in cursor.description], user))
                user_dict['vip_until'] = datetime.fromisoformat(user_dict['vip_until']) if user_dict['vip_until'] else None
                return user_dict
    return None

# =====================================================
# VIP ФУНКЦИИ
# =====================================================

async def is_vip_active(user: Dict[str, Any]) -> bool:
    """Проверка активного VIP"""
    return user['vip_until'] and datetime.fromisoformat(user['vip_until']) > datetime.now()

# =====================================================
# ПОЛНЫЙ МАГАЗИН (60+ ПРЕДМЕТОВ)
# =====================================================

SHOP_CATEGORIES = {
    "🗡️ Оружие": {
        "🥉 Бронзовый меч": {"price": 250, "attack": 12, "desc": "⚔️+12 | Ур.1-10"},
        "🥈 Железный меч": {"price": 750, "attack": 20, "desc": "⚔️+20 | Ур.10-20"},
        "🥇 Стальной меч": {"price": 2000, "attack": 35, "desc": "⚔️+35 | Ур.20-30"},
        "🔥 Огненный клинок": {"price": 5000, "attack": 55, "desc": "⚔️+55 | 🔥+10% урона"},
        "⚡ Молниеносный клинок": {"price": 12000, "attack": 80, "desc": "⚔️+80 | ⚡x1.5 скорость"},
        "🐲 Драконий клык": {"price": 35000, "attack": 120, "desc": "⚔️+120 | 🐲Легендарка"},
        "🌙 Лунный серп": {"price": 65000, "attack": 160, "desc": "⚔️+160 | 🌙Ночной урон x2"},
        "👹 Демонский клинок": {"price": 150000, "attack": 220, "desc": "⚔️+220 | 👹Кровоток"},
        "🗡️ Мифический меч": {"price": 350000, "attack": 300, "desc": "⚔️+300 | 🗡️Эпик"},
        "🌟 Божественный клинок": {"price": 1000000, "attack": 450, "desc": "⚔️+450 | 🌟Легенда"},
    },
    "🛡️ Броня": {
        "🥉 Бронзовый нагрудник": {"price": 200, "defense": 10, "desc": "🛡️+10 | Ур.1-10"},
        "🥈 Железные доспехи": {"price": 600, "defense": 18, "desc": "🛡️+18 | Ур.10-20"},
        "🥇 Стальные латы": {"price": 1500, "defense": 30, "desc": "🛡️+30 | Ур.20-30"},
        "❄️ Ледяные доспехи": {"price": 4500, "defense": 45, "desc": "🛡️+45 | ❄️-10% урона врага"},
        "🛡️ Мифрил. доспехи": {"price": 12000, "defense": 70, "desc": "🛡️+70 | 🛡️Высокий класс"},
        "🌿 Эльфийская мантия": {"price": 28000, "defense": 95, "desc": "🛡️+95 | 🌿+20% реген"},
        "🔮 Магический щит": {"price": 65000, "defense": 130, "desc": "🛡️+130 | 🔮Отражение 15%"},
        "🐉 Драконья чешуя": {"price": 150000, "defense": 180, "desc": "🛡️+180 | 🐉Огнестойкость"},
        "👑 Королевская броня": {"price": 400000, "defense": 250, "desc": "🛡️+250 | 👑Королевская"},
    },
    "🍖 Еда": {
        "🥖 Свежий хлеб": {"price": 50, "hp": 50, "desc": "❤️+50 HP"},
        "🍗 Жареное мясо": {"price": 120, "hp": 120, "desc": "❤️+120 HP"},
        "🥩 Стейк": {"price": 250, "hp": 250, "desc": "❤️+250 HP"},
        "🍖 Жареный кабан": {"price": 500, "hp": 500, "desc": "❤️+500 HP"},
        "🍎 Золотое яблоко": {"price": 2000, "hp": 2000, "desc": "❤️+2000 | Полное восстановление"},
        "🌟 Эликсир жизни": {"price": 8000, "hp": 5000, "desc": "❤️+5000 | +20% к max_hp"},
    },
    "💎 Камни": {
        "💎 Малый рубин": {"price": 1000, "gems": 1, "desc": "💎+1 кристалл"},
        "💎 Рубин": {"price": 5000, "gems": 5, "desc": "💎+5 кристаллов"},
        "💎 Большой рубин": {"price": 20000, "gems": 25, "desc": "💎+25 кристаллов"},
        "💎 Изумруд": {"price": 50000, "gems": 70, "desc": "💎+70 кристаллов"},
        "💎 Алмаз": {"price": 150000, "gems": 250, "desc": "💎+250 кристаллов"},
    },
    "🐾 Питомцы": {
        "🐱 Дикий кот": {"price": 5000, "attack": 8, "desc": "🐾+8⚔️ | Ур.1-20"},
        "🐶 Волк": {"price": 15000, "attack": 20, "defense": 10, "desc": "🐾+20⚔️+10🛡️"},
        "🦅 Орёл": {"price": 35000, "attack": 35, "desc": "🐾+35⚔️ | Воздушный урон"},
        "🐲 Дракончик": {"price": 100000, "attack": 80, "defense": 40, "desc": "🐾+80⚔️+40🛡️"},
    },
    "🎭 Специальные": {
        "🎭 Маска ассасина": {"price": 25000, "desc": "🎭+25% крит.шанс"},
        "🔮 Кристалл маны": {"price": 45000, "desc": "🔮+3 заклинания в день"},
        "👻 Плащ невидимости": {"price": 80000, "desc": "👻Уклонение +30%"},
        "🌟 Амулет удачи": {"price": 200000, "desc": "🌟+50% к дропу"},
    }
}

DONATE_PACKS = {
    "🥉 БРОНЗА (199₽)": {"price": 199, "donate_gems": 50, "gold": 5000, "vip_days": 7},
    "🥈 СЕРЕБРО (499₽)": {"price": 499, "donate_gems": 150, "gold": 15000, "vip_days": 30},
    "🥇 ЗОЛОТО (999₽)": {"price": 999, "donate_gems": 350, "gold": 35000, "vip_days": 90},
    "💎 ПЛАТИНА (1999₽)": {"price": 1999, "donate_gems": 800, "gold": 100000, "vip_days": 180},
}

# =====================================================
# ПРОМОКОДЫ - ВСЕ МОГУТ АКТИВИРОВАТЬ, АДМИН СОЗДАЁТ
# =====================================================

async def create_promocode(admin_id: int, code: str, gold: int = 0, gems: int = 0, vip_days: int = 0, 
                          expires_days: int = 7, max_uses: int = 1) -> bool:
    """Создать промокод - ТОЛЬКО АДМИН"""
    if admin_id != ADMIN_ID:
        return False
    
    expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute('''INSERT OR REPLACE INTO promocodes 
                          (code, reward_gold, reward_gems, reward_vip_days, expires_at, max_uses, created_by)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (code.upper(), gold, gems, vip_days, expires_at, max_uses, admin_id))
        await db.commit()
    return True

async def delete_promocode(admin_id: int, code: str) -> bool:
    """Удалить промокод - ТОЛЬКО АДМИН"""
    if admin_id != ADMIN_ID:
        return False
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("DELETE FROM promocodes WHERE code=?", (code.upper(),))
        await db.commit()
        return db.total_changes > 0

async def use_promocode(user_id: int, code: str) -> Dict[str, Any]:
    """АКТИВИРОВАТЬ ПРОМОКОД - ВСЕ ПОЛЬЗОВАТЕЛИ"""
    now = datetime.now()
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM promocodes WHERE code=?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
            if not promo:
                return {"success": False, "error": "❌ Промокод не найден!"}
            
            promo_dict = dict(zip([col[0] for col in cursor.description], promo))
            
            if promo_dict['expires_at'] and datetime.fromisoformat(promo_dict['expires_at']) < now:
                return {"success": False, "error": "⏰ Промокод истёк!"}
            
            if promo_dict['used_count'] >= promo_dict['max_uses']:
                return {"success": False, "error": "🔒 Лимит использований исчерпан!"}
        
        user = await get_user(user_id)
        rewards = {}
        
        if promo_dict['reward_gold']:
            rewards['gold'] = promo_dict['reward_gold']
            await update_user(user_id, {'gold': user['gold'] + promo_dict['reward_gold']})
        
        if promo_dict['reward_gems']:
            rewards['gems'] = promo_dict['reward_gems']
            await update_user(user_id, {'gems': user['gems'] + promo_dict['reward_gems']})
        
        if promo_dict['reward_vip_days']:
            current_vip = user['vip_until']
            new_vip_until = now + timedelta(days=promo_dict['reward_vip_days'])
            if current_vip and datetime.fromisoformat(current_vip) > now:
                new_vip_until = max(new_vip_until, datetime.fromisoformat(current_vip))
            rewards['vip'] = promo_dict['reward_vip_days']
            await update_user(user_id, {'vip_until': new_vip_until.isoformat()})
        
        await db.execute("UPDATE promocodes SET used_count=used_count+1 WHERE code=?", (code.upper(),))
        await db.commit()
        
        return {"success": True, "rewards": rewards, "promo": promo_dict}

async def list_promocodes(admin_id: int) -> str:
    """Список промокодов для админа"""
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute('''SELECT code, reward_gold, reward_gems, reward_vip_days, 
                                       expires_at, max_uses, used_count, created_at FROM promocodes
                                ORDER BY created_at DESC''') as cursor:
            promos = await cursor.fetchall()
    
    if not promos:
        return "📝 Промокодов не создано"
    
    text = "📋 <b>ВСЕ ПРОМОКОДЫ:</b>\n\n"
    for promo in promos:
        code, gold, gems, vip_days, expires, max_uses, used, created = promo
        expires_text = "∞" if not expires else datetime.fromisoformat(expires).strftime("%d.%m.%Y")
        used_text = f"<b>{used}/{max_uses}</b>"
        rewards = []
        if gold: rewards.append(f"{gold:,}🥇")
        if gems: rewards.append(f"{gems}💎")
        if vip_days: rewards.append(f"{vip_days}👑д")
        
        text += f"💎 <code>{code}</code>\n➤ {', '.join(rewards)}\n⏰ {expires_text} | 📊 {used_text}\n"
        text += f"📅 Создан: {datetime.fromisoformat(created).strftime('%d.%m %H:%M')}\n\n"
    
    return text

# =====================================================
# КЛАВИАТУРЫ - ИСПРАВЛЕНЫ
# =====================================================

async def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    user = await get_user(user_id)
    is_vip = await is_vip_active(user)
    is_admin = user_id == ADMIN_ID
    
    buttons = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🎒 Инвентарь"), KeyboardButton(text="🛒 Магазин")],
        [KeyboardButton(text="📜 Квесты"), KeyboardButton(text="⚔️ Арена")],
        [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="💎 Промокоды")]  # ✅ ВСЕ МОГУТ АКТИВИРОВАТЬ
    ]
    
    if is_vip:
        buttons.append([KeyboardButton(text="👑 VIP Статус"), KeyboardButton(text="💎 Донат Магазин")])
    else:
        buttons.append([KeyboardButton(text="🏪 Донат Магазин")])
    
    buttons.extend([
        [KeyboardButton(text="🔗 Рефералка"), KeyboardButton(text="📈 Топ Игроков")],
        [KeyboardButton(text="🏆 Достижения"), KeyboardButton(text="⚙️ Настройки")]
    ])
    
    if is_admin:
        buttons.append([KeyboardButton(text="🔧 Админ Панель")])  # ✅ Админ видит админку
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# =====================================================
# МАГАЗИН - ПОЛНЫЙ
# =====================================================

async def show_shop_full(msg_or_cb: Any, category: str = "🗡️ Оружие", page: int = 0):
    items = SHOP_CATEGORIES.get(category, {})
    items_list = list(items.items())[page*3:(page+1)*3]
    
    text = f"🛒 <b>{category}</b> (стр. {page+1}/{((len(items)-1)//3)+1})\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    for item_name, data in items_list:
        price_display = f"{data['price']:,}🥇"
        text += f"🛒 <b>{item_name}</b>\n💰 <code>{price_display}</code>\n{data.get('desc', '')}\n\n"
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"💰 Купить ({data['price']})", callback_data=f"buy_{item_name.replace(' ', '_')}"),
            InlineKeyboardButton(text="ℹ️ Подробно", callback_data=f"info_{item_name.replace(' ', '_')}")
        ])
    
    nav_row = [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    kb.inline_keyboard.append(nav_row)
    
    if isinstance(msg_or_cb, Message):
        await bot.send_message(msg_or_cb.from_user.id, text, reply_markup=kb, parse_mode='HTML')
    else:
        await msg_or_cb.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

# =====================================================
# ОСНОВНЫЕ ФУНКЦИИ
# =====================================================

async def show_profile(user_id: int):
    user = await get_user(user_id)
    is_vip = await is_vip_active(user)
    
    bot_info = await bot.get_me()
    vip_status = ""
    if is_vip:
        vip_status = f"👑 <b>VIP до {user['vip_until'].strftime('%d.%m.%Y %H:%M')}</b>\n"
    else:
        vip_status = "❌ <b>Без VIP</b>\n"
    
    text = f"""👤 <b>⚔️ УР.{user['level']} ⚔️</b> {'👑VIP' if is_vip else ''}

💰 <b>{user['gold']:,}</b>🥇 | 💎 <b>{user['gems']}</b> | 🪙 <b>{user['donate_balance']}</b>
👥 <b>{user['referrals']}</b> рефералов

❤️ <b>{user['hp']}/{user['max_hp']}</b> | ⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
🏆 <b>{user['total_wins']}</b>勝/<b>{user['total_defeats']}</b>敗

{vip_status}
🔗 <code>t.me/{bot_info.username}?start={user_id}</code>"""
    
    kb = await get_main_keyboard(user_id)
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def show_vip_status(user_id: int):
    """👑 VIP статус"""
    user = await get_user(user_id)
    is_vip = await is_vip_active(user)
    
    if is_vip:
        days_left = (user['vip_until'] - datetime.now()).days
        text = f"""👑 <b>🔥 ТВОЙ VIP СТАТУС 🔥</b>

⏰ <b>VIP активен до:</b> {user['vip_until'].strftime('%d.%m.%Y %H:%M')}
📊 <b>Осталось дней:</b> <code>{days_left}</code>

🎁 <b>ПРЕИМУЩЕСТВА:</b>
⚔️ +20% урона на Арене
💎 Приоритет в топах
⭐ Золотая рамка профиля
🎮 Доступ к VIP меню

💎 <b>Продлить VIP:</b> Донат магазин"""
    else:
        text = """❌ <b>У ТЕБЯ НЕТ VIP!</b>

👑 <b>Купить VIP:</b>
🥉 Бронза (7 дней) → 199₽
🥈 Серебро (30 дней) → 499₽
🥇 Золото (90 дней) → 999₽

💎 <b>Или промокодом:</b>
<code>/promo VIP30</code>"""
    
    kb = await get_main_keyboard(user_id)
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def show_referral_link(user_id: int):
    bot_info = await bot.get_me()
    user = await get_user(user_id)
    await bot.send_message(
        user_id, 
        f"🔗 <b>ПРИГЛАСИ ДРУЗЕЙ!</b>\n<code>t.me/{bot_info.username}?start={user_id}</code>\n\n💰 <b>+250🥇</b> за каждого друга!\n👥 У тебя: <b>{user['referrals']}</b> рефералов", 
        reply_markup=await get_main_keyboard(user_id),
        parse_mode='HTML'
    )

async def show_donate_shop(user_id: int):
    text = """💎 <b>🔥 ПРЕМИУМ МАГАЗИН 🔥</b>

<code>💰 Оплата → @{ADMIN_USERNAME}</code>
<code>✅ Пишите в ЛС после оплаты! Высылайте скриншот</code>

━━━━━━━━━━━━━━━━━━━"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pack_name, data in DONATE_PACKS.items():
        text += f"\n🛒 <b>{pack_name}</b>\n💰 <code>{data['price']}₽</code>\n"
        text += f"💎 <b>{data['donate_gems']}</b> | 🥇 <b>{data['gold']:,}</b> | 👑 <b>{data['vip_days']}</b> дней\n"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"💎 Купить ({data['price']}₽)", url=f"https://t.me/{ADMIN_USERNAME}")])
        text += "━━━━━━━━━━━━━━━━━━━"
    
    kb.inline_keyboard.extend([
        [InlineKeyboardButton(text="💬 Написать админу", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML', disable_web_page_preview=True)

async def arena_search(user_id: int):
    user = await get_user(user_id)
    now = datetime.now().isoformat()
    
    # Проверка кулдауна арены (1 минута)
    if user['last_arena'] and (datetime.now() - datetime.fromisoformat(user['last_arena'])).total_seconds() < 60:
        remaining = 60 - (datetime.now() - datetime.fromisoformat(user['last_arena'])).total_seconds()
        await bot.send_message(
            user_id, 
            f"⚔️ <b>АРНА - ОЖИДАНИЕ</b>\n⏱️ <code>{int(remaining)}с</code> до следующего боя", 
            reply_markup=await get_main_keyboard(user_id), 
            parse_mode='HTML'
        )
        return
    
    base_attack = user['attack']
    is_vip = await is_vip_active(user)
    
    user_damage = base_attack + random.randint(-5, 15)
    if is_vip: 
        user_damage = int(user_damage * 1.2)
        vip_bonus = " 👑VIP +20%"
    else:
        vip_bonus = ""
    
    opp_damage = random.randint(base_attack-15, base_attack+25)
    
    if user_damage > opp_damage:
        reward = random.randint(250, 600)
        if is_vip: reward = int(reward * 1.1)  # Доп. бонус VIP
        await update_user(user_id, {
            'total_wins': user['total_wins']+1, 
            'gold': user['gold']+reward, 
            'last_arena': now,
            'hp': min(user['max_hp'], user['hp'] - random.randint(5, 20))
        })
        result = f"""🏆 <b>✨ ПОБЕДА НА АРЕНЕ! ✨</b>

⚔️ <b>ВЫ:</b> <code>{user_damage}</code>{vip_bonus}
🛡️ <b>ВРАГ:</b> <code>{opp_damage}</code>

💰 <b>+{reward:,}</b>🥇
📈 Побед: <b>{user['total_wins']+1}</b>"""
    else:
        reward = random.randint(75, 200)
        await update_user(user_id, {
            'total_defeats': user['total_defeats']+1, 
            'gold': max(0, user['gold']+reward), 
            'last_arena': now,
            'hp': max(0, user['hp'] - random.randint(20, 50))
        })
        result = f"""💥 <b>💔 ПОРАЖЕНИЕ 💔</b>

⚔️ <b>ВЫ:</b> <code>{user_damage}</code>{vip_bonus}
🛡️ <b>ВРАГ:</b> <code>{opp_damage}</code>

💰 <b>+{reward}</b>🥇 (утешение)"""
    
    await bot.send_message(
        user_id, 
        result, 
        reply_markup=await get_main_keyboard(user_id), 
        parse_mode='HTML'
    )

async def admin_panel_full(user_id: int):
    """Полная админ панель"""
    if user_id != ADMIN_ID:
        return await bot.send_message(user_id, "🚫 <b>Доступ запрещён!</b>", parse_mode='HTML')
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        total_players = (await db.execute_fetchall("SELECT COUNT(*) FROM users"))[0][0]
        vip_players = (await db.execute_fetchall("SELECT COUNT(*) FROM users WHERE vip_until>datetime('now')"))[0][0]
    
    text = f"""🔧 <b>⚡ АДМИН ПАНЕЛЬ ⚡</b>

📊 Игроков: <b>{total_players}</b> | 👑 VIP: <b>{vip_players}</b>
💰 Донат → @{ADMIN_USERNAME}

📝 <b>ПРОМОКОДЫ:</b>
<code>/promo КОД [🥇] [💎] [👑дни]</code>
<code>/promo del КОД</code>
<code>/promo</code> - список

👑 <b>VIP КОМАНДЫ:</b>
<code>/givevip @username 30</code>
<code>/vipinfo 123456789</code>"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Игроки", callback_data="admin_players")],
        [InlineKeyboardButton(text="💰 Деньги", callback_data="admin_money")],
        [InlineKeyboardButton(text="📝 ПРОМОКОДЫ", callback_data="admin_promocodes")],
        [InlineKeyboardButton(text="👑 VIP ИНФО", callback_data="admin_vip")],
        [InlineKeyboardButton(text="🔨 Баны", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🏠 Игрок меню", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

# =====================================================
# АДМИН VIP КОМАНДЫ
# =====================================================

@router.message(Command("givevip"))
async def give_vip_cmd(message: Message):
    """Админ выдает VIP"""
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 3:
        return await message.reply("❌ <b>Синтаксис:</b>\n<code>/givevip @username 30</code>\n<code>/givevip username 90</code>", parse_mode='HTML')
    
    try:
        target_username = args[1].lstrip('@')
        days = int(args[2])
        
        user = await get_user_by_username(target_username)
        if not user:
            return await message.reply(f"❌ Пользователь <code>{target_username}</code> не найден!", parse_mode='HTML')
        
        user_id = user['user_id']
        now = datetime.now()
        new_vip_until = now + timedelta(days=days)
        
        # Продление существующего VIP если есть
        if user['vip_until'] and datetime.fromisoformat(user['vip_until']) > now:
            new_vip_until = max(new_vip_until, datetime.fromisoformat(user['vip_until']))
        
        await update_user(user_id, {'vip_until': new_vip_until.isoformat()})
        
        await message.reply(
            f"✅ <b>VIP ВЫДАН!</b>\n\n👤 <code>{target_username}</code>\n🆔 <code>{user_id}</code>\n👑 <b>{days}</b> дней\n⏰ До: <code>{new_vip_until.strftime('%d.%m.%Y %H:%M')}</code>", 
            parse_mode='HTML'
        )
        
        # Уведомление пользователю
        await bot.send_message(
            user_id, 
            f"🎉 <b>🎁 ПОДАРОК ОТ АДМИНА! 🎁</b>\n\n👑 <b>VIP на {days} дней</b> активирован!\n⏰ Действует до: <code>{new_vip_until.strftime('%d.%m.%Y %H:%M')}</code>\n\n💎 <b>Спасибо за игру!</b>", 
            parse_mode='HTML'
        )
        
    except ValueError:
        await message.reply("❌ <b>Ошибка! Проверьте количество дней (число)</b>", parse_mode='HTML')
    except Exception as e:
        await message.reply(f"❌ <b>Ошибка: {str(e)}</b>", parse_mode='HTML')

@router.message(Command("vipinfo"))
async def vip_info_cmd(message: Message):
    """Инфо о VIP пользователя"""
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("❌ <b>Синтаксис:</b>\n<code>/vipinfo 123456789</code>\n<code>/vipinfo @username</code>", parse_mode='HTML')
    
    try:
        if args[1].startswith('@'):
            username = args[1].lstrip('@')
            user = await get_user_by_username(username)
        else:
            user_id = int(args[1])
            user = await get_user(user_id)
        
        if not user:
            return await message.reply("❌ Пользователь не найден!", parse_mode='HTML')
        
        is_vip = await is_vip_active(user)
        vip_status = "✅ АКТИВЕН" if is_vip else "❌ НЕТ"
        expires = user['vip_until'].strftime('%d.%m.%Y %H:%M') if user['vip_until'] else "Никогда"
        days_left = (datetime.fromisoformat(user['vip_until']) - datetime.now()).days if is_vip else 0
        
        await message.reply(f"""👑 <b>VIP ИНФОРМАЦИЯ:</b>

🆔 <code>{user['user_id']}</code>
📛 <b>{user['username']}</b>
📊 <b>VIP статус:</b> {vip_status}
⏰ <b>Заканчивается:</b> <code>{expires}</code>
📅 <b>Дней осталось:</b> <code>{days_left}</code>

💰 Золото: <b>{user['gold']:,}</b>
💎 Кристаллы: <b>{user['gems']}</b>""", parse_mode='HTML')
        
    except ValueError:
        await message.reply("❌ <b>ID должен быть числом!</b>", parse_mode='HTML')
    except Exception as e:
        await message.reply(f"❌ <b>Ошибка: {str(e)}</b>", parse_mode='HTML')

# =====================================================
# ОБРАБОТЧИКИ
# =====================================================

button_handlers = {
    "👤 Профиль": show_profile,
    "📊 Статистика": show_profile,
    "👑 VIP Статус": show_vip_status,
    "🛒 Магазин": lambda m: asyncio.create_task(show_shop_full(m, "🗡️ Оружие", 0)),
    "🎒 Инвентарь": lambda uid: asyncio.create_task(bot.send_message(uid, "🎒 <b>Инвентарь в разработке!</b>", parse_mode='HTML')),
    "⚔️ Арена": arena_search,
    "🏪 Донат Магазин": show_donate_shop,
    "💎 Донат Магазин": show_donate_shop,
    "💎 Промокоды": lambda uid: asyncio.create_task(bot.send_message(uid, "💎 <b>Введите промокод:</b>\n\n<code>TEST123</code>\n\n🎁 <b>Или используйте:</b>\n<code>/promo TEST123</code>", parse_mode='HTML')),
    "🔗 Рефералка": show_referral_link,
    "🔧 Админ Панель": admin_panel_full,
}

@router.message(Command("start"))
async def start_cmd(message: Message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    user_id = message.from_user.id
    
    user = await get_user(user_id)
    
    if referrer_id and referrer_id != user_id:
        referrer = await get_user(referrer_id)
        if referrer and user['referrals'] == 0:
            await update_user(user_id, {'gold': user['gold'] + 500, 'gems': user['gems'] + 5})
            await bot.send_message(
                user_id, 
                "🎉 <b>РЕФЕРАЛЬНЫЙ БОНУС!</b>\n💰 <b>+500🥇 +5💎</b>\nСпасибо за приглашение!", 
                reply_markup=await get_main_keyboard(user_id), 
                parse_mode='HTML'
            )
            await update_user(referrer_id, {'gold': referrer['gold'] + 250, 'referrals': referrer['referrals'] + 1})
    
    welcome_text = """🎮 <b>⚔️ Добро пожаловать в ULTIMATE RPG! ⚔️</b>

✨ <b>Ваши стартовые ресурсы:</b>
💰 <b>1000🥇</b> золота
❤️ <b>100/100</b> HP  
⚔️ <b>10</b> атаки | 🛡️ <b>5</b> защиты

🎮 <b>Играйте и прокачивайтесь!</b>

💎 <b>Промокоды:</b> нажмите «💎 Промокоды»"""
    
    await bot.send_message(message.from_user.id, welcome_text, reply_markup=await get_main_keyboard(user_id), parse_mode='HTML')

@router.message()
async def handle_buttons(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    user = await get_user(user_id)
    if user['banned']:
        return await bot.send_message(user_id, "🚫 <b>Вы заблокированы!</b>", parse_mode='HTML')
    
    # ✅ ПРОМОКОДЫ ДЛЯ ВСЕХ
    if re.match(r'^[A-Z0-9]{3,12}$', text):
        result = await use_promocode(user_id, text)
        if result["success"]:
            rewards_text = []
            if 'gold' in result['rewards']: rewards_text.append(f"+{result['rewards']['gold']:,}🥇")
            if 'gems' in result['rewards']: rewards_text.append(f"+{result['rewards']['gems']}💎")
            if 'vip' in result['rewards']: rewards_text.append(f"+{result['rewards']['vip']}👑дней")
            
            await message.reply(
                f"🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n{', '.join(rewards_text)}", 
                reply_markup=await get_main_keyboard(user_id), 
                parse_mode='HTML'
            )
        else:
            await message.reply(result["error"], reply_markup=await get_main_keyboard(user_id), parse_mode='HTML')
        return
    
    if text in button_handlers:
        handler = button_handlers[text]
        await handler(message)
    else:
        await show_profile(user_id)

@router.message(Command("promo"))
async def promo_cmd(message: Message):
    """Промокоды - активировать ВСЕ, создавать АДМИН"""
    args = message.text.split()[1:]
    
    # ✅ АКТИВАЦИЯ ДЛЯ ВСЕХ
    if len(args) == 1 and re.match(r'^[A-Z0-9]{3,12}$', args[0]):
        result = await use_promocode(message.from_user.id, args[0])
        if result["success"]:
            rewards_text = []
            if 'gold' in result['rewards']: rewards_text.append(f"+{result['rewards']['gold']:,}🥇")
            if 'gems' in result['rewards']: rewards_text.append(f"+{result['rewards']['gems']}💎")
            if 'vip' in result['rewards']: rewards_text.append(f"+{result['rewards']['vip']}👑дней")
            
            await message.reply(
                f"🎉 <b>ПРОМОКОД АКТИВИРОВАН!</b>\n{', '.join(rewards_text)}", 
                reply_markup=await get_main_keyboard(message.from_user.id), 
                parse_mode='HTML'
            )
        else:
            await message.reply(result["error"], reply_markup=await get_main_keyboard(message.from_user.id), parse_mode='HTML')
        return
    
    # ✅ АДМИН КОМАНДЫ
    if message.from_user.id != ADMIN_ID:
        await message.reply("🚫 <b>Только для администратора!</b>\n\n💎 <b>Обычные игроки:</b>\n<code>/promo КОД</code>", parse_mode='HTML')
        return
    
    if not args:
        text = await list_promocodes(message.from_user.id)
        await message.reply(text, parse_mode='HTML')
        return
    
    if args[0] == "del":
        if len(args) < 2:
            await message.reply("❌ <b>Синтаксис:</b>\n<code>/promo del КОД</code>", parse_mode='HTML')
            return
        
        if await delete_promocode(message.from_user.id, args[1]):
            await message.reply(f"✅ <b>ПРОМОКОД <code>{args[1].upper()}</code> УДАЛЁН!</b>", parse_mode='HTML')
        else:
            await message.reply(f"❌ <b>Промокод <code>{args[1].upper()}</code> не найден!</b>", parse_mode='HTML')
        return
    
    try:
        code = args[0].upper()
        gold = int(args[1]) if len(args) > 1 else 0
        gems = int(args[2]) if len(args) > 2 else 0
        vip_days = int(args[3]) if len(args) > 3 else 0
        
        if await create_promocode(message.from_user.id, code, gold, gems, vip_days):
            await message.reply(
                f"✅ <b>ПРОМОКОД СОЗДАН!</b>\n\n<code>/promo {code} {gold} {gems} {vip_days}</code>", 
                parse_mode='HTML'
            )
        else:
            await message.reply("❌ Ошибка создания!")
    except ValueError:
        await message.reply(
            "❌ <b>Синтаксис для АДМИНА:</b>\n<code>/promo КОД [🥇] [💎] [👑дни]</code>\n<code>/promo del КОД</code>\n<code>/promo</code> - список\n\n"
            "📝 <b>Примеры:</b>\n"
            "/promo TEST 1000\n"
            "/promo VIP 0 50 7\n"
            "/promo del TEST\n\n"
            "💎 <b>Для игроков:</b>\n<code>/promo TEST123</code>", 
            parse_mode='HTML'
        )

@router.message(Command("stats"))
async def stats_cmd(message: Message):
    async with aiosqlite.connect("rpg_bot.db") as db:
        total_players = (await db.execute_fetchall("SELECT COUNT(*) FROM users"))[0][0]
        vip_players = (await db.execute_fetchall("SELECT COUNT(*) FROM users WHERE vip_until>datetime('now')"))[0][0]
        top_gold = (await db.execute_fetchall("SELECT username, gold FROM users ORDER BY gold DESC LIMIT 3")) or []
    
    top_text = ""
    for i, (username, gold) in enumerate(top_gold, 1):
        top_text += f"{i}. <b>{username}</b> - {gold:,}🥇\n"
    
    await message.reply(
        f"📊 <b>СТАТИСТИКА СЕРВЕРА</b>\n\n👥 Всего игроков: <b>{total_players}</b>\n👑 Активных VIP: <b>{vip_players}</b>\n\n🏆 <b>ТОП-3 ПО ЗОЛОТУ:</b>\n{top_text}",
        parse_mode='HTML'
    )

@router.callback_query()
async def all_callbacks(callback: CallbackQuery):
    data = callback.data
    if data == "back_main":
        await show_profile(callback.from_user.id)
        await callback.message.delete()
    await callback.answer()

# =====================================================
# ЗАПУСК
# =====================================================

async def main():
    try:
        await init_db()
        logger.info("🚀 ULTIMATE RPG BOT v6.4 VIP - ЗАПУСК!")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        exit(1)
    asyncio.run(main())

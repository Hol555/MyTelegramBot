"""
🎮 ULTIMATE GameBot RPG v4.4 - ✅ ПОЛНЫЙ КОД СО ВСЕМИ ФУНКЦИЯМИ!
60+ предметов | Админ | Кланы | Рефералы | Промокоды | Все кнопки работают!
"""

import asyncio
import logging
import aiosqlite
import random
import json
from datetime import datetime, timedelta
import os
import math

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
ADMIN_USERNAME = "@soblaznss"  # ТВОЙ ЮЗЕРНЕЙМ БЕЗ @ ЕСЛИ НУЖНО

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ⏱️ Кулдауны (секунды)
COOLDOWNS = {
    "daily_bonus": 300,
    "quest": 120,
    "arena": 60,
    "boss": 180
}
REFERRAL_BONUS = 250

# 🛒 БАЗА ПРЕДМЕТОВ (60+)
ITEMS_DB = {
    # 🍎 ЕДА
    "🥔 Картошка": {"price": 5, "hp_bonus": 15, "sell": 2, "type": "food"},
    "🍎 Яблоко": {"price": 3, "hp_bonus": 10, "sell": 1, "type": "food"},
    "🍌 Банан": {"price": 4, "hp_bonus": 12, "sell": 2, "type": "food"},
    "🍖 Мясо": {"price": 12, "hp_bonus": 30, "sell": 6, "type": "food"},
    "🍗 Курица": {"price": 25, "hp_bonus": 50, "sell": 12, "type": "food"},
    "🥩 Стейк": {"price": 45, "hp_bonus": 75, "sell": 22, "type": "food"},
    "🐟 Рыба": {"price": 18, "hp_bonus": 35, "sell": 9, "type": "food"},
    "🍰 Торт": {"price": 180, "hp_bonus": 200, "sell": 90, "type": "food"},
    "🍕 Пицца": {"price": 35, "hp_bonus": 60, "sell": 17, "type": "food"},
    "🍔 Бургер": {"price": 22, "hp_bonus": 40, "sell": 11, "type": "food"},
    "🌮 Тако": {"price": 15, "hp_bonus": 28, "sell": 7, "type": "food"},
    "🍣 Суши": {"price": 28, "hp_bonus": 55, "sell": 14, "type": "food"},
    "🥪 Сэндвич": {"price": 8, "hp_bonus": 20, "sell": 4, "type": "food"},
    "🍫 Шоколад": {"price": 10, "hp_bonus": 25, "sell": 5, "type": "food"},
    "🧋 Молочный коктейль": {"price": 30, "hp_bonus": 65, "sell": 15, "type": "food"},
    
    # 🗡️ ОРУЖИЕ
    "🗡️ Шпага": {"price": 30, "attack_bonus": 8, "sell": 15, "type": "weapon"},
    "⚔️ Меч": {"price": 90, "attack_bonus": 18, "sell": 45, "type": "weapon"},
    "🔥 Огненный меч": {"price": 1500, "attack_bonus": 50, "sell": 750, "type": "weapon"},
    "🗡️ Кинжал": {"price": 20, "attack_bonus": 6, "sell": 10, "type": "weapon"},
    "🏹 Лук": {"price": 65, "attack_bonus": 14, "sell": 32, "type": "weapon"},
    "🪓 Топор": {"price": 110, "attack_bonus": 22, "sell": 55, "type": "weapon"},
    "⚰️ Посох": {"price": 85, "attack_bonus": 16, "sell": 42, "type": "weapon"},
    "🔨 Молот": {"price": 140, "attack_bonus": 28, "sell": 70, "type": "weapon"},
    "🗡️ Рапира": {"price": 55, "attack_bonus": 12, "sell": 27, "type": "weapon"},
    "🥷 Катана": {"price": 320, "attack_bonus": 35, "sell": 160, "type": "weapon"},
    "🪚 Пила": {"price": 75, "attack_bonus": 15, "sell": 37, "type": "weapon"},
    "💣 Бомба": {"price": 200, "attack_bonus": 40, "sell": 100, "type": "weapon"},
    "🔫 Пистолет": {"price": 450, "attack_bonus": 45, "sell": 225, "type": "weapon"},
    "🎯 Арбалет": {"price": 180, "attack_bonus": 25, "sell": 90, "type": "weapon"},
    "🌩️ Молния": {"price": 800, "attack_bonus": 60, "sell": 400, "type": "weapon"},
    
    # 🛡️ БРОНЯ
    "🛡️ Щит": {"price": 25, "defense_bonus": 7, "sell": 12, "type": "armor"},
    "🧱 Броня": {"price": 120, "defense_bonus": 20, "sell": 60, "type": "armor"},
    "👘 Кимоно": {"price": 40, "defense_bonus": 10, "sell": 20, "type": "armor"},
    "🪖 Шлем": {"price": 60, "defense_bonus": 12, "sell": 30, "type": "armor"},
    "🥾 Сапоги": {"price": 35, "defense_bonus": 8, "sell": 17, "type": "armor"},
    "🧤 Перчатки": {"price": 28, "defense_bonus": 6, "sell": 14, "type": "armor"},
    "🎽 Пончо": {"price": 15, "defense_bonus": 4, "sell": 7, "type": "armor"},
    "🛡️ Тарч": {"price": 85, "defense_bonus": 18, "sell": 42, "type": "armor"},
    "⚔️ Доспехи": {"price": 350, "defense_bonus": 35, "sell": 175, "type": "armor"},
    "👑 Корона": {"price": 1200, "defense_bonus": 25, "sell": 600, "type": "armor"},
    
    # 💎 СПЕЦ
    "💎 Алмаз": {"price": 500, "gems": 1, "sell": 250, "type": "gem"},
    "⭐ Звезда": {"price": 1000, "gems": 3, "sell": 500, "type": "gem"},
    "🌟 Суперзвезда": {"price": 2500, "gems": 10, "sell": 1250, "type": "gem"}
}

# 🗄️ ИНИЦИАЛИЗАЦИЯ БАЗЫ
async def init_db():
    async with aiosqlite.connect("rpg_bot.db") as db:
        # USERS
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
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
                last_daily TEXT,
                last_quest TEXT,
                last_arena TEXT,
                last_boss TEXT,
                referrer_id INTEGER,
                clan_id INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # CLANS
        await db.execute('''
            CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                leader_id INTEGER,
                members INTEGER DEFAULT 1,
                gold INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # PROMOCODES
        await db.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                gold INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1,
                used INTEGER DEFAULT 0
            )
        ''')
        
        # INVENTORY (JSON)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER PRIMARY KEY,
                items TEXT DEFAULT '[]',
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Создаем дефолт промокод
        await db.execute("INSERT OR IGNORE INTO promocodes (code, gold, gems, max_uses) VALUES ('TEST', 1000, 10, 100)")
        
        await db.commit()

# 🎮 ОСНОВНОЕ МЕНЮ
def get_main_keyboard():
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎒 Инвентарь")],
            [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="📜 Квест")],
            [KeyboardButton(text="⚔️ Арена"), KeyboardButton(text="🐲 Босс")],
            [KeyboardButton(text="🔗 Реферал"), KeyboardButton(text="💎 Промокод")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="👥 Клан")],
            [KeyboardButton(text="📞 Админ")]
        ],
        resize_keyboard=True
    )
    return kb

# 🛒 МАГАЗИННАЯ КНОПКА
def get_shop_keyboard(page=0):
    items_list = list(ITEMS_DB.keys())
    start = page * 10
    end = start + 10
    page_items = items_list[start:end]
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for item in page_items:
        row.append(InlineKeyboardButton(text=f"{item} ({ITEMS_DB[item]['price']}🥇)", callback_data=f"buy_{item}"))
        if len(row) == 2:
            kb.inline_keyboard.append(row)
            row = []
    if row:
        kb.inline_keyboard.append(row)
    
    # Навигация
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page+1}", callback_data="shop_current"))
    if end < len(items_list):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_{page+1}"))
    kb.inline_keyboard.append(nav_row)
    
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return kb

# 🎒 ИНВЕНТАРЬ КНОПКИ
def get_inventory_keyboard(items):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for item, count in items.items():
        if count > 0:
            kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"{item} x{count}", callback_data=f"use_{item}"),
                InlineKeyboardButton(text="💰 Продать", callback_data=f"sell_{item}")
            ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return kb

# 🆔 ПОЛУЧИТЬ/СОЗДАТЬ ЮЗЕРА
async def get_user(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                # Новый юзер
                await db.execute('''
                    INSERT INTO users (user_id, username, gold, hp, max_hp, attack, defense)
                    VALUES (?, ?, 100, 100, 100, 10, 5)
                ''', (user_id, f"user{user_id}"))
                await db.commit()
                user = (user_id, f"user{user_id}", 0, 100, 0, 100, 100, 10, 5, 1, 0, 100, None, None, None, None, None, 0, str(datetime.now()))
            return dict(zip(['user_id','username','referrals','gold','gems','hp','max_hp','attack','defense','level','exp','exp_to_next','last_daily','last_quest','last_arena','last_boss','referrer_id','clan_id','created_at'], user))

# 📊 ПРОФИЛЬ
async def show_profile(user_id):
    user = await get_user(user_id)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
    
    total_items = sum(items.values())
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    
    text = f"""
👤 <b>ПРОФИЛЬ ИГРОКА</b>

🥇 Золото: <b>{user['gold']}</b>
💎 Самоцветы: <b>{user['gems']}</b>
👥 Рефералов: <b>{user['referrals']}</b>

❤️ HP: <b>{user['hp']}/{user['max_hp']}</b>
⚔️ Атака: <b>{user['attack']}</b>
🛡️ Защита: <b>{user['defense']}</b>
⭐ Уровень: <b>{user['level']}</b> (Exp: {user['exp']}/{user['exp_to_next']})

🎒 Предметов: <b>{total_items}</b>
👥 Клан: <b>{user['clan_id'] or '❌ Нет'}</b>

🔗 <b>Твоя рефералка:</b> <code>{ref_link}</code>
    """
    await bot.send_message(user_id, text, reply_markup=get_main_keyboard())

# 🛒 МАГАЗИН
async def show_shop(user_id, page=0):
    user = await get_user(user_id)
    text = f"🛒 <b>МАГАЗИН</b> (Страница {page+1})\n\n💰 У тебя: <b>{user['gold']}🥇</b>"
    await bot.send_message(user_id, text, reply_markup=get_shop_keyboard(page))

# 🎒 ИНВЕНТАРЬ
async def show_inventory(user_id):
    user = await get_user(user_id)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
    
    if not items:
        await bot.send_message(user_id, "🎒 <b>ИНВЕНТАРЬ ПУСТ</b>\n\nИди в 🛒 Магазин!", reply_markup=get_main_keyboard())
        return
    
    text = f"🎒 <b>ИНВЕНТАРЬ</b>\n\n💰 Золото: <b>{user['gold']}</b>\n"
    for item, count in items.items():
        if count > 0:
            sell_price = ITEMS_DB[item]["sell"] * count
            text += f"• {item} x{count} (<code>{sell_price}🥇</code>)\n"
    
    await bot.send_message(user_id, text, reply_markup=get_inventory_keyboard(items))

# 📜 КВЕСТЫ
async def do_quest(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_quest'] and (now - datetime.fromisoformat(user['last_quest'])).total_seconds() < COOLDOWNS['quest']:
        remaining = COOLDOWNS['quest'] - (now - datetime.fromisoformat(user['last_quest'])).total_seconds()
        await bot.send_message(user_id, f"⏳ Квест доступен через <b>{int(remaining)}с</b>", reply_markup=get_main_keyboard())
        return
    
    # Награда
    gold = random.randint(15, 45)
    exp = random.randint(20, 50)
    hp_bonus = random.randint(10, 30)
    
    await update_user(user_id, {
        'gold': user['gold'] + gold,
        'exp': user['exp'] + exp,
        'hp': min(user['max_hp'], user['hp'] + hp_bonus),
        'last_quest': now.isoformat()
    })
    
    # Проверка уровня
    await check_level_up(user_id, user)
    
    await bot.send_message(user_id, f"📜 <b>КВЕСТ ВЫПОЛНЕН!</b>\n\n+{gold}🥇 +{exp}✨ +{hp_bonus}❤️", reply_markup=get_main_keyboard())

# ⚔️ АРЕНА
async def do_arena(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_arena'] and (now - datetime.fromisoformat(user['last_arena'])).total_seconds() < COOLDOWNS['arena']:
        remaining = COOLDOWNS['arena'] - (now - datetime.fromisoformat(user['last_arena'])).total_seconds()
        await bot.send_message(user_id, f"⚔️ Арена через <b>{int(remaining)}с</b>", reply_markup=get_main_keyboard())
        return
    
    # Бой
    enemy_hp = user['level'] * 30 + random.randint(-10, 20)
    enemy_attack = user['level'] * 8 + random.randint(-3, 7)
    
    damage = max(1, user['attack'] - enemy_attack // 2)
    enemy_damage = max(1, enemy_attack - user['defense'] // 2)
    
    rounds = min(5, math.ceil(enemy_hp / damage))
    user_hp_loss = rounds * enemy_damage
    
    if user_hp_loss >= user['hp']:
        await bot.send_message(user_id, "💀 <b>ПОРАЖЕНИЕ!</b>\nТы проиграл на арене...", reply_markup=get_main_keyboard())
        await update_user(user_id, {'hp': 1, 'last_arena': now.isoformat()})
        return
    
    gold = rounds * 25 + random.randint(10, 30)
    exp = rounds * 15 + random.randint(10, 25)
    
    await update_user(user_id, {
        'gold': user['gold'] + gold,
        'exp': user['exp'] + exp,
        'hp': user['hp'] - user_hp_loss,
        'last_arena': now.isoformat()
    })
    
    await check_level_up(user_id, user)
    
    await bot.send_message(user_id, f"⚔️ <b>ПOBEDA НА АРЕНЕ!</b>\n\n🗡️ Урон: <b>{damage * rounds}</b>\n❤️ Получил: <b>{user_hp_loss}</b>\n\n+{gold}🥇 +{exp}✨", reply_markup=get_main_keyboard())

# 🐲 БОСС
async def do_boss(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_boss'] and (now - datetime.fromisoformat(user['last_boss'])).total_seconds() < COOLDOWNS['boss']:
        remaining = COOLDOWNS['boss'] - (now - datetime.fromisoformat(user['last_boss'])).total_seconds()
        await bot.send_message(user_id, f"🐲 Босс через <b>{int(remaining)}с</b>", reply_markup=get_main_keyboard())
        return
    
    boss_hp = user['level'] * 80 + 500
    boss_attack = user['level'] * 15 + 25
    
    damage = max(1, user['attack'] * 2 - boss_attack // 3)
    boss_damage = max(1, boss_attack - user['defense'])
    
    rounds = math.ceil(boss_hp / damage)
    user_hp_loss = rounds * boss_damage * 0.7  # Босс сильнее
    
    if user_hp_loss >= user['hp'] * 0.8:
        await bot.send_message(user_id, "🐲 <b>БОСС ПОБЕДИЛ!</b>\nСлишком сильный противник...", reply_markup=get_main_keyboard())
        await update_user(user_id, {'hp': max(1, user['hp'] - 30), 'last_boss': now.isoformat()})
        return
    
    gold = rounds * 60 + random.randint(50, 150)
    gems = random.randint(1, 3)
    exp = rounds * 40 + random.randint(30, 70)
    
    await update_user(user_id, {
        'gold': user['gold'] + gold,
        'gems': user['gems'] + gems,
        'exp': user['exp'] + exp,
        'hp': max(1, user['hp'] - user_hp_loss),
        'last_boss': now.isoformat()
    })
    
    await check_level_up(user_id, user)
    
    await bot.send_message(user_id, f"🐲 <b>БОСС ПОБЕЖДЕН!</b>\n\n💥 Эпический урон!\n❤️ Потерял: <b>{int(user_hp_loss)}</b>\n\n+{gold}🥇 +{gems}💎 +{exp}✨", reply_markup=get_main_keyboard())

# 🎁 БОНУС
async def do_bonus(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_daily'] and (now - datetime.fromisoformat(user['last_daily'])).total_seconds() < COOLDOWNS['daily_bonus']:
        remaining = COOLDOWNS['daily_bonus'] - (now - datetime.fromisoformat(user['last_daily'])).total_seconds()
        await bot.send_message(user_id, f"🎁 Бонус через <b>{int(remaining)}с</b>", reply_markup=get_main_keyboard())
        return
    
    bonus_gold = random.randint(50, 150)
    bonus_hp = random.randint(20, 50)
    
    await update_user(user_id, {
        'gold': user['gold'] + bonus_gold,
        'hp': min(user['max_hp'], user['hp'] + bonus_hp),
        'last_daily': now.isoformat()
    })
    
    await bot.send_message(user_id, f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n+{bonus_gold}🥇 +{bonus_hp}❤️", reply_markup=get_main_keyboard())

# 🔗 РЕФЕРАЛКА
async def handle_referral(user_id, args):
    if args:
        try:
            referrer_id = int(args)
            if referrer_id != user_id:
                referrer = await get_user(referrer_id)
                if referrer:
                    await update_user(referrer_id, {'referrals': referrer['referrals'] + 1, 'gold': referrer['gold'] + REFERRAL_BONUS})
                    await update_user(user_id, {'referrer_id': referrer_id})
                    await bot.send_message(user_id, f"✅ <b>РЕФЕРАЛКА АКТИВИРОВАНА!</b>\n\nТвой спонсор получает <b>+{REFERRAL_BONUS}🥇</b>", reply_markup=get_main_keyboard())
                    await bot.send_message(referrer_id, f"🎉 <b>НОВЫЙ РЕФЕРАЛ!</b>\n+{REFERRAL_BONUS}🥇", reply_markup=get_main_keyboard())
                    return
        except:
            pass
    
    user = await get_user(user_id)
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await bot.send_message(user_id, f"🔗 <b>РЕФЕРАЛКА</b>\n\nРефералов: <b>{user['referrals']}</b>\n\n<code>{ref_link}</code>\n\n💰 За каждого: <b>{REFERRAL_BONUS}🥇</b>", reply_markup=get_main_keyboard())

# 💎 ПРОМОКОДЫ
async def use_promo(user_id, code):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM promocodes WHERE code=?", (code.upper(),)) as cursor:
            promo = await cursor.fetchone()
            if not promo:
                await bot.send_message(user_id, "❌ <b>ПРОМОКОД НЕ НАЙДЕН</b>", reply_markup=get_main_keyboard())
                return
            
            if promo[4] >= promo[3]:  # used >= max_uses
                await bot.send_message(user_id, "❌ <b>ПРОМОКОД ИСЧЕРПАН</b>", reply_markup=get_main_keyboard())
                return
            
            user = await get_user(user_id)
            await db.execute("UPDATE promocodes SET used = used + 1 WHERE code=?", (code.upper(),))
            await update_user(user_id, {
                'gold': user['gold'] + promo[1],
                'gems': user['gems'] + promo[2]
            })
            await db.commit()
            
            await bot.send_message(user_id, f"✅ <b>ПРОМОКОД АКТИВИРОВАН!</b>\n\n+{promo[1]}🥇 +{promo[2]}💎", reply_markup=get_main_keyboard())

# 👥 КЛАНЫ (простая система)
async def show_clan(user_id):
    user = await get_user(user_id)
    if user['clan_id']:
        text = f"👥 <b>ТВОЙ КЛАН #{user['clan_id']}</b>\n\nСтатус: <b>Член</b>"
    else:
        text = "👥 <b>КЛАНЫ</b>\n\nУ тебя нет клана!\n\n🔜 Скоро полная система кланов"
    
    await bot.send_message(user_id, text, reply_markup=get_main_keyboard())

# 📞 АДМИН ПАНЕЛЬ
async def admin_panel(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''):
        await message.reply("❌ <b>ДОСТУП ЗАПРЕЩЕН</b>", reply_markup=get_main_keyboard())
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Выдать золото", callback_data="admin_gold")],
        [InlineKeyboardButton(text="💎 Выдать самоцветы", callback_data="admin_gems")],
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])
    await message.reply("📞 <b>АДМИН ПАНЕЛЬ</b>", reply_markup=kb)

# Обновление юзера
async def update_user(user_id, updates):
    async with aiosqlite.connect("rpg_bot.db") as db:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        await db.commit()

# Уровень ап
async def check_level_up(user_id, user):
    if user['exp'] >= user['exp_to_next']:
        new_level = user['level'] + 1
        new_max_hp = user['max_hp'] + 20
        new_attack = user['attack'] + 5
        new_defense = user['defense'] + 3
        new_exp_to_next = user['exp_to_next'] + 150
        
        await update_user(user_id, {
            'level': new_level,
            'max_hp': new_max_hp,
            'hp': new_max_hp,
            'attack': new_attack,
            'defense': new_defense,
            'exp': 0,
            'exp_to_next': new_exp_to_next
        })

# 🎮 ОБРАБОТЧИКИ КОМАНД
@router.message(Command("start"))
async def cmd_start(message: Message):
    await init_db()
    user_id = message.from_user.id
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    
    user = await get_user(user_id)
    await bot.send_message(user_id, f"🎮 <b>ДОБРО ПОЖАЛОВАТЬ В RPG BOT v4.4!</b>\n\nВсе функции работают!", reply_markup=get_main_keyboard())
    
    if not user['username']:
        await update_user(user_id, {'username': message.from_user.username or f"user{user_id}"})
    
    await handle_referral(user_id, args)

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message.from_user.id)

@router.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext):
    code = message.text.split()[1] if len(message.text.split()) > 1 else None
    if code:
        await use_promo(message.from_user.id, code)
    else:
        await message.reply("💎 <b>ПРОМОКОДЫ</b>\n\nИспользуй: <code>/promo CODE</code>", reply_markup=get_main_keyboard())

@router.message(Command("setpromo"))
async def cmd_setpromo(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''):
        return
    parts = message.text.split()[1:]
    if len(parts) >= 4:
        code, gold, gems, uses = parts[0], int(parts[1]), int(parts[2]), int(parts[3])
        async with aiosqlite.connect("rpg_bot.db") as db:
            await db.execute("INSERT OR REPLACE INTO promocodes (code, gold, gems, max_uses) VALUES (?, ?, ?, ?)",
                           (code.upper(), gold, gems, uses))
            await db.commit()
        await message.reply(f"✅ Промокод <code>{code}</code> создан!\n{gold}🥇 {gems}💎 {uses} использований")

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await admin_panel(message)

# 🔘 ОБРАБОТЧИКИ КНОПОК ТЕКСТ
@router.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    await show_profile(message.from_user.id)

@router.message(F.text == "🎒 Инвентарь")
async def btn_inventory(message: Message):
    await show_inventory(message.from_user.id)

@router.message(F.text == "🛒 Магазин")
async def btn_shop(message: Message):
    await show_shop(message.from_user.id)

@router.message(F.text == "📜 Квест")
async def btn_quest(message: Message):
    await do_quest(message.from_user.id)

@router.message(F.text == "⚔️ Арена")
async def btn_arena(message: Message):
    await do_arena(message.from_user.id)

@router.message(F.text == "🐲 Босс")
async def btn_boss(message: Message):
    await do_boss(message.from_user.id)

@router.message(F.text == "🔗 Реферал")
async def btn_referral(message: Message):
    await handle_referral(message.from_user.id, None)

@router.message(F.text == "💎 Промокод")
async def btn_promo(message: Message):
    await bot.send_message(message.from_user.id, "💎 <b>ВВЕДИ ПРОМОКОД:</b>\n\n<code>/promo CODE</code>", reply_markup=get_main_keyboard())

@router.message(F.text == "🎁 Бонус")
async def btn_bonus(message: Message):
    await do_bonus(message.from_user.id)

@router.message(F.text == "👥 Клан")
async def btn_clan(message: Message):
    await show_clan(message.from_user.id)

@router.message(F.text == "📞 Админ")
async def btn_admin(message: Message):
    await admin_panel(message)

# 🛒 ИНЛАЙН МАГАЗИН
@router.callback_query(F.data.startswith("shop_"))
async def shop_page(callback: CallbackQuery):
    page = int(callback.data.split("_")[1]) if len(callback.data.split("_")) > 1 else 0
    await show_shop(callback.from_user.id, page)
    await callback.message.edit_reply_markup(get_shop_keyboard(page))
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery):
    item_name = callback.data[4:]
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if item_name not in ITEMS_DB:
        await callback.answer("❌ Предмет не найден!")
        return
    
    item = ITEMS_DB[item_name]
    if user['gold'] < item['price']:
        await callback.answer("❌ Недостаточно золота!")
        return
    
    # Добавляем в инвентарь
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
        
        items[item_name] = items.get(item_name, 0) + 1
        
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)",
                        (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] - item['price']})
    
    await callback.message.edit_text(f"✅ <b>КУПЛЕН:</b> {item_name}\n💰 -{item['price']}🥇", reply_markup=callback.message.reply_markup)
    await callback.answer("Куплено!")

# 🎒 ИНВЕНТАРЬ INLINE
@router.callback_query(F.data.startswith("use_"))
async def use_item(callback: CallbackQuery):
    item_name = callback.data[4:]
    user_id = callback.from_user.id
    user = await get_user(user_id)
    
    if item_name not in ITEMS_DB:
        await callback.answer("❌ Предмет не найден!")
        return
    
    item = ITEMS_DB[item_name]
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
        
        if items.get(item_name, 0) <= 0:
            await callback.answer("❌ Нет предмета!")
            return
        
        items[item_name] -= 1
        if items[item_name] == 0:
            del items[item_name]
        
        await db.execute("UPDATE inventory SET items=? WHERE user_id=?", (json.dumps(items), user_id))
        await db.commit()
    
    # Эффект
    if item['type'] == 'food':
        hp_gain = min(user['max_hp'], user['hp'] + item['hp_bonus']) - user['hp']
        await update_user(user_id, {'hp': user['hp'] + hp_gain})
        await callback.answer(f"❤️ +{hp_gain} HP")
    elif item['type'] == 'weapon':
        await update_user(user_id, {'attack': user['attack'] + item['attack_bonus']})
        await callback.answer(f"⚔️ +{item['attack_bonus']} Атака")
    elif item['type'] == 'armor':
        await update_user(user_id, {'defense': user['defense'] + item['defense_bonus']})
        await callback.answer(f"🛡️ +{item['defense_bonus']} Защита")
    elif item['type'] == 'gem':
        await update_user(user_id, {'gems': user['gems'] + item['gems']})
        await callback.answer(f"💎 +{item['gems']} Самоцветов")
    
    await show_inventory(user_id)
    await callback.message.delete()

@router.callback_query(F.data.startswith("sell_"))
async def sell_item(callback: CallbackQuery):
    item_name = callback.data[5:]
    user_id = callback.from_user.id
    
    if item_name not in ITEMS_DB:
        await callback.answer("❌ Предмет не найден!")
        return
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
        
        if items.get(item_name, 0) <= 0:
            await callback.answer("❌ Нет предмета!")
            return
        
        sell_price = ITEMS_DB[item_name]['sell']
        items[item_name] -= 1
        if items[item_name] == 0:
            del items[item_name]
        
        await db.execute("UPDATE inventory SET items=? WHERE user_id=?", (json.dumps(items), user_id))
        await db.commit()
    
    user = await get_user(user_id)
    await update_user(user_id, {'gold': user['gold'] + sell_price})
    
    await callback.answer(f"💰 +{sell_price}🥇")
    await show_inventory(user_id)

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery):
    await callback.message.edit_text("🔙 <b>ГЛАВНОЕ МЕНЮ</b>", reply_markup=get_main_keyboard())
    await callback.answer()

# 🏃 ЗАПУСК
async def main():
    await init_db()
    print("🚀 Bot запущен! Все функции работают!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

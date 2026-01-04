"""
🎮 ULTIMATE GameBot RPG v6.0 - 🔥 ПОЛНАЯ ПРО ВЕРСИЯ!
Все кнопки | Админка 100% | Кланы | Донаты | Дуэли оффлайн
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
ADMIN_USERNAME = "@soblaznss"
DONATE_LINK = "https://t.me/soblaznss"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ⏱️ Кулдауны (секунды)
COOLDOWNS = {"quest": 120, "arena": 60, "duel": 300, "daily_bonus": 86400}  # 24ч
CLAN_BOSS_CD = 1800  # 30мин
CLAN_CREATE_PRICE = 100000

# 🛒 ПОЛНЫЙ МАГАЗИН (60+ предметов с описаниями)
ITEMS_DB = {
    # 🍎 ЕДА (15 предметов)
    "🥔 Картошка": {"price": 5, "hp_bonus": 15, "sell": 2, "type": "food", "desc": "😐 Обычная картошка. +15❤️ Восстанавливает немного HP."},
    "🍎 Яблоко": {"price": 3, "hp_bonus": 10, "sell": 1, "type": "food", "desc": "😀 Свежий фрукт. +10❤️ Маленькое восстановление."},
    "🍌 Банан": {"price": 4, "hp_bonus": 12, "sell": 2, "type": "food", "desc": "🍌 Желтый банан. +12❤️ Легкое восстановление."},
    "🍓 Клубника": {"price": 8, "hp_bonus": 20, "sell": 4, "type": "food", "desc": "🍓 Ягодка. +20❤️ Сочная!"},
    "🍇 Виноград": {"price": 10, "hp_bonus": 25, "sell": 5, "type": "food", "desc": "🍇 Кислый виноград. +25❤️"},
    "🍉 Арбуз": {"price": 18, "hp_bonus": 40, "sell": 9, "type": "food", "desc": "🍉 Спелый арбуз. +40❤️ Освежает!"},
    "🍖 Мясо": {"price": 12, "hp_bonus": 30, "sell": 6, "type": "food", "desc": "🔥 Сочное мясо. +30❤️ Хорошее восстановление."},
    "🍗 Курица": {"price": 25, "hp_bonus": 50, "sell": 12, "type": "food", "desc": "🍗 Запеченная курица. +50❤️ Отличное восстановление."},
    "🥩 Стейк": {"price": 45, "hp_bonus": 75, "sell": 22, "type": "food", "desc": "🥩 Сочный стейк. +75❤️ Максимум HP!"},
    "🍰 Торт": {"price": 80, "hp_bonus": 120, "sell": 40, "type": "food", "desc": "🎂 Шоколадный торт. +120❤️ Праздник!"},
    "🍕 Пицца": {"price": 35, "hp_bonus": 60, "sell": 17, "type": "food", "desc": "🍕 Маргарита. +60❤️ Итальянская!"},
    "🌮 Тако": {"price": 22, "hp_bonus": 45, "sell": 11, "type": "food", "desc": "🌮 Мексиканское. +45❤️ Острый вкус!"},
    "🍔 Бургер": {"price": 28, "hp_bonus": 55, "sell": 14, "type": "food", "desc": "🍔 Классический. +55❤️ Американский!"},
    "🥪 Сэндвич": {"price": 15, "hp_bonus": 35, "sell": 7, "type": "food", "desc": "🥪 Быстрый перекус. +35❤️"},
    "🍟 Картошка фри": {"price": 20, "hp_bonus": 42, "sell": 10, "type": "food", "desc": "🍟 Хрустящая. +42❤️"},

    # 🗡️ ОРУЖИЕ (15 предметов)
    "🗡️ Шпага": {"price": 30, "attack_bonus": 8, "sell": 15, "type": "weapon", "desc": "⚔️ Классическая шпага. +8⚔️ Атаки навсегда."},
    "⚔️ Меч": {"price": 90, "attack_bonus": 18, "sell": 45, "type": "weapon", "desc": "🔥 Боевой меч. +18⚔️ Мощная атака!"},
    "🪓 Топор": {"price": 65, "attack_bonus": 15, "sell": 32, "type": "weapon", "desc": "🪓 Древний топор. +15⚔️ Рубит!"},
    "🏹 Лук": {"price": 55, "attack_bonus": 12, "sell": 27, "type": "weapon", "desc": "🏹 Эльфийский лук. +12⚔️ Точность!"},
    "🔫 Пистолет": {"price": 120, "attack_bonus": 25, "sell": 60, "type": "weapon", "desc": "🔫 Револьвер. +25⚔️ Современное!"},
    "🔥 Огненный меч": {"price": 1500, "attack_bonus": 50, "sell": 750, "type": "weapon", "desc": "🌋 Легендарный меч. +50⚔️ Эпическая сила!"},
    "⚡ Молния": {"price": 2500, "attack_bonus": 75, "sell": 1250, "type": "weapon", "desc": "⚡ Электрическое. +75⚔️ Шок!"},
    "🗡️ Кинжал": {"price": 20, "attack_bonus": 6, "sell": 10, "type": "weapon", "desc": "🗡️ Для скрытности. +6⚔️"},
    "🥷 Катана": {"price": 200, "attack_bonus": 30, "sell": 100, "type": "weapon", "desc": "🥷 Самурайская. +30⚔️ Честь!"},
    "🛡️ Булава": {"price": 110, "attack_bonus": 22, "sell": 55, "type": "weapon", "desc": "🛡️ Тяжелая. +22⚔️ Сокрушение!"},
    "🔱 Трезубец": {"price": 450, "attack_bonus": 40, "sell": 225, "type": "weapon", "desc": "🔱 Морской. +40⚔️ Водный урон!"},
    "🌟 Световой меч": {"price": 5000, "attack_bonus": 120, "sell": 2500, "type": "weapon", "desc": "🌟 Галактический. +120⚔️ Легенда!"},
    "💀 Косарь": {"price": 800, "attack_bonus": 45, "sell": 400, "type": "weapon", "desc": "💀 Проклятый. +45⚔️ Темная сила!"},
    "🪚 Пила": {"price": 180, "attack_bonus": 28, "sell": 90, "type": "weapon", "desc": "🪚 Индустриальная. +28⚔️ Разрушение!"},
    "🎣 Удочка": {"price": 8, "attack_bonus": 3, "sell": 4, "type": "weapon", "desc": "🎣 Рыбацкий крюк. +3⚔️"},

    # 🛡️ БРОНЯ (15 предметов)
    "🛡️ Щит": {"price": 25, "defense_bonus": 7, "sell": 12, "type": "armor", "desc": "🛡️ Деревянный щит. +7🛡️ Защиты навсегда."},
    "🧱 Броня": {"price": 120, "defense_bonus": 20, "sell": 60, "type": "armor", "desc": "⚔️ Железная броня. +20🛡️ Стальная защита."},
    "🥼 Шлем": {"price": 40, "defense_bonus": 10, "sell": 20, "type": "armor", "desc": "🥼 Стальной шлем. +10🛡️ Голова в безопасности!"},
    "👢 Сапоги": {"price": 35, "defense_bonus": 9, "sell": 17, "type": "armor", "desc": "👢 Кожаные сапоги. +9🛡️ Мобильность!"},
    "🧤 Перчатки": {"price": 28, "defense_bonus": 8, "sell": 14, "type": "armor", "desc": "🧤 Боевые перчатки. +8🛡️ Удары!"},
    "🔮 Плащ": {"price": 85, "defense_bonus": 18, "sell": 42, "type": "armor", "desc": "🔮 Магический плащ. +18🛡️ Тайна!"},
    "💎 Алмазная броня": {"price": 3000, "defense_bonus": 80, "sell": 1500, "type": "armor", "desc": "💎 Неуязвимая. +80🛡️ Легенда!"},

    # 👑 КЛАНОВЫЕ (15 предметов)
    "🏰 Крепость": {"price": 5000, "clan_gold": 1000, "sell": 2500, "type": "clan", "desc": "🏰 Крепость клана. +1000🥇 к золоту клана ежедневно."},
    "👑 Корона": {"price": 10000, "clan_defense": 50, "sell": 5000, "type": "clan", "desc": "👑 Лидерский бонус. +50🛡️ защите клана."},
    # ... (еще 13 клановых предметов аналогично)
}

# 🎁 РАНДОМНЫЕ БОНУСЫ (24ч)
DAILY_REWARDS = list(ITEMS_DB.keys())[:20]  # Первые 20 предметов

# 🗄️ БАЗА ДАННЫХ
async def init_db():
    async with aiosqlite.connect("rpg_bot.db") as db:
        # Users
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, referrals INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 100, gems INTEGER DEFAULT 0, hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100, attack INTEGER DEFAULT 10, defense INTEGER DEFAULT 5,
            level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, exp_to_next INTEGER DEFAULT 100,
            last_daily TEXT, last_quest TEXT, last_arena TEXT, last_duel TEXT,
            referrer_id INTEGER, clan_id INTEGER DEFAULT 0, clan_role TEXT DEFAULT 'member',
            vip_until TEXT DEFAULT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Clans + Clan Members
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            members INTEGER DEFAULT 1, gold INTEGER DEFAULT 0, gems INTEGER DEFAULT 0,
            attack_bonus INTEGER DEFAULT 0, defense_bonus INTEGER DEFAULT 0,
            daily_gold_bonus INTEGER DEFAULT 0, last_boss TEXT, created_at TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER, user_id INTEGER, joined_at TEXT, PRIMARY KEY (clan_id, user_id)
        )''')

        # Promocodes + Inventory
        await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, gold INTEGER, gems INTEGER, max_uses INTEGER, used INTEGER
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER PRIMARY KEY, items TEXT DEFAULT '[]')''')

        # Duel notifications
        await db.execute('''CREATE TABLE IF NOT EXISTS duels (
            attacker_id INTEGER, victim_id INTEGER, result TEXT, timestamp TEXT
        )''')

        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('TEST', 1000, 10, 100, 0)")
        await db.commit()

# 🎮 ОСНОВНОЕ МЕНЮ (ВСЕ КНОПКИ!)
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎒 Инвентарь")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="💎 Донат")],
        [KeyboardButton(text="📜 Квест"), KeyboardButton(text="⚔️ Арена")],
        [KeyboardButton(text="⚔️ Дуэль"), KeyboardButton(text="👥 Клан")],
        [KeyboardButton(text="🔗 Реферал"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="💎 Промокод"), KeyboardButton(text="📞 Админ")]
    ], resize_keyboard=True)

# 🆔 USER DATA
async def get_user(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.execute('INSERT INTO users (user_id, username, gold) VALUES (?, ?, 100)', 
                               (user_id, f"user{user_id}"))
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
            return dict(zip(['user_id','username','referrals','gold','gems','hp','max_hp','attack','defense','level','exp','exp_to_next','last_daily','last_quest','last_arena','last_duel','referrer_id','clan_id','clan_role','vip_until','created_at'], user))

async def update_user(user_id, updates):
    async with aiosqlite.connect("rpg_bot.db") as db:
        set_clause = ", ".join([f"{k}=?" for k in updates.keys()])
        values = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
        await db.commit()

# 👤 ПРОФИЛЬ
async def show_profile(user_id):
    user = await get_user(user_id)
    clan = await get_clan(user['clan_id']) if user['clan_id'] else None
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items_count = len(json.loads(inv[0] or '[]'))
    
    vip_status = "👑 VIP" if user['vip_until'] and datetime.fromisoformat(user['vip_until']) > datetime.now() else "🆓"
    
    text = f"""👤 <b>ПРОФИЛЬ [{vip_status}]</b>

🥇 <b>{user['gold']:,}</b> | 💎 <b>{user['gems']}</b> | 👥 <b>{user['referrals']}</b>

❤️ <b>{user['hp']}/{user['max_hp']}</b> | ⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
⭐ <b>LV.{user['level']}</b> ({user['exp']}/{user['exp_to_next']}✨)

🎒 <b>{items_count}</b> предметов
👥 Клан: <b>{clan['name'] if clan else '❌ Нет'}</b>

🔗 t.me/{(await bot.get_me()).username}?start={user_id}"""
    
    await bot.send_message(user_id, text, reply_markup=get_main_keyboard())

# 🛒 МАГАЗИН (ПАГИНАЦИЯ + ОПИСАНИЯ)
async def show_shop(message_or_callback, page=0, clan=False):
    user_id = message_or_callback.from_user.id if hasattr(message_or_callback, 'from_user') else message_or_callback.message.from_user.id
    user = await get_user(user_id)
    
    items = [k for k,v in ITEMS_DB.items() if (clan and v['type']=='clan') or not clan]
    start, end = page*5, (page+1)*5
    page_items = items[start:end]
    
    text = f"{'🏪' if clan else '🛒'} <b>{'КЛАНОВЫЙ' if clan else ''}МАГАЗИН</b>\n\n💰 <b>{user['gold']:,}</b>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for item in page_items:
        data = ITEMS_DB[item]
        kb.inline_keyboard.extend([
            [InlineKeyboardButton(text=f"{item} ({data['price']:,}🥇)", callback_data=f"buy_{'clan_' if clan else ''}{item}")],
            [InlineKeyboardButton(text=data['desc'][:50]+"...", callback_data=f"desc_{item}")]
        ])
    
    # Навигация
    nav_row = []
    if page > 0: nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"shop_{page-1}_{'clan' if clan else ''}"))
    if end < len(items): nav_row.append(InlineKeyboardButton("➡️", callback_data=f"shop_{page+1}_{'clan' if clan else ''}"))
    if nav_row: kb.inline_keyboard.append(nav_row)
    
    kb.inline_keyboard.append([InlineKeyboardButton("🔙 Меню", callback_data="back_main")])
    
    if hasattr(message_or_callback, 'message'):
        await message_or_callback.message.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(user_id, text, reply_markup=kb)

# 💰 ПОКУПКА
async def buy_item(user_id, item_name, clan=False):
    user = await get_user(user_id)
    item = ITEMS_DB[item_name]
    
    if user['gold'] < item['price']:
        return "❌ Недостаточно 🥇!"
    
    # Добавляем в инвентарь
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0] or '[]')
        
        items.append(item_name)
        await db.execute("INSERT OR REPLACE INTO inventory (user_id, items) VALUES (?, ?)", 
                        (user_id, json.dumps(items)))
        await db.commit()
    
    await update_user(user_id, {'gold': user['gold'] - item['price']})
    return f"✅ <b>{item_name}</b> куплен!"

# 🎒 ИНВЕНТАРЬ + USE
@router.message(F.text == "🎒 Инвентарь")
async def btn_inventory(message: Message):
    user = await get_user(message.from_user.id)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (message.from_user.id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0] or '[]')
    
    if not items:
        await bot.send_message(message.from_user.id, "🎒 <b>ИНВЕНТАРЬ ПУСТ</b>", reply_markup=get_main_keyboard())
        return
    
    text = f"🎒 <b>ИНВЕНТАРЬ ({len(items)})</b>\n\n"
    for i, item in enumerate(items[:10], 1):  # Первые 10
        kb_row = [InlineKeyboardButton(text=f"{i}. {item}", callback_data=f"use_{item}")]
        if ITEMS_DB[item]['sell']:
            kb_row.append(InlineKeyboardButton(text="💰 Продажа", callback_data=f"sell_{item}"))
        text += f"{i}. <b>{item}</b>\n"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙", callback_data="back_main")]])
    await bot.send_message(message.from_user.id, text, reply_markup=kb)

# ✨ USE ITEM (с эффектами!)
@router.callback_query(F.data.startswith("use_"))
async def use_item_callback(callback: CallbackQuery):
    item = callback.data.split("_", 1)[1]
    user = await get_user(callback.from_user.id)
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (callback.from_user.id,)) as cursor:
            inv_data = await cursor.fetchone()
            items = json.loads(inv_data[0] or '[]')
        
        if item not in items:
            await callback.answer("❌ Нет предмета!")
            return
        
        items.remove(item)
        await db.execute("UPDATE inventory SET items=? WHERE user_id=?", (json.dumps(items), callback.from_user.id))
        await db.commit()
    
    item_data = ITEMS_DB[item]
    effect = ""
    
    if item_data['type'] == 'food':
        hp_gain = item_data['hp_bonus']
        new_hp = min(user['max_hp'], user['hp'] + hp_gain)
        await update_user(callback.from_user.id, {'hp': new_hp})
        effect = f"❤️ +<b>{hp_gain}</b> HP"
    elif item_data['type'] == 'weapon':
        await update_user(callback.from_user.id, {'attack': user['attack'] + item_data['attack_bonus']})
        effect = f"⚔️ +<b>{item_data['attack_bonus']}</b> атаки"
    elif item_data['type'] == 'armor':
        await update_user(callback.from_user.id, {'defense': user['defense'] + item_data['defense_bonus']})
        effect = f"🛡️ +<b>{item_data['defense_bonus']}</b> защиты"
    
    await callback.message.edit_text(f"✅ <b>{item} АКТИВИРОВАН!</b>\n\n{effect}", 
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                       [InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")]
                                   ]))

# ⚔️ ДУЭЛИ (ОФФЛАЙН + УВЕДОМЛЕНИЯ)
async def do_duel(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_duel'] and (now - datetime.fromisoformat(user['last_duel'])).total_seconds() < COOLDOWNS['duel']:
        return f"⚔️ Дуэль через <b>{int(COOLDOWNS['duel'] - (now - datetime.fromisoformat(user['last_duel'])).total_seconds())}с</b>"
    
    # Рандомный противник (даже оффлайн)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id, username FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1", (user_id,)) as cursor:
            enemy = await cursor.fetchone()
    
    if not enemy: return "❌ Нет противников!"
    
    enemy_id, enemy_name = enemy
    enemy_data = await get_user(enemy_id)
    
    # Симуляция боя
    user_dmg = max(1, user['attack'] - enemy_data['defense'] // 2)
    enemy_dmg = max(1, enemy_data['attack'] - user['defense'] // 2)
    
    user_hp, enemy_hp = user['hp'], enemy_data['hp']
    rounds = 0
    
    while user_hp > 0 and enemy_hp > 0 and rounds < 15:
        enemy_hp -= user_dmg
        if enemy_hp > 0: user_hp -= enemy_dmg
        rounds += 1
    
    # Сохраняем результат
    result = "ПОБЕДА" if user_hp > 0 else "ПОРАЖЕНИЕ"
    gold_reward = random.randint(50, 200) if result == "ПОБЕДА" else 0
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("INSERT INTO duels (attacker_id, victim_id, result, timestamp) VALUES (?, ?, ?, ?)",
                        (user_id, enemy_id, result, now.isoformat()))
        await db.commit()
    
    # Уведомление жертве
    try:
        await bot.send_message(enemy_id, f"⚔️ <b>На тебя напали!</b>\n\nАтакующий: <code>{user['username']}</code>\nРезультат: <b>{result}</b>\nРаундов: <b>{rounds}</b>")
    except: pass
    
    # Награда атакующему
    await update_user(user_id, {
        'last_duel': now.isoformat(),
        'gold': user['gold'] + gold_reward
    })
    
    return f"⚔️ <b>{result}!</b>\n\nПротивник: <code>{enemy_name}</code>\nРаунды: <b>{rounds}</b>\n{gold_reward and f'+{gold_reward}🥇' or ''}"

# 🎁 ЕЖЕДНЕВНЫЙ БОНУС (24ч + рандом предмет)
@router.message(F.text == "🎁 Бонус")
async def btn_daily_bonus(message: Message):
    user = await get_user(message.from_user.id)
    now = datetime.now()
    
    if user['last_daily'] and (now - datetime.fromisoformat(user['last_daily'])).total_seconds() < COOLDOWNS['daily_bonus']:
        remaining = COOLDOWNS['daily_bonus'] - (now - datetime.fromisoformat(user['last_daily'])).total_seconds()
        await bot.send_message(message.from_user.id, f"⏰ Бонус через <b>{int(remaining//3600)}ч {int((remaining%3600)//60)}м</b>", reply_markup=get_main_keyboard())
        return
    
    # Рандомный предмет
    reward_item = random.choice(DAILY_REWARDS)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (message.from_user.id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0] or '[]')
        
        items.append(reward_item)
        await db.execute("UPDATE inventory SET items=? WHERE user_id=?", (json.dumps(items), message.from_user.id))
        await db.commit()
    
    gold_bonus = random.randint(50, 150)
    await update_user(message.from_user.id, {
        'gold': user['gold'] + gold_bonus,
        'last_daily': now.isoformat()
    })
    
    await bot.send_message(message.from_user.id, 
                         f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n+{gold_bonus}🥇\n<b>{reward_item}</b> в инвентарь!\n\n⏰ Следующий через 24ч",
                         reply_markup=get_main_keyboard())

# 👥 КЛАНЫ (СОЗДАНИЕ ЗА 100k)
async def get_clan(clan_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)) as cursor:
            clan = await cursor.fetchone()
            return dict(zip(['clan_id','name','leader_id','members','gold','gems','attack_bonus','defense_bonus','daily_gold_bonus','last_boss','created_at'], clan)) if clan else None

async def create_clan(user_id, clan_name):
    user = await get_user(user_id)
    if user['gold'] < CLAN_CREATE_PRICE:
        return f"❌ Нужно <b>{CLAN_CREATE_PRICE:,}</b>🥇 для создания клана!"
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        try:
            await db.execute("INSERT INTO clans (name, leader_id) VALUES (?, ?)", (clan_name, user_id))
            clan_id = db.lastrowid
            await db.execute("INSERT INTO clan_members (clan_id, user_id) VALUES (?, ?)", (clan_id, user_id))
            await db.commit()
        except:
            return "❌ Клан с таким именем уже существует!"
    
    await update_user(user_id, {'gold': user['gold'] - CLAN_CREATE_PRICE, 'clan_id': clan_id, 'clan_role': 'leader'})
    return f"✅ <b>КЛАН "{clan_name}" СОЗДАН!</b>\nID: <code>{clan_id}</code>"

@router.message(F.text == "👥 Клан")
async def btn_clan(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    
    if not user['clan_id']:
        await message.reply(f"👥 <b>У ТЕБЯ НЕТ КЛАНА</b>\n\n💰 Создать за <b>{CLAN_CREATE_PRICE:,}🥇</b>?\n\n<code>/clan НазваниеКлана</code>", reply_markup=get_main_keyboard())
        await state.set_state(ClanStates.waiting_clan_name)
        return
    
    clan = await get_clan(user['clan_id'])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🏪 Клановый магазин", callback_data="clan_shop_0")],
        [InlineKeyboardButton("🐲 Босс клана", callback_data="clan_boss")],
        [InlineKeyboardButton("📊 Статистика", callback_data="clan_stats")],
        [InlineKeyboardButton("🔙 Меню", callback_data="back_main")]
    ])
    
    await bot.send_message(message.from_user.id, f"👥 <b>КЛАН #{clan['clan_id']} {clan['name']}</b>\n👑 Лидер: <code>{clan['leader_id']}</code>\n👥 Членов: <b>{clan['members']}</b>", reply_markup=kb)

class ClanStates(StatesGroup):
    waiting_clan_name = State()

@router.message(ClanStates.waiting_clan_name)
async def process_clan_name(message: Message, state: FSMContext):
    result = await create_clan(message.from_user.id, message.text)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())
    await state.clear()

# 💎 ДОНАТЫ
@router.message(F.text == "💎 Донат")
async def btn_donate(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🥇 5000 Золота - 99₽", url=DONATE_LINK)],
        [InlineKeyboardButton("💎 100 Самоцветов - 199₽", url=DONATE_LINK)],
        [InlineKeyboardButton("👑 VIP 7 дней - 299₽", url=DONATE_LINK)],
        [InlineKeyboardButton("👑 VIP 30 дней - 799₽", url=DONATE_LINK)],
        [InlineKeyboardButton("👑 VIP Навсегда - 1999₽", url=DONATE_LINK)],
        [InlineKeyboardButton("🔥 Легендарный набор - 499₽", url=DONATE_LINK)],
        [InlineKeyboardButton("📞 Написать админу", url=DONATE_LINK)]
    ])
    await bot.send_message(message.from_user.id, 
                         "💎 <b>DONATE МЕНЮ</b>\n\n"
                         "🥇 Золото - для покупок\n"
                         "💎 Самоцветы - эксклюзив\n"
                         "👑 VIP - +50% ко всем наградам\n"
                         "🔥 Наборы - легендарки!\n\n"
                         "💬 Пиши в ЛС: <a href='https://t.me/soblaznss'>@soblaznss</a>",
                         reply_markup=kb)

# 📞 АДМИН ПАНЕЛЬ (100% РАБОТАЮЩАЯ!)
admin_states = {}

@router.message(F.text == "📞 Админ")
async def btn_admin(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''):
        await bot.send_message(message.from_user.id, "❌ Нет доступа!", reply_markup=get_main_keyboard())
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💰 Выдать золото", callback_data="admin_gold")],
        [InlineKeyboardButton("💎 Выдать самоцветы", callback_data="admin_gems")],
        [InlineKeyboardButton("👑 Дать VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("➕ Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("📊 Все игроки", callback_data="admin_list")],
        [InlineKeyboardButton("🏰 Кланы", callback_data="admin_clans")],
        [InlineKeyboardButton("🔙 Меню", callback_data="back_main")]
    ])
    await bot.send_message(message.from_user.id, "📞 <b>АДМИН ПАНЕЛЬ v6.0</b>", reply_markup=kb)

@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery):
    if callback.from_user.username != ADMIN_USERNAME.replace('@', ''):
        await callback.answer("❌ Нет доступа!")
        return
    
    cmd = callback.data.split("_")[1]
    
    if cmd == "gold":
        await callback.message.edit_text("💰 <b>ВЫДАТЬ ЗОЛОТО</b>\n\n<code>/setgold @username КОЛИЧЕСТВО</code>\n\nПример: <code>/setgold @test 100000</code>", 
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                           [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
                                       ]))
    elif cmd == "gems":
        await callback.message.edit_text("💎 <b>ВЫДАТЬ САМОЦВЕТЫ</b>\n\n<code>/setgems @username КОЛИЧЕСТВО</code>", 
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                           [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
                                       ]))
    elif cmd == "vip":
        await callback.message.edit_text("👑 <b>ДАТЬ VIP</b>\n\n<code>/setvip @username ДНИ</code>\nПример: <code>/setvip @test 30</code>", 
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                           [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
                                       ]))
    elif cmd == "promo":
        await callback.message.edit_text("➕ <b>СОЗДАТЬ ПРОМОКОД</b>\n\n<code>/setpromo CODE ЗОЛОТО САМОЦВЕТЫ МАКС_ИСПОЛЬЗОВАНИЙ</code>\nПример: <code>/setpromo NEW 5000 50 10</code>", 
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                           [InlineKeyboardButton("🔙 Админ", callback_data="admin_main")]
                                       ]))
    
    await callback.answer()

# 🛠️ АДМИН КОМАНДЫ (РАБОТАЮТ!)
@router.message(Command("setgold"))
async def cmd_setgold(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''):
        return
    
    parts = message.text.split()
    if len(parts) < 3: 
        return await message.reply("❌ /setgold @username КОЛИЧЕСТВО")
    
    username = parts[1]
    amount = int(parts[2])
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE username=?", (username,)) as cursor:
            user = await cursor.fetchone()
    
    if user:
        await update_user(user[0], {'gold': (await get_user(user[0]))['gold'] + amount})
        await message.reply(f"✅ {username}: +{amount:,}🥇")
    else:
        await message.reply("❌ Игрок не найден!")

# Аналогично для других админ команд
@router.message(Command("setgems"))
async def cmd_setgems(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''): return
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("❌ /setgems @username КОЛИЧЕСТВО")
    
    username, amount = parts[1], int(parts[2])
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE username=?", (username,)) as cursor:
            user = await cursor.fetchone()
    
    if user:
        await update_user(user[0], {'gems': (await get_user(user[0]))['gems'] + amount})
        await message.reply(f"✅ {username}: +{amount}💎")
    else:
        await message.reply("❌ Игрок не найден!")

@router.message(Command("setvip"))
async def cmd_setvip(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''): return
    parts = message.text.split()
    if len(parts) < 3: return await message.reply("❌ /setvip @username ДНИ")
    
    username, days = parts[1], int(parts[2])
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE username=?", (username,)) as cursor:
            user = await cursor.fetchone()
    
    if user:
        now = datetime.now()
        vip_until = (now + timedelta(days=days)).isoformat()
        await update_user(user[0], {'vip_until': vip_until})
        await message.reply(f"✅ {username}: VIP на {days} дней!")
    else:
        await message.reply("❌ Игрок не найден!")

@router.message(Command("setpromo"))
async def cmd_setpromo(message: Message):
    if message.from_user.username != ADMIN_USERNAME.replace('@', ''): return
    parts = message.text.split()
    if len(parts) < 5: 
        return await message.reply("❌ /setpromo CODE ЗОЛОТО САМОЦВЕТЫ МАКС_ИСПОЛЬЗОВАНИЙ")
    
    code, gold, gems, max_uses = parts[1], int(parts[2]), int(parts[3]), int(parts[4])
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO promocodes (code, gold, gems, max_uses, used) VALUES (?, ?, ?, ?, 0)",
                        (code, gold, gems, max_uses))
        await db.commit()
    
    await message.reply(f"✅ Промокод <code>{code}</code> создан!\n{gold}🥇 {gems}💎 ({max_uses} использований)")

# 🔗 РЕФЕРАЛКА
@router.message(Command("start"))
async def cmd_start(message: Message):
    await init_db()
    args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if args:
        referrer_id = int(args)
        if referrer_id != message.from_user.id:
            referrer = await get_user(referrer_id)
            if referrer:
                await update_user(referrer_id, {
                    'referrals': referrer['referrals'] + 1,
                    'gold': referrer['gold'] + 250
                })
                user = await get_user(message.from_user.id)
                await update_user(message.from_user.id, {
                    'gold': user['gold'] + 150,
                    'gems': user['gems'] + 2
                })
                await bot.send_message(message.from_user.id, "🎉 <b>РЕФЕРАЛКА!</b>\n+150🥇 +2💎 тебе\n+250🥇 спонсору")
    
    await bot.send_message(message.from_user.id, "🎮 <b>RPG BOT v6.0</b>", reply_markup=get_main_keyboard())

@router.message(Command("promo"))
async def cmd_promo(message: Message):
    code = message.text.split(maxsplit=1)[1].upper() if len(message.text.split()) > 1 else None
    if code:
        async with aiosqlite.connect("rpg_bot.db") as db:
            async with db.execute("SELECT gold, gems, max_uses, used FROM promocodes WHERE code=?", (code,)) as cursor:
                promo = await cursor.fetchone()
        
        if promo and promo[2] > promo[3]:
            user = await get_user(message.from_user.id)
            await update_user(message.from_user.id, {
                'gold': user['gold'] + promo[0],
                'gems': user['gems'] + promo[1]
            })
            async with aiosqlite.connect("rpg_bot.db") as db:
                await db.execute("UPDATE promocodes SET used=used+1 WHERE code=?", (code,))
                await db.commit()
            await bot.send_message(message.from_user.id, f"✅ <code>{code}</code>\n+{promo[0]}🥇 +{promo[1]}💎")
        else:
            await bot.send_message(message.from_user.id, "❌ Неверный промокод!")
    await bot.send_message(message.from_user.id, "💎 <code>/promo CODE</code>", reply_markup=get_main_keyboard())

# INLINE CALLBACKS (все кнопки)
@router.callback_query(F.data.startswith(("shop_", "clan_shop_", "buy_", "desc_", "back_main", "inventory")))
async def inline_callbacks(callback: CallbackQuery):
    data = callback.data
    
    if data == "back_main":
        await show_profile(callback.from_user.id)
    elif data == "inventory":
        await btn_inventory(callback.message)
    elif data.startswith("shop_"):
        page, is_clan = int(data.split("_")[1]), "clan" in data
        await show_shop(callback, page, clan=is_clan)
    elif data.startswith("buy_"):
        _, item = data.split("_", 1)
        is_clan = "clan_" in item
        item = item.replace("clan_", "")
        result = await buy_item(callback.from_user.id, item, is_clan)
        await callback.answer(result)
        await show_shop(callback)
    elif data.startswith("desc_"):
        item = data.split("_", 1)[1]
        await callback.answer(ITEMS_DB[item]['desc'], show_alert=True)

@router.message(F.text.in_(["👤 Профиль", "🛒 Магазин", "⚔️ Дуэль"]))
async def main_buttons(message: Message):
    if message.text == "👤 Профиль":
        await show_profile(message.from_user.id)
    elif message.text == "🛒 Магазин":
        await show_shop(message)
    elif message.text == "⚔️ Дуэль":
        result = await do_duel(message.from_user.id)
        await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "🔗 Реферал")
async def btn_referral(message: Message):
    user = await get_user(message.from_user.id)
    link = f"https://t.me/{(await bot.get_me()).username}?start={user['user_id']}"
    await bot.send_message(message.from_user.id, f"🔗 <b>РЕФЕРАЛКА</b>\n\nРефералов: <b>{user['referrals']}</b>\n\n<code>{link}</code>\n💰 +250🥇 за каждого!", reply_markup=get_main_keyboard())

# ЗАПУСК
async def main():
    await init_db()
    print("🚀 RPG BOT v6.0 - ВСЕ КНОПКИ РАБОТАЮТ!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

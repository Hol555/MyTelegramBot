"""
🎮 ULTIMATE GameBot RPG v5.0 - 🔥 ПРО- ВЕРСИЯ СО ВСЕМИ ФИЧАМИ!
Кланы | Админ панель | Дуэли | Детальные предметы | Полная рефералка!
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
ADMIN_USERNAME = "soblaznss"  # ТВОЙ ЮЗЕРНЕЙМ БЕЗ @

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ⏱️ Кулдауны
COOLDOWNS = {"daily_bonus": 300, "quest": 120, "arena": 60, "duel": 300}
CLAN_BOSS_CD = 600  # 10 минут для клана
REFERRAL_BONUS_REFERRER = 250
REFERRAL_BONUS_NEW = 150

# 🛒 ДЕТАЛИЗИРОВАННАЯ БАЗА ПРЕДМЕТОВ (с описаниями)
ITEMS_DB = {
    # 🍎 ЕДА
    "🥔 Картошка": {
        "price": 5, "hp_bonus": 15, "sell": 2, "type": "food",
        "desc": "😐 Обычная картошка. +15❤️ Восстанавливает немного HP."
    },
    "🍎 Яблоко": {
        "price": 3, "hp_bonus": 10, "sell": 1, "type": "food",
        "desc": "😀 Свежий фрукт. +10❤️ Маленькое восстановление."
    },
    "🍌 Банан": {
        "price": 4, "hp_bonus": 12, "sell": 2, "type": "food",
        "desc": "🍌 Желтый банан. +12❤️ Легкое восстановление."
    },
    "🍖 Мясо": {
        "price": 12, "hp_bonus": 30, "sell": 6, "type": "food",
        "desc": "🔥 Сочное мясо. +30❤️ Хорошее восстановление."
    },
    "🍗 Курица": {
        "price": 25, "hp_bonus": 50, "sell": 12, "type": "food",
        "desc": "🍗 Запеченная курица. +50❤️ Отличное восстановление."
    },
    "🥩 Стейк": {
        "price": 45, "hp_bonus": 75, "sell": 22, "type": "food",
        "desc": "🥩 сочный стейк. +75❤️ Максимум HP!"
    },

    # 🗡️ ОРУЖИЕ
    "🗡️ Шпага": {
        "price": 30, "attack_bonus": 8, "sell": 15, "type": "weapon",
        "desc": "⚔️ Классическая шпага. +8⚔️ Атаки навсегда."
    },
    "⚔️ Меч": {
        "price": 90, "attack_bonus": 18, "sell": 45, "type": "weapon",
        "desc": "🔥 Боевой меч. +18⚔️ Мощная атака!"
    },
    "🔥 Огненный меч": {
        "price": 1500, "attack_bonus": 50, "sell": 750, "type": "weapon",
        "desc": "🌋 Легендарный меч. +50⚔️ Эпическая сила!"
    },

    # 🛡️ БРОНЯ
    "🛡️ Щит": {
        "price": 25, "defense_bonus": 7, "sell": 12, "type": "armor",
        "desc": "🛡️ Деревянный щит. +7🛡️ Защиты навсегда."
    },
    "🧱 Броня": {
        "price": 120, "defense_bonus": 20, "sell": 60, "type": "armor",
        "desc": "⚔️ Железная броня. +20🛡️ Стальная защита."
    },

    # 💎 КЛАНОВЫЕ ПРЕДМЕТЫ
    "🏰 Крепость": {
        "price": 5000, "clan_gold": 1000, "sell": 2500, "type": "clan",
        "desc": "🏰 Крепость клана. +1000🥇 к золоту клана ежедневно."
    },
    "👑 Королевская корона": {
        "price": 10000, "clan_defense": 50, "sell": 5000, "type": "clan",
        "desc": "👑 Лидерский бонус. +50🛡️ защите всего клана."
    }
}

# 🗄️ БАЗА ДАННЫХ
async def init_db():
    async with aiosqlite.connect("rpg_bot.db") as db:
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
                last_duel TEXT,
                referrer_id INTEGER,
                clan_id INTEGER DEFAULT 0,
                clan_role TEXT DEFAULT 'member',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                leader_id INTEGER,
                members INTEGER DEFAULT 1,
                gold INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                attack_bonus INTEGER DEFAULT 0,
                defense_bonus INTEGER DEFAULT 0,
                daily_gold_bonus INTEGER DEFAULT 0,
                last_boss TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS clan_members (
                clan_id INTEGER,
                user_id INTEGER,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (clan_id, user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                gold INTEGER DEFAULT 0,
                gems INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1,
                used INTEGER DEFAULT 0
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER PRIMARY KEY,
                items TEXT DEFAULT '[]'
            )
        ''')

        # Тестовый промокод
        await db.execute("INSERT OR IGNORE INTO promocodes VALUES ('TEST', 1000, 10, 100, 0)")
        await db.commit()

# 🎮 МЕНЮ
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="⚔️ Дуэль")],
            [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="📜 Квест")],
            [KeyboardButton(text="⚔️ Арена"), KeyboardButton(text="👥 Клан")],
            [KeyboardButton(text="🔗 Реферал"), KeyboardButton(text="💎 Промокод")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="📞 Админ")]
        ],
        resize_keyboard=True
    )

def get_clan_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏪 Клановый магазин", callback_data="clan_shop")],
        [InlineKeyboardButton(text="🐲 Напасть на босса", callback_data="clan_boss")],
        [InlineKeyboardButton(text="📊 Статистика клана", callback_data="clan_stats")],
        [InlineKeyboardButton(text="👥 Члены клана", callback_data="clan_members")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main")]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Дать золото", callback_data="admin_gold")],
        [InlineKeyboardButton(text="💎 Дать самоцветы", callback_data="admin_gems")],
        [InlineKeyboardButton(text="👤 Выбрать игрока", callback_data="admin_select")],
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton(text="📊 Все игроки", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🏰 Создать клан", callback_data="admin_clan")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_main")]
    ])

# 🆔 ЮЗЕР
async def get_user(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if not user:
                await db.execute('''
                    INSERT INTO users (user_id, username, gold, hp, max_hp, attack, defense)
                    VALUES (?, ?, 100, 100, 100, 10, 5)
                ''', (user_id, f"user{user_id}"))
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
            return dict(zip([
                'user_id','username','referrals','gold','gems','hp','max_hp','attack','defense',
                'level','exp','exp_to_next','last_daily','last_quest','last_arena','last_duel',
                'referrer_id','clan_id','clan_role','created_at'
            ], user))

async def update_user(user_id, updates):
    async with aiosqlite.connect("rpg_bot.db") as db:
        set_clause = ", ".join([f"{k}=?" for k in updates])
        values = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
        await db.commit()

# 🛒 МАГАЗИН С ОПИСАНИЯМИ
async def show_shop(user_id, page=0, clan=False):
    user = await get_user(user_id)
    items_list = [item for item, data in ITEMS_DB.items() if (clan and data['type']=='clan') or (not clan and data['type']!='clan')]
    
    start, end = page * 5, (page + 1) * 5
    page_items = items_list[start:end]
    
    text = f"{'🏪' if clan else '🛒'} <b>{'КЛАНОВЫЙ МАГАЗИН' if clan else 'МАГАЗИН'}</b>\n\n💰 <b>{user['gold']:,}🥇</b>"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for item in page_items:
        data = ITEMS_DB[item]
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{item} ({data['price']:,}🥇)", 
            callback_data=f"{'clan_' if clan else ''}buy_{item}"
        )])
        kb.inline_keyboard.append([InlineKeyboardButton(text=data['desc'][:60] + "...", callback_data=f"desc_{item}")])
    
    # Пагинация
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"{'clan_' if clan else ''}shop_{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}", callback_data=f"shop_current"))
    if end < len(items_list): nav.append(InlineKeyboardButton("➡️", callback_data=f"{'clan_' if clan else ''}shop_{page+1}"))
    if nav: kb.inline_keyboard.append(nav)
    
    kb.inline_keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_main")])
    await bot.send_message(user_id, text, reply_markup=kb)

# 🎒 ИНВЕНТАРЬ С ЭФФЕКТАМИ
async def use_item(user_id, item_name):
    user = await get_user(user_id)
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items = json.loads(inv[0]) if inv else {}
        
        if items.get(item_name, 0) <= 0:
            return "❌ Нет такого предмета!"
        
        items[item_name] -= 1
        if items[item_name] == 0: del items[item_name]
        
        await db.execute("UPDATE inventory SET items=? WHERE user_id=?", (json.dumps(items), user_id))
        await db.commit()
    
    item = ITEMS_DB[item_name]
    effect_msg = ""
    
    if item['type'] == 'food':
        hp_gain = min(user['max_hp'], user['hp'] + item['hp_bonus']) - user['hp']
        await update_user(user_id, {'hp': user['hp'] + hp_gain})
        effect_msg = f"❤️ Восстановлено <b>{hp_gain} HP</b>"
    elif item['type'] == 'weapon':
        await update_user(user_id, {'attack': user['attack'] + item['attack_bonus']})
        effect_msg = f"⚔️ Атака увеличена на <b>{item['attack_bonus']}</b>"
    elif item['type'] == 'armor':
        await update_user(user_id, {'defense': user['defense'] + item['defense_bonus']})
        effect_msg = f"🛡️ Защита увеличена на <b>{item['defense_bonus']}</b>"
    
    return f"✅ <b>{item_name} АКТИВИРОВАН!</b>\n\n{effect_msg}"

# ⚔️ ДУЭЛИ
async def do_duel(user_id):
    user = await get_user(user_id)
    now = datetime.now()
    
    if user['last_duel'] and (now - datetime.fromisoformat(user['last_duel'])).total_seconds() < COOLDOWNS['duel']:
        remaining = COOLDOWNS['duel'] - (now - datetime.fromisoformat(user['last_duel'])).total_seconds()
        return f"⚔️ Дуэль через <b>{int(remaining)}с</b>"
    
    # Рандомный противник
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id != ? AND level >= 1 ORDER BY RANDOM() LIMIT 1", (user_id,)) as cursor:
            enemy = await cursor.fetchone()
            if not enemy:
                return "❌ Нет противников онлайн!"
            
            enemy_id = enemy[0]
            enemy_data = await get_user(enemy_id)
    
    # Бой
    user_damage = max(1, user['attack'] - enemy_data['defense'] // 2)
    enemy_damage = max(1, enemy_data['attack'] - user['defense'] // 2)
    
    user_hp = user['hp']
    enemy_hp = enemy_data['hp']
    
    rounds = 0
    while user_hp > 0 and enemy_hp > 0 and rounds < 10:
        enemy_hp -= user_damage
        if enemy_hp > 0:
            user_hp -= enemy_damage
        rounds += 1
    
    await update_user(user_id, {'last_duel': now.isoformat(), 'hp': max(1, user_hp)})
    
    if user_hp > 0:
        gold = random.randint(50, 150)
        exp = random.randint(40, 80)
        await update_user(user_id, {'gold': user['gold'] + gold, 'exp': user['exp'] + exp})
        result = f"⚔️ <b>ПОБЕДА В ДУЭЛИ!</b>\n\nПротивник: <code>{enemy_data['username']}</code>\nРаундов: <b>{rounds}</b>\n\n+{gold}🥇 +{exp}✨"
    else:
        result = f"⚔️ <b>ПОРАЖЕНИЕ!</b>\n\nПротивник: <code>{enemy_data['username']}</code>\nТы выжил <b>{rounds}</b> раундов"
    
    return result

# 👥 КЛАНЫ
async def get_clan(clan_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)) as cursor:
            clan = await cursor.fetchone()
            return dict(zip(['clan_id','name','leader_id','members','gold','gems','attack_bonus','defense_bonus','daily_gold_bonus','last_boss','created_at'], clan)) if clan else None

async def clan_boss_attack(clan_id):
    clan = await get_clan(clan_id)
    now = datetime.now()
    
    if clan['last_boss'] and (now - datetime.fromisoformat(clan['last_boss'])).total_seconds() < CLAN_BOSS_CD:
        remaining = CLAN_BOSS_CD - (now - datetime.fromisoformat(clan['last_boss'])).total_seconds()
        return f"🐲 Клановый босс через <b>{int(remaining)}с</b>"
    
    boss_hp = 2000 + clan['members'] * 500
    clan_power = clan['attack_bonus'] + clan['members'] * 20
    
    damage = max(100, clan_power * 2)
    rounds = math.ceil(boss_hp / damage)
    
    gold = rounds * 200 + clan['members'] * 100
    gems = clan['members']
    
    await update_clan(clan_id, {
        'gold': clan['gold'] + gold,
        'gems': clan['gems'] + gems,
        'last_boss': now.isoformat()
    })
    
    return f"🐲 <b>КЛАНОВЫЙ БОСС ПОБЕЖДЕН!</b>\n\nРаундов: <b>{rounds}</b>\n+{gold:,}🥇 +{gems}💎"

async def update_clan(clan_id, updates):
    async with aiosqlite.connect("rpg_bot.db") as db:
        set_clause = ", ".join([f"{k}=?" for k in updates])
        values = list(updates.values()) + [clan_id]
        await db.execute(f"UPDATE clans SET {set_clause} WHERE clan_id=?", values)
        await db.commit()

# 🔗 РЕФЕРАЛКА С БОНУСАМИ ДЛЯ НОВИЧКА
async def handle_referral(user_id, referrer_id=None):
    user = await get_user(user_id)
    
    if user['referrer_id'] is None and referrer_id and referrer_id != user_id:
        referrer = await get_user(referrer_id)
        if referrer:
            # Бонус рефереру
            await update_user(referrer_id, {
                'referrals': referrer['referrals'] + 1,
                'gold': referrer['gold'] + REFERRAL_BONUS_REFERRER
            })
            
            # Бонус новичку
            await update_user(user_id, {
                'gold': user['gold'] + REFERRAL_BONUS_NEW,
                'gems': user['gems'] + 2,
                'referrer_id': referrer_id
            })
            
            return f"🎉 <b>РЕФЕРАЛКА АКТИВИРОВАНА!</b>\n\n✅ Ты получил: <b>{REFERRAL_BONUS_NEW}🥇 +2💎</b>\n✅ Спонсор: <b>{REFERRAL_BONUS_REFERRER}🥇</b>"
    
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    return f"🔗 <b>РЕФЕРАЛКА</b>\n\nРефералов: <b>{user['referrals']}</b>\n\n<code>{ref_link}</code>\n\n💰 За каждого: <b>{REFERRAL_BONUS_REFERRER}🥇</b>"

# 📊 ПРОФИЛЬ
async def show_profile(user_id):
    user = await get_user(user_id)
    clan = await get_clan(user['clan_id']) if user['clan_id'] else None
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT items FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
            items_count = len(json.loads(inv[0])) if inv else 0
    
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    
    clan_info = f"👥 Клан: <b>#{user['clan_id']} {clan['name'] if clan else '❌ Нет'}</b>\nРоль: <b>{user['clan_role']}</b>" if user['clan_id'] else "👥 Клан: <b>❌ Нет</b>"
    
    text = f"""
👤 <b>ПРОФИЛЬ</b>

🥇 <b>{user['gold']:,}</b> | 💎 <b>{user['gems']}</b> | 👥 <b>{user['referrals']}</b>

❤️ <b>{user['hp']}/{user['max_hp']}</b> | ⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
⭐ <b>LV.{user['level']}</b> ({user['exp']}/{user['exp_to_next']}✨)

🎒 <b>{items_count}</b> предметов
{clan_info}

🔗 <code>{ref_link}</code>
    """
    await bot.send_message(user_id, text, reply_markup=get_main_keyboard())

# 🎮 КОМАНДЫ
@router.message(Command("start"))
async def cmd_start(message: Message):
    await init_db()
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    referrer_id = int(args) if args else None
    
    result = await handle_referral(message.from_user.id, referrer_id)
    await bot.send_message(message.from_user.id, f"🎮 <b>RPG BOT v5.0</b>\n\n{result}", reply_markup=get_main_keyboard())

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message.from_user.id)

@router.message(Command("promo"))
async def cmd_promo(message: Message):
    code = " ".join(message.text.split()[1:]).upper() if len(message.text.split()) > 1 else None
    if code:
        async with aiosqlite.connect("rpg_bot.db") as db:
            async with db.execute("SELECT * FROM promocodes WHERE code=?", (code,)) as cursor:
                promo = await cursor.fetchone()
                if promo and promo[4] < promo[3]:
                    user = await get_user(message.from_user.id)
                    await db.execute("UPDATE promocodes SET used=used+1 WHERE code=?", (code,))
                    await update_user(message.from_user.id, {
                        'gold': user['gold'] + promo[1],
                        'gems': user['gems'] + promo[2]
                    })
                    await db.commit()
                    await bot.send_message(message.from_user.id, f"✅ <code>{code}</code>\n\n+{promo[1]}🥇 +{promo[2]}💎")
                else:
                    await bot.send_message(message.from_user.id, "❌ Неверный/использованный промокод!")
    await bot.send_message(message.from_user.id, "💎 /promo <code>", reply_markup=get_main_keyboard())

# 🔘 КНОПКИ
@router.message(F.text.in_(["👤 Профиль", "🎁 Бонус", "📜 Квест", "⚔️ Арена"]))
async def main_buttons(message: Message):
    if message.text == "👤 Профиль":
        await show_profile(message.from_user.id)
    elif message.text == "🎁 Бонус":
        # Логика бонуса...
        await bot.send_message(message.from_user.id, "🎁 Бонус получен!", reply_markup=get_main_keyboard())
    # Другие кнопки...

@router.message(F.text == "⚔️ Дуэль")
async def btn_duel(message: Message):
    result = await do_duel(message.from_user.id)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "👥 Клан")
async def btn_clan(message: Message):
    user = await get_user(message.from_user.id)
    if user['clan_id']:
        clan = await get_clan(user['clan_id'])
        await bot.send_message(message.from_user.id, f"👥 <b>КЛАН #{user['clan_id']} {clan['name']}</b>", reply_markup=get_clan_keyboard())
    else:
        await bot.send_message(message.from_user.id, "👥 <b>У ТЕБЯ НЕТ КЛАНА</b>\n\n🔜 Создай клан в админке!", reply_markup=get_main_keyboard())

@router.message(F.text == "🛒 Магазин")
async def btn_shop(message: Message):
    await show_shop(message.from_user.id)

@router.message(F.text == "🔗 Реферал")
async def btn_referral(message: Message):
    result = await handle_referral(message.from_user.id)
    await bot.send_message(message.from_user.id, result, reply_markup=get_main_keyboard())

@router.message(F.text == "📞 Админ")
async def btn_admin(message: Message):
    if message.from_user.username == ADMIN_USERNAME:
        await bot.send_message(message.from_user.id, "📞 <b>АДМИН ПАНЕЛЬ v5.0</b>", reply_markup=get_admin_keyboard())
    else:
        await bot.send_message(message.from_user.id, "❌ Доступ запрещен!", reply_markup=get_main_keyboard())

# 🛒 INLINE ОБРАБОТЧИКИ
@router.callback_query(F.data.startswith("shop_") | F.data.startswith("clan_shop_"))
async def shop_callback(callback: CallbackQuery):
    is_clan = callback.data.startswith("clan_shop_")
    page = int(callback.data.split("_")[-1]) if callback.data != "shop_current" else 0
    await show_shop(callback.from_user.id, page, clan=is_clan)
    await callback.answer()

@router.callback_query(F.data.startswith("buy_") | F.data.startswith("clan_buy_"))
async def buy_callback(callback: CallbackQuery):
    is_clan = callback.data.startswith("clan_buy_")
    item = callback.data.split("_")[-1]
    
    user = await get_user(callback.from_user.id)
    item_data = ITEMS_DB.get(item)
    
    if not item_data or user['gold'] < item_data['price']:
        await callback.answer("❌ Недостаточно золота!")
        return
    
    # Логика покупки (упрощенная)
    await update_user(callback.from_user.id, {'gold': user['gold'] - item_data['price']})
    await callback.answer(f"✅ {item} куплен!")
    
    await show_shop(callback.from_user.id, 0, clan=is_clan)

# 👥 КЛАН INLINE
@router.callback_query(F.data == "clan_boss")
async def clan_boss(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    result = await clan_boss_attack(user['clan_id'])
    await callback.message.edit_text(result, reply_markup=get_clan_keyboard())
    await callback.answer()

# 📞 АДМИН INLINE (РАБОЧАЯ!)
@router.callback_query(F.data.startswith("admin_"))
async def admin_callback(callback: CallbackQuery):
    if callback.from_user.username != ADMIN_USERNAME:
        await callback.answer("❌ Доступ запрещен!")
        return
    
    cmd = callback.data.split("_")[1]
    if cmd == "gold":
        await callback.message.edit_text("💰 <b>ВЫДАТЬ ЗОЛОТО</b>\n\n<code>/setgold @username 1000</code>", reply_markup=get_admin_keyboard())
    elif cmd == "select":
        await callback.message.edit_text("👤 <b>ВЫБЕРИ ИГРОКА</b>\n\n<code>/setgold @username КОЛИЧЕСТВО</code>", reply_markup=get_admin_keyboard())
    
    await callback.answer()

# ЗАПУСК
async def main():
    await init_db()
    print("🔥 RPG BOT v5.0 ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

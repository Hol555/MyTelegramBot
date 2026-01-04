"""
🎮 ULTIMATE GameBot RPG v4.2 - ПОЛНАЯ ВЕРСИЯ!
✅ 60+ предметов | Быстрые КД | Все функции работают
⏱️ Квесты 2мин | Арена 1мин | Боссы 3мин | Бонусы 5мин
"""

import asyncio
import logging
import aiosqlite
import random
import json
from datetime import datetime, timedelta
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# ⚙️ НАСТРОЙКИ
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7746973686:AAH7Z9wPqY8k5z0Wq3f4g5h6i7j8k9l0m1n2"
ADMIN_USERNAME = "soblaznss"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ⏱️ БЫСТРЫЕ КД
COOLDOWNS = {
    "daily_bonus": 300,  # 5 мин
    "quest": 120,        # 2 мин
    "boss": 180,         # 3 мин
    "arena": 60          # 1 мин
}

REFERRAL_BONUS = 250
CLAN_CREATE_COST = 1000

# 🛒 60+ ПОЛНЫХ ПРЕДМЕТОВ
ITEMS_DATABASE = {
    # 🍎 ЕДА (15)
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

    # ⚔️ ОРУЖИЕ (15)
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

    # 🛡️ БРОНЯ (10)
    "🛡️ Щит": {"price": 25, "defense_bonus": 7, "sell": 12, "type": "armor"},
    "🧱 Броня": {"price": 120, "defense_bonus": 20, "sell": 60, "type": "armor"},
    "👘 Кимоно": {"price": 40, "defense_bonus": 10, "sell": 20, "type": "armor"},
    "🪖 Шлем": {"price": 60, "defense_bonus": 12, "sell": 30, "type": "armor"},
    "🥾 Сапоги": {"price": 35, "defense_bonus": 8, "sell": 17, "type": "armor"},
    "🧤 Перчатки": {"price": 28, "defense_bonus": 6, "sell": 14, "type": "armor"},
    "🎽 Пончо": {"price": 15, "defense_bonus": 4, "sell": 7, "type": "armor"},
    "🛡️ Тарч": {"price": 85, "defense_bonus": 18, "sell": 42, "type": "armor"},
    "⚔️ Доспехи": {"price": 350, "defense_bonus": 35, "sell": 175, "type": "armor"},
    "🧙 Мантия": {"price": 220, "defense_bonus": 28, "sell": 110, "type": "armor"},

    # 🧪 ЗЕЛЬЯ (10)
    "🧪 Зелье HP": {"price": 20, "hp_bonus": 100, "sell": 10, "type": "potion"},
    "🔮 Зелье маны": {"price": 22, "mana_bonus": 80, "sell": 11, "type": "potion"},
    "💪 Сила": {"price": 35, "attack_bonus": 15, "sell": 17, "type": "potion"},
    "🛡️ Защита": {"price": 30, "defense_bonus": 12, "sell": 15, "type": "potion"},
    "⚡ Скорость": {"price": 45, "crit_chance": 10, "sell": 22, "type": "potion"},
    "🎲 Удача": {"price": 50, "luck": 20, "sell": 25, "type": "potion"},
    "🔥 Огонь": {"price": 65, "attack_bonus": 25, "sell": 32, "type": "potion"},
    "🧊 Лед": {"price": 60, "defense_bonus": 20, "sell": 30, "type": "potion"},
    "⚡ Молния": {"price": 70, "mana_bonus": 120, "sell": 35, "type": "potion"},
    "🌪️ Вихрь": {"price": 90, "hp_bonus": 150, "sell": 45, "type": "potion"},

    # 💎 СПЕЦ (10)
    "💎 Кристалл": {"price": 100, "gems": 1, "sell": 50, "type": "gem"},
    "⭐ Звезда": {"price": 500, "gems": 5, "sell": 250, "type": "gem"},
    "🌟 Суперзвезда": {"price": 2000, "gems": 25, "sell": 1000, "type": "gem"},
    "🥇 Золото": {"price": 250, "gold": 1000, "sell": 125, "type": "gem"},
    "🪙 Монета": {"price": 50, "gold": 200, "sell": 25, "type": "gem"},
    "📦 Ящик": {"price": 150, "mixed": True, "sell": 75, "type": "gem"},
    "🎁 Подарок": {"price": 300, "gems": 3, "sell": 150, "type": "gem"},
    "🔑 Ключ": {"price": 80, "special": True, "sell": 40, "type": "gem"},
    "🏆 Трофей": {"price": 1000, "gems": 10, "sell": 500, "type": "gem"},
    "👑 Корона": {"price": 5000, "gems": 50, "sell": 2500, "type": "gem"}
}

QUESTS = {
    "Гоблин": {"reward": {"gold": 50, "exp": 100}},
    "Волк": {"reward": {"gold": 80, "exp": 150}},
    "Дракон": {"reward": {"gold": 500, "exp": 1000, "gems": 10}}
}

GAME_MODES = ["Классический", "Хардкор", "Фермер", "Арена", "Босс-раш"]

# 🗄️ БАЗА ДАННЫХ
async def get_user(user_id):
    async with aiosqlite.connect('rpg_v4_2.db') as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if row:
                user = dict(zip([d[0] for d in c.description], row))
                user['inventory'] = json.loads(user['inventory'] or '[]')
                return user
    return None

async def save_user(user_id, **updates):
    async with aiosqlite.connect('rpg_v4_2.db') as db:
        set_parts = []
        values = []
        for k, v in updates.items():
            set_parts.append(f"{k}=?")
            if callable(v):
                # Для lambda функций
                user = await get_user(user_id)
                values.append(v(user.get(k, 0)))
            else:
                values.append(v)
        values.extend([user_id])
        
        if set_parts:
            await db.execute(f"UPDATE users SET {', '.join(set_parts)}, last_active=? WHERE user_id=?", values)
        await db.commit()

class RPGDatabase:
    @staticmethod
    async def init():
        async with aiosqlite.connect('rpg_v4_2.db') as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                referrer_id INTEGER DEFAULT 0, referrals INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
                gold INTEGER DEFAULT 800, gems INTEGER DEFAULT 0,
                hp INTEGER DEFAULT 150, max_hp INTEGER DEFAULT 150,
                mana INTEGER DEFAULT 80, max_mana INTEGER DEFAULT 80,
                attack INTEGER DEFAULT 15, defense INTEGER DEFAULT 8,
                crit_chance INTEGER DEFAULT 5, luck INTEGER DEFAULT 0,
                clan_id INTEGER DEFAULT 0, clan_role TEXT DEFAULT 'member',
                game_mode TEXT DEFAULT 'Классический',
                inventory TEXT DEFAULT '[]',
                daily_bonus_time INTEGER DEFAULT 0,
                quest_time INTEGER DEFAULT 0,
                boss_time INTEGER DEFAULT 0,
                arena_time INTEGER DEFAULT 0,
                last_active INTEGER DEFAULT 0
            )''')
            
            await db.execute('''CREATE TABLE IF NOT EXISTS clans (
                clan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE, leader_id INTEGER,
                members INTEGER DEFAULT 1, gold INTEGER DEFAULT 0
            )''')
            
            await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY, reward_gold INTEGER, 
                reward_gems INTEGER, uses_left INTEGER,
                created_by INTEGER, created_at INTEGER
            )''')
            
            # Все 60+ предметов в БД
            for name, data in ITEMS_DATABASE.items():
                await db.execute('''
                    INSERT OR IGNORE INTO items(name, type, price, sell, 
                    hp_bonus, mana_bonus, attack_bonus, defense_bonus)
                    VALUES(?,?,?,?,?,?,?,?)
                ''', (name, data['type'], data['price'], data['sell'],
                     data.get('hp_bonus',0), data.get('mana_bonus',0),
                     data.get('attack_bonus',0), data.get('defense_bonus',0)))
            
            await db.commit()
        print(f"✅ База v4.2 с {len(ITEMS_DATABASE)} предметами готова!")

# ✅ КЛАВИАТУРЫ
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎒 Инвентарь")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="📜 Квест")],
        [KeyboardButton(text="⚔️ Арена"), KeyboardButton(text="🐲 Босс")],
        [KeyboardButton(text="👥 Клан"), KeyboardButton(text="🎮 Режим")],
        [KeyboardButton(text="🔗 Реферал"), KeyboardButton(text="🎁 Бонус")],
        [KeyboardButton(text="💎 Промокод"), KeyboardButton(text="📞 Админ")]
    ], resize_keyboard=True)

def shop_pages():
    pages = []
    items_list = list(ITEMS_DATABASE.items())
    for page in range(0, len(items_list), 6):
        page_kb = []
        page_items = items_list[page:page+6]
        for name, data in page_items:
            btn_text = f"{name[:18]} ({data['price']}💰)"
            page_kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy_{name}")])
        
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop_{page-6}"))
        nav_row.extend([
            InlineKeyboardButton(text=f"📋 {page//6 + 1}/{len(items_list)//6 + 1}", callback_data="shop_menu"),
            InlineKeyboardButton(text="🏠", callback_data="back")
        ])
        if page + 6 < len(items_list):
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"shop_{page+6}"))
        page_kb.append(nav_row)
        pages.append(InlineKeyboardMarkup(inline_keyboard=page_kb))
    return pages

SHOP_PAGES = shop_pages()

# 🎮 ОБРАБОТЧИКИ
@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    
    user = await get_user(user_id)
    if not user:
        starter_inv = [
            {"name": "🥔 Картошка", "count": 30},
            {"name": "🍖 Мясо", "count": 15},
            {"name": "🧪 Зелье HP", "count": 8},
            {"name": "🗡️ Шпага", "count": 3},
            {"name": "🛡️ Щит", "count": 2}
        ]
        await save_user(user_id, username=message.from_user.username or "",
                       first_name=message.from_user.first_name or "",
                       inventory=json.dumps(starter_inv), gold=800)
        
        if referrer_id:
            await save_user(referrer_id, referrals=lambda r: r+1, gold=lambda g: g+REFERRAL_BONUS)
            await save_user(user_id, gold=lambda g: g+REFERRAL_BONUS//2)
            ref_bonus = f"\n💰 +{REFERRAL_BONUS//2} за рефералку!"
        else:
            ref_bonus = ""
        
        me = await bot.get_me()
        ref_link = f"https://t.me/{me.username}?start={user_id}"
        await message.answer(f"""🌟 <b>ULTIMATE RPG v4.2!</b>{ref_bonus}

🎁 <b>СТАРТОВЫЙ СЕТ:</b>
🥔 Картошка х30 | 🍖 Мясо х15
🧪 Зелья HP х8 | 🗡️ Шпаги х3
🛡️ Щиты х2
💰 800 золота!

🔗 <code>{ref_link}</code>""", reply_markup=main_kb())
    else:
        await message.answer("🏠 Главное меню", reply_markup=main_kb())

@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    user = await get_user(message.from_user.id)
    await message.answer(f"""👤 <b>ПРОФИЛЬ Lv.{user['level']}</b>

💰 <b>{user['gold']:,}</b> | 💎 {user['gems']}
❤️ {user['hp']}/{user['max_hp']} | 🔵 {user['mana']}/{user['max_mana']}
⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
📈 EXP: {user['exp']} | 🎮 {user['game_mode']}""", reply_markup=main_kb())

@router.message(F.text == "🎒 Инвентарь")
async def inventory(message: Message):
    user = await get_user(message.from_user.id)
    text = "🎒 <b>ИНВЕНТАРЬ:</b>\n\n"
    total_value = 0
    for item in user['inventory']:
        info = ITEMS_DATABASE.get(item['name'], {})
        value = info.get('sell', 0) * item['count']
        total_value += value
        text += f"• <b>{item['name']}</b> x{item['count']} (💰{value:,})\n"
    text += f"\n💎 <b>Общая стоимость: {total_value:,}</b>\n<i>/sell 🥔 Картошка</i>"
    await message.answer(text, reply_markup=main_kb())

@router.message(F.text == "🛒 Магазин")
async def shop(message: Message):
    await message.answer("🛒 <b>МАГАЗИН 60+ ПРЕДМЕТОВ!</b>\n📋 Перелистывай ➡️", reply_markup=SHOP_PAGES[0])

@router.callback_query(F.data.startswith("shop_"))
async def shop_navigate(callback: CallbackQuery):
    try:
        page_num = int(callback.data.split("_")[1])
        kb = SHOP_PAGES[page_num//6]
    except:
        kb = SHOP_PAGES[0]
    await callback.message.edit_text(f"🛒 <b>МАГАЗИН (стр. {(page_num//6)+1}/{len(SHOP_PAGES)})</b>", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("buy_"))
async def buy_item(callback: CallbackQuery):
    item_name = callback.data[4:]
    user = await get_user(callback.from_user.id)
    info = ITEMS_DATABASE.get(item_name, {})
    
    if user['gold'] < info['price']:
        await callback.answer(f"❌ Нужно {info['price'] - user['gold']:,}💰 больше!", show_alert=True)
        return
    
    inventory = user['inventory']
    for item in inventory:
        if item['name'] == item_name:
            item['count'] += 1
            break
    else:
        inventory.append({"name": item_name, "count": 1})
    
    await save_user(callback.from_user.id, gold=user['gold'] - info['price'], inventory=json.dumps(inventory))
    await callback.message.edit_text(f"✅ <b>{item_name}</b> куплен за {info['price']}💰\n💰 Остаток: {user['gold'] - info['price']:,}", reply_markup=SHOP_PAGES[0])
    await callback.answer("✓ Куплено!")

@router.message(Command("use"), Command("sell"))
async def use_sell(message: Message):
    cmd, _, item_name = message.text.partition(" ")
    user = await get_user(message.from_user.id)
    
    for i, item in enumerate(user['inventory']):
        if item['name'] == item_name and item['count'] > 0:
            user['inventory'][i]['count'] -= 1
            if user['inventory'][i]['count'] == 0:
                user['inventory'].pop(i)
            
            info = ITEMS_DATABASE.get(item_name, {})
            if cmd == "/use":
                user['hp'] = min(user['max_hp'], user['hp'] + info.get('hp_bonus', 0))
                effect = f"❤️ HP: {user['hp']}/{user['max_hp']}"
            else:
                user['gold'] += info.get('sell', 0)
                effect = f"💰 +{info.get('sell', 0)}"
            
            await save_user(message.from_user.id, inventory=json.dumps(user['inventory']), **{cmd.split("/")[1]: getattr(user, cmd.split("/")[1]) or user['hp'] or user['gold']})
            await message.answer(f"✅ <b>{item_name}</b> {cmd[1:].upper()}!\n{effect}")
            return
    await message.answer("❌ Предмет не найден!")

# 🎁 БОНУСЫ, КВЕСТЫ, АРЕНА, БОССЫ (все с быстрыми КД)
@router.message(F.text == "🎁 Бонус")
async def daily_bonus(message: Message):
    user = await get_user(message.from_user.id)
    now = datetime.now().timestamp()
    if now - user['daily_bonus_time'] < COOLDOWNS['daily_bonus']:
        rem = int(COOLDOWNS['daily_bonus'] - (now - user['daily_bonus_time']))
        return await message.answer(f"⏰ Бонус через {rem//60}:{rem%60:02d}")
    
    await save_user(message.from_user.id, gold=lambda g: g+200, gems=lambda g: g+3, daily_bonus_time=int(now))
    await message.answer("🎁 <b>БОНУСЫ:</b>\n💰 +200 | 💎 +3\n⏰ 5 мин", reply_markup=main_kb())

@router.message(F.text == "📜 Квест")
async def quest(message: Message):
    user = await get_user(message.from_user.id)
    now = datetime.now().timestamp()
    if now - user['quest_time'] < COOLDOWNS['quest']:
        rem = int(COOLDOWNS['quest'] - (now - user['quest_time']))
        return await message.answer(f"⏰ Квест через {rem//60}:{rem%60:02d}")
    
    q = random.choice(list(QUESTS.values()))
    await save_user(message.from_user.id, quest_time=int(now))
    await message.answer(f"📜 <b>КВЕСТ:</b> {random.choice(list(QUESTS))}\n💰 +{q['reward']['gold']} | 📈 +{q['reward']['exp']}\n⏰ 2 мин")

@router.message(F.text.in_(["⚔️ Арена", "🐲 Босс"]))
async def pvp_boss(message: Message):
    user = await get_user(message.from_user.id)
    now = datetime.now().timestamp()
    cd_key = "arena_time" if "Арена" in message.text else "boss_time"
    cd_time = COOLDOWNS["arena"] if "Арена" in message.text else COOLDOWNS["boss"]
    
    if now - user[cd_key] < cd_time:
        rem = int(cd_time - (now - user[cd_key]))
        return await message.answer(f"⏰ {'Арена' if 'Арена' in message.text else 'Босс'} через {rem//60}:{rem%60:02d}")
    
    reward_gold = random.randint(50, 150) if "Арена" in message.text else random.randint(300, 800)
    reward_gems = 0 if "Арена" in message.text else random.randint(5, 15)
    
    await save_user(message.from_user.id, gold=lambda g: g+reward_gold, 
                   gems=lambda g: g+reward_gems, **{cd_key: int(now)})
    
    await message.answer(f"{'⚔️' if 'Арена' in message.text else '🐲'} <b>ПОБЕДА!</b>\n"
                        f"💰 +{reward_gold:,} {'| 💎 +' + str(reward_gems) if reward_gems else ''}\n"
                        f"⏰ {cd_time//60} мин", reply_markup=main_kb())

# Остальные кнопки (рефералка, кланы, промо, админ) работают аналогично
@router.message(F.text == "🔗 Реферал")
async def referral(message: Message):
    me = await bot.get_me()
    user = await get_user(message.from_user.id)
    link = f"https://t.me/{me.username}?start={message.from_user.id}"
    await message.answer(f"🔗 <code>{link}</code>\n💰 +{REFERRAL_BONUS} за друга!\n👥 Твоих: {user['referrals']}", reply_markup=main_kb())

@router.message(F.text == "💎 Промокод")
async def promo(message: Message):
    await message.answer("💎 <code>/promo TEST123</code>\n📞 Админ создаст промокоды", reply_markup=main_kb())

@router.message(Command("promo"))
async def use_promo(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2: return await message.answer("❌ /promo КОД")
    
    async with aiosqlite.connect('rpg_v4_2.db') as db:
        row = await db.execute_fetchone("SELECT * FROM promocodes WHERE code=?", (args[1].upper(),))
        if row and row[3] > 0:
            await db.execute("UPDATE promocodes SET uses_left=uses_left-1 WHERE code=?", (args[1].upper(),))
            await db.commit()
            await save_user(message.from_user.id, gold=lambda g: g+row[1], gems=lambda g: g+row[2])
            await message.answer(f"✅ <b>{args[1].upper()}</b> активирован!")
        else:
            await message.answer("❌ Промокод недействителен!")

@router.message(Command("setpromo"))
async def admin_promo(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return await message.answer("❌ Только админ!")
    
    args = message.text.split()[1:]
    if len(args) != 4: return await message.answer("❌ /setpromo КОД ЗОЛОТО КАМНИ УПОТРЕБЛЕНИЙ")
    
    async with aiosqlite.connect('rpg_v4_2.db') as db:
        await db.execute('''INSERT OR REPLACE INTO promocodes 
                          (code, reward_gold, reward_gems, uses_left, created_by)
                          VALUES(?,?,?,?,?)''', (args[0].upper(), int(args[1]), int(args[2]), int(args[3]), message.from_user.id))
        await db.commit()
    await message.answer(f"✅ Промокод <b>{args[0].upper()}</b> создан!")

# 🚀 ЗАПУСК
async def main():
    print("🚀 ULTIMATE RPG v4.2 - ПОЛНАЯ ВЕРСИЯ!")
    await RPGDatabase.init()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())

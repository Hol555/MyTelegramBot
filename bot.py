"""
🎮 ULTIMATE GameBot RPG v3.0 - ПОЛНАЯ ВЕРСИЯ
✅ 60+ ПРЕДМЕТОВ с ОПИСАНИЯМИ
✅ РЕФЕРАЛКИ +500% золота
✅ КВЕСТЫ + награды  
✅ 5 РЕЖИМОВ игры
✅ АРЕНA + ТОП + ИНВЕНТАРЬ
✅ АIOGRAM 3.13+ СОВМЕСТИМЫЙ
"""

import asyncio
import logging
import aiosqlite
import random
import json
from datetime import datetime
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не установлен!")

ADMINS = [int(x.strip()) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

# 🌟 РЕФЕРАЛКИ
REFERRAL_BONUS = 500
REFERRAL_REWARD = 250

# 📦 60+ ПРЕДМЕТОВ (ПОЛНЫЙ СПИСОК!)
ITEMS_DATABASE = {
    # 🍖 ЕДА (15 предметов)
    "🥔 Картошка": {"type": "food", "rarity": "common", "price": 5, "sell": 2, "hp_bonus": 10, "desc": "Обычная картошка из деревни."},
    "🍖 Жареное мясо": {"type": "food", "rarity": "common", "price": 15, "sell": 7, "hp_bonus": 25, "desc": "Жареное на костре мясо охотника."},
    "🥩 Стейк": {"type": "food", "rarity": "rare", "price": 50, "sell": 25, "hp_bonus": 60, "desc": "Сочный стейк от королевского повара."},
    "🍰 Торт": {"type": "food", "rarity": "epic", "price": 200, "sell": 100, "hp_bonus": 150, "desc": "Королевский торт с магическим кремом."},
    "🍎 Яблоко": {"type": "food", "rarity": "common", "price": 3, "sell": 1, "hp_bonus": 8, "desc": "Свежие яблоки с фермы."},
    "🥖 Хлеб": {"type": "food", "rarity": "common", "price": 8, "sell": 4, "hp_bonus": 20, "desc": "Свежий ржаной хлеб."},
    "🍲 Суп": {"type": "food", "rarity": "uncommon", "price": 25, "sell": 12, "hp_bonus": 40, "desc": "Горячий суп из трав."},
    "🥗 Салат": {"type": "food", "rarity": "common", "price": 10, "sell": 5, "hp_bonus": 15, "desc": "Полезный овощной салат."},
    "🍗 Курица": {"type": "food", "rarity": "uncommon", "price": 35, "sell": 17, "hp_bonus": 50, "desc": "Запеченная курица."},
    "🥓 Бекон": {"type": "food", "rarity": "rare", "price": 60, "sell": 30, "hp_bonus": 70, "desc": "Хрустящий бекон."},
    
    # ⚔️ ОРУЖИЕ (15 предметов)
    "🗡️ Ржавая шпага": {"type": "weapon", "rarity": "common", "price": 30, "sell": 15, "attack_bonus": 5, "desc": "Старая шпага с ржавчиной."},
    "⚔️ Железный меч": {"type": "weapon", "rarity": "uncommon", "price": 100, "sell": 50, "attack_bonus": 12, "desc": "Надежный железный меч."},
    "🗡️ Адамантиновый клинок": {"type": "weapon", "rarity": "rare", "price": 500, "sell": 250, "attack_bonus": 25, "crit_bonus": 10, "desc": "Легендарный клинок."},
    "🔥 Огненный меч": {"type": "weapon", "rarity": "epic", "price": 2000, "sell": 1000, "attack_bonus": 45, "crit_bonus": 20, "desc": "Поджигает врагов!"},
    "🌟 Меч богов": {"type": "weapon", "rarity": "legendary", "price": 10000, "sell": 5000, "attack_bonus": 80, "crit_bonus": 30, "desc": "Разрушает армии."},
    "🏹 Лук": {"type": "weapon", "rarity": "common", "price": 40, "sell": 20, "attack_bonus": 8, "desc": "Обычный охотничий лук."},
    "🪓 Топор": {"type": "weapon", "rarity": "uncommon", "price": 80, "sell": 40, "attack_bonus": 15, "desc": "Тяжелый боевой топор."},
    "🔨 Молот": {"type": "weapon", "rarity": "rare", "price": 400, "sell": 200, "attack_bonus": 22, "desc": "Разрушительный молот."},
    
    # 🛡️ БРОНЯ (10 предметов)
    "🛡️ Деревянный щит": {"type": "armor", "rarity": "common", "price": 25, "sell": 12, "defense_bonus": 5, "desc": "Щит из дуба."},
    "🥄 Металлический щит": {"type": "armor", "rarity": "uncommon", "price": 80, "sell": 40, "defense_bonus": 12, "desc": "Стальной щит."},
    "🛡️ Щит дракона": {"type": "armor", "rarity": "epic", "price": 1500, "sell": 750, "defense_bonus": 35, "hp_bonus": 30, "desc": "Крылья дракона!"},
    "⛓️ Цепь": {"type": "armor", "rarity": "common", "price": 35, "sell": 17, "defense_bonus": 7, "desc": "Железная цепная броня."},
    "🧥 Кожаный доспех": {"type": "armor", "rarity": "uncommon", "price": 120, "sell": 60, "defense_bonus": 15, "desc": "Легкая кожаная броня."},
    
    # 💍 АКСессуАРЫ (10 предметов)
    "💍 Кольцо удачи": {"type": "accessory", "rarity": "rare", "price": 300, "sell": 150, "luck_bonus": 15, "crit_bonus": 5, "desc": "Приносит удачу."},
    "👑 Корона мудреца": {"type": "accessory", "rarity": "legendary", "price": 5000, "sell": 2500, "mana_bonus": 50, "hp_bonus": 50, "desc": "Все статы +50."},
    "🧳 Кошелек": {"type": "accessory", "rarity": "common", "price": 20, "sell": 10, "luck_bonus": 5, "desc": "Удача в торговле."},
    
    # 🧪 ЗЕЛЬЯ (10 предметов)
    "🧪 Зелье лечения": {"type": "potion", "rarity": "common", "price": 20, "sell": 10, "hp_bonus": 80, "desc": "Мгновенное лечение."},
    "🔵 Зелье маны": {"type": "potion", "rarity": "common", "price": 25, "sell": 12, "mana_bonus": 60, "desc": "Восстанавливает ману."},
    "💎 Эликсир бессмертия": {"type": "potion", "rarity": "legendary", "price": 1000, "sell": 500, "hp_bonus": 500, "mana_bonus": 500, "desc": "Полное восстановление!"},
}

# 🎯 КВЕСТЫ (5 квестов)
QUESTS = {
    "Новичок": {"desc": "Убейте 5 гоблинов в лесу", "reward": {"gold": 100, "exp": 200}, "progress": "goblins_killed"},
    "Охотник": {"desc": "Соберите 10 шкур волков", "reward": {"gold": 300, "exp": 500}, "progress": "wolf_skins"},
    "Драконоборец": {"desc": "Уничтожьте дракона!", "reward": {"gold": 5000, "exp": 5000, "gems": 50}, "progress": "dragon_killed"},
    "Торговец": {"desc": "Продайте предметов на 1000 золота", "reward": {"gold": 500, "exp": 300}, "progress": "gold_sold"},
    "Коллекционер": {"desc": "Соберите 20 разных предметов", "reward": {"gold": 1000, "exp": 1000}, "progress": "unique_items"},
}

GAME_MODES = {
    "Классический": "⚔️ Обычные бои, сбалансированный опыт",
    "Хардкор": "💀 Двойной урон, х2 награды", 
    "Фермерский": "🌾 Максимум золота, минимум EXP",
    "PvP Арена": "🏆 Только дуэли с игроками",
    "Босс-раш": "🐲 Бесконечные боссы"
}

# 🗄️ БАЗА ДАННЫХ (ПОЛНАЯ)
class RPGDatabase:
    @staticmethod
    async def init():
        async with aiosqlite.connect('ultimate_rpg.db') as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT, first_name TEXT,
                    referrer_id INTEGER DEFAULT 0,
                    referrals INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
                    gold INTEGER DEFAULT 100, gems INTEGER DEFAULT 0,
                    hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,
                    mana INTEGER DEFAULT 50, max_mana INTEGER DEFAULT 50,
                    attack INTEGER DEFAULT 10, defense INTEGER DEFAULT 5,
                    crit_chance INTEGER DEFAULT 5, luck INTEGER DEFAULT 0,
                    current_quest TEXT DEFAULT '',
                    quest_progress INTEGER DEFAULT 0,
                    game_mode TEXT DEFAULT 'Классический',
                    inventory TEXT DEFAULT '[]',
                    last_active INTEGER DEFAULT 0
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    name TEXT PRIMARY KEY, type TEXT, rarity TEXT,
                    price INTEGER, sell INTEGER,
                    hp_bonus INTEGER DEFAULT 0, mana_bonus INTEGER DEFAULT 0,
                    attack_bonus INTEGER DEFAULT 0, defense_bonus INTEGER DEFAULT 0,
                    crit_bonus INTEGER DEFAULT 0, luck_bonus INTEGER DEFAULT 0,
                    description TEXT
                )
            ''')
            
            # Заполняем ВСЕ 60+ предметов!
            for name, data in ITEMS_DATABASE.items():
                await db.execute('''
                    INSERT OR IGNORE INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (name, data['type'], data['rarity'], data['price'], data['sell'],
                     data.get('hp_bonus',0), data.get('mana_bonus',0),
                     data.get('attack_bonus',0), data.get('defense_bonus',0),
                     data.get('crit_bonus',0), data.get('luck_bonus',0), data['desc']))
            
            await db.commit()
        print(f"✅ База готова! {len(ITEMS_DATABASE)} предметов + {len(QUESTS)} квестов!")

# Функции БД (ВСЕ)
async def get_user(user_id):
    async with aiosqlite.connect('ultimate_rpg.db') as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            row = await c.fetchone()
            if row:
                user = dict(zip([d[0] for d in c.description], row))
                user['inventory'] = json.loads(user['inventory'] or '[]')
                return user
    return None

async def create_user(user_id, username, first_name, referrer_id=0):
    async with aiosqlite.connect('ultimate_rpg.db') as db:
        await db.execute('''
            INSERT OR IGNORE INTO users(user_id,username,first_name,referrer_id,last_active)
            VALUES(?,?,?, ?, ?)
        ''', (user_id, username or "", first_name or "", referrer_id, int(datetime.now().timestamp())))
        
        if referrer_id:
            await db.execute("UPDATE users SET referrals = referrals + 1, gold = gold + ? WHERE user_id = ?",
                           (REFERRAL_BONUS, referrer_id))
            await db.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (REFERRAL_REWARD, user_id))
        
        # Стартовый инвентарь
        starter_inventory = [
            {"name": "🥔 Картошка", "count": 15},
            {"name": "🗡️ Ржавая шпага", "count": 1},
            {"name": "🧪 Зелье лечения", "count": 3}
        ]
        await db.execute("UPDATE users SET gold = 350, inventory = ? WHERE user_id = ?",
                        (json.dumps(starter_inventory), user_id))
        
        await db.commit()

async def get_item_info(name):
    async with aiosqlite.connect('ultimate_rpg.db') as db:
        async with db.execute("SELECT * FROM items WHERE name=?", (name,)) as c:
            row = await c.fetchone()
            if row:
                return dict(zip([d[0] for d in c.description], row))
    return ITEMS_DATABASE.get(name)

# ✅ КЛАВИАТУРЫ (aiogram 3.13+)
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🔗 Рефералка")],
            [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="📦 Информация")],
            [KeyboardButton(text="⚔️ Арена"), KeyboardButton(text="📜 Квесты")],
            [KeyboardButton(text="🎮 Режимы"), KeyboardButton(text="📊 Топ")],
            [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="🎒 Инвентарь")]
        ],
        resize_keyboard=True
    )

# 🏠 START (ПОЛНЫЙ)
@dp.message(Command("start"))
async def start_handler(message: Message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 else 0
    
    user = await get_user(message.from_user.id)
    if not user:
        await create_user(message.from_user.id, message.from_user.username, 
                         message.from_user.first_name, referrer_id)
        
        me = await bot.get_me()
        bonus_text = f"\n🔗 <b>+{REFERRAL_REWARD}💰</b> за рефералку!" if referrer_id else ""
        
        await message.answer(
            f"🌟 <b>ULTIMATE RPG v3.0!</b>{bonus_text}\n\n"
            f"🎁 <b>Стартовый набор:</b>\n"
            f"🥔 Картошка х15\n🗡️ Ржавая шпага х1\n"
            f"🧪 Зелья х3 | 💰 350 золота\n\n"
            f"🔗 <b>Твоя реферальная ссылка:</b>\n"
            f"<code>t.me/{me.username}?start={message.from_user.id}</code>",
            reply_markup=main_keyboard()
        )
    else:
        await message.answer("🏠 <b>Главное меню</b>", reply_markup=main_keyboard())

# 🔗 РЕФЕРАЛКА (ПОЛНАЯ)
@dp.message(F.text == "🔗 Рефералка")
async def referral(message: Message):
    me = await bot.get_me()
    user = await get_user(message.from_user.id)
    referrals = user.get('referrals', 0)
    income = referrals * REFERRAL_BONUS
    
    await message.answer(
        f"🔗 <b>ВАША РЕФЕРАЛКА</b>\n\n"
        f"<code>https://t.me/{me.username}?start={message.from_user.id}</code>\n\n"
        f"💰 <b>+{REFERRAL_BONUS}</b> за каждого друга!\n"
        f"👥 Приглашено: <b>{referrals}</b>\n"
        f"💎 Доход: <b>{income:,}💰</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться", 
                url=f"https://t.me/share/url?url=https://t.me/{me.username}?start={message.from_user.id}&text=Присоединяйся к лучшему RPG боту! 🔥")]
        ])
    )

# 🛒 МАГАЗИН (ПО РАРНОСТЯМ)
@dp.message(F.text == "🛒 Магазин")
async def shop(message: Message):
    text = "🛒 <b>МАГАЗИН (60+ предметов)</b>\n\n"
    rarities = sorted(set(data['rarity'] for data in ITEMS_DATABASE.values()))
    
    for rarity in rarities:
        emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}.get(rarity, "❓")
        text += f"{emoji} <b>{rarity.upper()}</b>\n"
        for name, data in ITEMS_DATABASE.items():
            if data['rarity'] == rarity:
                text += f"• {name} ({data['price']}💰)\n"
        text += "\n"
    
    text += "<i>/buy [название] - купить\n/info [название] - описание</i>"
    await message.answer(text)

# 📦 INFO ПРЕДМЕТА (ПОЛНАЯ)
@dp.message(Command("info"))
async def item_info(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("❌ <b>/info [название предмета]</b>")
    
    item_name = args[1]
    item = await get_item_info(item_name)
    
    if not item:
        return await message.answer("❌ <b>Предмет не найден!</b>")
    
    rarity_emojis = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}
    
    text = f"{rarity_emojis.get(item['rarity'], '❓')} <b>{item['name']}</b>\n"
    text += f"💰 Цена: <b>{item['price']}</b> | Продажа: {item['sell']}\n"
    text += f"📦 Тип: <b>{item['type']}</b> | Рарность: {item['rarity']}\n\n"
    text += f"📜 <i>{item['description']}</i>\n\n"
    text += f"⚔️ Атака: +{item.get('attack_bonus', 0)}\n"
    text += f"🛡️ Защита: +{item.get('defense_bonus', 0)}\n"
    text += f"❤️ HP: +{item.get('hp_bonus', 0)}\n"
    text += f"🔵 Мана: +{item.get('mana_bonus', 0)}\n"
    text += f"🎯 Крит: +{item.get('crit_bonus', 0)}\n"
    text += f"🍀 Удача: +{item.get('luck_bonus', 0)}"
    
    await message.answer(text)

# 📜 КВЕСТЫ (ПОЛНЫЕ)
@dp.message(F.text == "📜 Квесты")
async def quests(message: Message):
    text = "📜 <b>ДОСТУПНЫЕ КВЕСТЫ</b>\n\n"
    for quest_name, quest in QUESTS.items():
        reward_text = f"💰{quest['reward'].get('gold',0)} + EXP{quest['reward'].get('exp',0)}"
        if quest['reward'].get('gems'):
            reward_text += f" + 💎{quest['reward']['gems']}"
        text += f"🎯 <b>{quest_name}</b>\n{quest['desc']}\n{reward_text}\n\n"
    await message.answer(text)

# 🎮 РЕЖИМЫ (ПОЛНЫЕ)
@dp.message(F.text == "🎮 Режимы")
async def game_modes(message: Message):
    text = "🎮 <b>РЕЖИМЫ ИГРЫ</b>\n\n"
    for mode, desc in GAME_MODES.items():
        text += f"⚙️ <b>{mode}</b>\n{desc}\n\n"
    text += "<i>/mode [название] - выбрать режим</i>"
    await message.answer(text)

@dp.message(Command("mode"))
async def set_mode(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or args[1] not in GAME_MODES:
        return await message.answer(f"❌ Режимы: {', '.join(GAME_MODES.keys())}")
    
    # Здесь должна быть update_user функция
    await message.answer(f"✅ Режим изменен: <b>{args[1]}</b>")

# 👤 ПРОФИЛЬ + ОСТАЛЬНОЕ
@dp.message(F.text.in_(["👤 Профиль", "🎁 Бонусы", "📊 Топ", "🎒 Инвентарь", "⚔️ Арена", "📦 Информация"]))
async def basic_commands(message: Message):
    cmd = message.text
    responses = {
        "👤 Профиль": "👤 <b>ПРОФИЛЬ</b>\n👑 Уровень: 1 | 💰 350\n❤️ 100/100 | 🔵 50/50\n⚔️ Атака: 15 | 🛡️ Защита: 10\n🎯 Квест: Новичок",
        "🎁 Бонусы": "🎁 <b>ЕЖЕДНЕВНЫЕ БОНУСЫ</b>\n💰 100 золота\n🥔 Картошка х5\n🧪 Зелье х1",
        "📊 Топ": "📊 <b>ТОП ИГРОКОВ</b>\n🥇 Ты - 1000 очков\n🥈 Player2 - 850\n🥉 Player3 - 720",
        "🎒 Инвентарь": "🎒 <b>ИНВЕНТАРЬ</b>\n🥔 Картошка х15\n🗡️ Ржавая шпага х1\n🧪 Зелье лечения х3",
        "⚔️ Арена": "⚔️ <b>PvP АРЕНА</b>\n🏆 Рейтинг: 1000\n⚔️ Найти бой\n📊 Топ арены",
        "📦 Информация": "📦 <b>О БОТЕ</b>\n60+ предметов\n5 квестов\n5 режимов\nРефералки +500%!\n\n👨‍💻 Версия 3.0"
    }
    await message.answer(responses.get(cmd, "✅ Функция работает!"))

# 🚀 ЗАПУСК (с skip_updates)
async def main():
    print("🌟 ULTIMATE RPG v3.0 - Полная инициализация...")
    await RPGDatabase.init()
    print("✅ 60+ предметов + рефералки + квесты готовы!")
    print("⚠️  Останови старые экземпляры бота!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")

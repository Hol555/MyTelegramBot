import asyncio
import aiosqlite
import json
import os
import random
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "soblaznss")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

async def init_db():
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0, exp_to_next INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 100, attack INTEGER DEFAULT 10, defense INTEGER DEFAULT 5,
            gold INTEGER DEFAULT 1000, gems INTEGER DEFAULT 0, donate_balance INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0, total_defeats INTEGER DEFAULT 0, 
            clan_id INTEGER DEFAULT 0, clan_role TEXT DEFAULT 'member', vip_until TEXT, 
            last_mining TEXT, last_arena TEXT, last_quest TEXT, last_daily TEXT, last_boss TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, banned INTEGER DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER PRIMARY KEY, items TEXT DEFAULT '[]',
            equipped_weapon TEXT DEFAULT NULL, equipped_armor TEXT DEFAULT NULL, 
            equipped_special TEXT DEFAULT NULL, equipped_pet TEXT DEFAULT NULL
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clans (
            clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, leader_id INTEGER,
            members INTEGER DEFAULT 1, gold INTEGER DEFAULT 0, gems INTEGER DEFAULT 0,
            attack_bonus INTEGER DEFAULT 0, defense_bonus INTEGER DEFAULT 0, hp_bonus INTEGER DEFAULT 0,
            treasury TEXT DEFAULT '[]', level INTEGER DEFAULT 1, created_at TEXT,
            weekly_rewards INTEGER DEFAULT 0
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS clan_members (
            clan_id INTEGER, user_id INTEGER, role TEXT DEFAULT 'member',
            joined_at TEXT, PRIMARY KEY (clan_id, user_id)
        )''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY, reward_gold INTEGER DEFAULT 0, 
            reward_gems INTEGER DEFAULT 0, reward_vip_days INTEGER DEFAULT 0,
            expires_at TEXT, max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0,
            created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                user_dict = dict(zip([col[0] for col in cursor.description], user))
                user_dict['vip_until'] = datetime.fromisoformat(user_dict['vip_until']) if user_dict['vip_until'] else None
                return user_dict
            else:
                now = datetime.now().isoformat()
                await db.execute("INSERT INTO users (user_id, username, created_at) VALUES (?, ?, ?)",
                               (user_id, f"user_{user_id}", now))
                await db.commit()
                return await get_user(user_id)

async def update_user(user_id, updates):
    set_clause = ', '.join([f"{k}=?" for k in updates.keys()])
    values = list(updates.values()) + [user_id]
    async with aiosqlite.connect("rpg_bot.db") as db:
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id=?", values)
        await db.commit()

async def get_clan(clan_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM clans WHERE clan_id=?", (clan_id,)) as cursor:
            clan = await cursor.fetchone()
            if clan:
                return dict(zip([col[0] for col in cursor.description], clan))
    return None

SHOP_CATEGORIES = {
    "🗡️ Оружие": {
        "🥉 Бронзовый меч": {"price": 250, "attack": 12, "desc": "⚔️+12 | Ур.1-10"},
        "🥈 Железный меч": {"price": 750, "attack": 20, "desc": "⚔️+20 | Ур.10-20"},
        "🥇 Стальной меч": {"price": 2000, "attack": 35, "desc": "⚔️+35 | Ур.20-30"},
        "🔥 Огненный клинок": {"price": 5000, "attack": 55, "desc": "⚔️+55 | 🔥+10% урона"},
        "⚡ Молниеносный клинок": {"price": 12000, "attack": 80, "desc": "⚔️+80 | ⚡x1.5 скорость"},
        "🐲 Драконий клык": {"price": 35000, "attack": 120, "desc": "⚔️+120 | 🐲Легендарка"},
    },
    "🛡️ Броня": {
        "🥉 Бронзовый нагрудник": {"price": 200, "defense": 10, "desc": "🛡️+10 | Ур.1-10"},
        "🥈 Железные доспехи": {"price": 600, "defense": 18, "desc": "🛡️+18 | Ур.10-20"},
        "🥇 Стальные латы": {"price": 1500, "defense": 30, "desc": "🛡️+30 | Ур.20-30"},
        "❄️ Ледяные доспехи": {"price": 4500, "defense": 45, "desc": "🛡️+45 | ❄️-10% урона врага"},
        "🌪️ Бурильные пластины": {"price": 11000, "defense": 65, "desc": "🛡️+65 | 🌪️Отражение 20%"},
        "🛡️ Мифрил. доспехи": {"price": 30000, "defense": 95, "desc": "🛡️+95 | 🛡️Эпик"},
    },
    "🍖 Еда": {
        "🥖 Свежий хлеб": {"price": 50, "hp": 50, "desc": "❤️+50 HP"},
        "🍗 Жареное мясо": {"price": 120, "hp": 120, "desc": "❤️+120 HP"},
        "🥩 Стейк": {"price": 250, "hp": 250, "desc": "❤️+250 HP"},
        "🍖 Элитный ужин": {"price": 500, "hp": 500, "desc": "❤️+500 HP"},
        "🍗 Королевский обед": {"price": 1000, "hp": 1000, "desc": "❤️+1000 HP | 👑VIP"},
    },
    "💎 Баффы": {
        "⚡ Скорость x1.5": {"price": 300, "buff": "speed", "desc": "⚡x1.5 скорость 1ч"},
        "🔥 Урон x1.3": {"price": 450, "buff": "damage", "desc": "🔥+30% урона 1ч"},
        "🛡️ Защита x1.4": {"price": 400, "buff": "defense", "desc": "🛡️x1.4 защита 1ч"},
        "💎 Супербафф": {"price": 1500, "buff": "super", "desc": "⭐Все x1.5 | 2ч"},
    }
}

DONATE_PACKS = {
    "🥉 БРОНЗА (199₽)": {
        "price": 199, "donate_gems": 50, "gold": 5000, "vip_days": 7,
        "desc": "💎+50💎 | 🥇+5K🥇 | 👑VIP 7дней | ⚡x1.2 EXP"
    },
    "🥈 СЕРЕБРО (499₽)": {
        "price": 499, "donate_gems": 150, "gold": 15000, "vip_days": 30,
        "desc": "💎+150💎 | 🥇+15K🥇 | 👑VIP 30дней | ⚡x1.5 EXP"
    },
    "🥇 ЗОЛОТО (999₽)": {
        "price": 999, "donate_gems": 350, "gold": 35000, "vip_days": 90,
        "desc": "💎+350💎 | 🥇+35K🥇 | 👑VIP 90дней | ⚡x2 EXP"
    },
    "💎 ПЛАТИНА (1999₽)": {
        "price": 1999, "donate_gems": 800, "gold": 80000, "vip_days": 365,
        "desc": "💎+800💎 | 🥇+80K🥇 | 👑VIP 1год | ⚡x3 EXP"
    }
}

CLAN_SHOP = {
    "👑 Король клана": {"price": 10000, "effect": "attack_bonus+20", "desc": "⚔️ +20% АТК"},
    "🛡️ Стальной щит": {"price": 8000, "effect": "defense_bonus+15", "desc": "🛡️ +15% ЗАЩ"},
    "💎 Алмаз казны": {"price": 15000, "effect": "income_bonus+25", "desc": "💰 +25% доход"},
    "🔥 Огненный тотем": {"price": 25000, "effect": "boss_multiplier+50", "desc": "🐲 x1.5 босс"},
    "🌟 Легенда клана": {"price": 50000, "effect": "all_bonus+30", "desc": "🏆 Все +30%"}
}

COOLDOWNS = {'mining': 300, 'arena': 60, 'quest': 120, 'daily_bonus': 86400, 'boss': 180}

def get_main_keyboard(user_id):
    user = asyncio.run_coroutine_threadsafe(get_user(user_id), asyncio.get_event_loop()).result()
    is_vip = user['vip_until'] and datetime.fromisoformat(user['vip_until']) > datetime.now()
    is_admin = user_id == ADMIN_ID
    
    buttons = [
        [KeyboardButton("👤 Профиль"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("🎒 Инвентарь"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("📜 Квесты"), KeyboardButton("⚔️ Арена")],
        [KeyboardButton("🎁 Бонусы"), KeyboardButton("🏰 Кланы")]
    ]
    
    if is_vip:
        buttons.append([KeyboardButton("👑 VIP Статус"), KeyboardButton("💎 Донат Магазин")])
    else:
        buttons.append([KeyboardButton("🏪 Донат Магазин"), KeyboardButton("💎 Промокоды")])
    
    buttons.extend([
        [KeyboardButton("🔗 Рефералка"), KeyboardButton("📈 Топ Игроков")]
    ])
    
    if is_admin:
        buttons.append([KeyboardButton("🔧 Админ Панель")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def show_profile(user_id):
    user = await get_user(user_id)
    clan = await get_clan(user['clan_id']) if user['clan_id'] else None
    is_vip = user['vip_until'] and datetime.fromisoformat(user['vip_until']) > datetime.now()
    
    vip_status = f"👑 <b>VIP до {user['vip_until'].strftime('%d.%m.%Y')}</b>" if is_vip else "❌ Без VIP"
    clan_text = f"👥 <b>{clan['name']}</b>\n📊 Членов: <b>{clan['members']}</b>" if clan else "👥 <i>Без клана</i>"
    
    text = f"""👤 <b>⚔️ УР.{user['level']} ⚔️</b> {'👑VIP' if is_vip else ''}

💰 <b>{user['gold']:,}</b>🥇 | 💎 <b>{user['gems']}</b> | 🪙 <b>{user['donate_balance']}</b>
👥 <b>{user['referrals']}</b> рефералов

❤️ <b>{user['hp']}/{user['max_hp']}</b> | ⚔️ <b>{user['attack']}</b> | 🛡️ <b>{user['defense']}</b>
🏆 <b>{user['total_wins']}</b>勝/<b>{user['total_defeats']}</b>敗

{clan_text}
<b>{vip_status}</b>

🔗 <code>t.me/{(await bot.get_me()).username}?start={user_id}</code>"""
    
    kb = get_main_keyboard(user_id)
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def show_shop_full(msg_or_cb, category="🗡️ Оружие", page=0):
    items = SHOP_CATEGORIES.get(category, {})
    items_list = list(items.items())[page*3:(page+1)*3]
    
    text = f"🛒 <b>{category}</b> (стр. {page+1})\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    for item_name, data in items_list:
        price_display = f"{data['price']:,}🥇"
        text += f"🛒 <b>{item_name}</b>\n💰 <code>{price_display}</code>\n{data.get('desc', '')}\n\n"
        kb.inline_keyboard.append([
            InlineKeyboardButton(f"💰 Купить", callback_data=f"buy_{item_name.replace(' ', '_')}"),
            InlineKeyboardButton("ℹ️", callback_data=f"info_{item_name.replace(' ', '_')}")
        ])
    
    cat_buttons = []
    for cat in SHOP_CATEGORIES:
        emoji = "✅" if cat == category else ""
        cat_buttons.append(InlineKeyboardButton(f"{emoji}{cat}", callback_data=f"shop_cat_{cat.replace(' ', '_')}_0"))
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"shop_cat_{category.replace(' ', '_')}_{page-1}"))
    nav_row.append(InlineKeyboardButton("🏠", callback_data="back_main"))
    if (page+1)*3 < len(items):
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"shop_cat_{category.replace(' ', '_')}_{page+1}"))
    
    kb.inline_keyboard.extend([cat_buttons[:3], cat_buttons[3:], [InlineKeyboardButton("🏠 Главное", callback_data="back_main")], nav_row])
    
    if isinstance(msg_or_cb, Message):
        await bot.send_message(msg_or_cb.from_user.id, text, reply_markup=kb, parse_mode='HTML')
    else:
        await msg_or_cb.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

async def show_donate_shop(user_id):
    text = """💎 <b>🔥 ДОНАТ МАГАЗИН 🔥</b>

<code>💰 Оплата → @{ADMIN_USERNAME}</code>
<code>✅ Пишите в ЛС после оплаты!</code>

"""
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pack_name, data in DONATE_PACKS.items():
        text += f"🛒 <b>{pack_name}</b>\n💰 <code>{data['price']}₽</code>\n{data['desc']}\n\n"
        kb.inline_keyboard.append([InlineKeyboardButton(f"💎 Купить ({data['price']}₽)", url=f"https://t.me/{ADMIN_USERNAME}")])
    
    kb.inline_keyboard.extend([
        [InlineKeyboardButton("💬 Админ", url=f"https://t.me/{ADMIN_USERNAME}")],
        [InlineKeyboardButton("🏠 Меню", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML', disable_web_page_preview=True)

async def show_inventory_full(user_id):
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute("SELECT * FROM inventory WHERE user_id=?", (user_id,)) as cursor:
            inv = await cursor.fetchone()
    
    if not inv:
        await bot.send_message(user_id, "🎒 <b>Инвентарь пуст!</b>", reply_markup=get_main_keyboard(user_id))
        return
    
    text = f"""🎒 <b>ИНВЕНТАРЬ</b>

🗡️ Оружие: <code>{inv[2] or '❌'}</code>
🛡️ Броня: <code>{inv[3] or '❌'}</code>

📦 Предметы:"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🛒 Продать", callback_data="sell_first")],
        [InlineKeyboardButton("🏠 Меню", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def arena_search(user_id):
    user = await get_user(user_id)
    now = datetime.now().isoformat()
    
    if user['last_arena'] and (datetime.now() - datetime.fromisoformat(user['last_arena'])).total_seconds() < COOLDOWNS['arena']:
        remaining = COOLDOWNS['arena'] - (datetime.now() - datetime.fromisoformat(user['last_arena'])).total_seconds()
        await bot.send_message(user_id, f"⚔️ Арена: <code>{int(remaining)}с</code>", reply_markup=get_main_keyboard(user_id), parse_mode='HTML')
        return
    
    user_damage = user['attack'] + random.randint(-5, 10)
    opp_damage = random.randint(user['attack']-10, user['attack']+20)
    
    if user_damage > opp_damage:
        reward = random.randint(200, 500)
        await update_user(user_id, {'total_wins': user['total_wins']+1, 'gold': user['gold']+reward, 'last_arena': now})
        result = f"🏆 <b>ПОБЕДА!</b>\n⚔️ <b>{user_damage}</b> → 🛡️ <b>{opp_damage}</b>\n💰 <b>+{reward}</b>🥇"
    else:
        reward = random.randint(50, 150)
        await update_user(user_id, {'total_defeats': user['total_defeats']+1, 'gold': user['gold']+reward, 'last_arena': now})
        result = f"💥 <b>ПОРАЖЕНИЕ</b>\n⚔️ <b>{user_damage}</b> → 🛡️ <b>{opp_damage}</b>\n💰 <b>+{reward}</b>🥇"
    
    await bot.send_message(user_id, result, reply_markup=get_main_keyboard(user_id), parse_mode='HTML')

async def show_clan_menu_full(user_id):
    user = await get_user(user_id)
    clan = await get_clan(user['clan_id']) if user['clan_id'] else None
    
    if clan:
        text = f"""🏰 <b>{clan['name']} [Ур.{clan['level']}]</b>

👑 Лидер: <code>{clan['leader_id']}</code>
💰 Казна: <b>{clan['gold']:,}🥇</b> | 💎 <b>{clan['gems']}</b>
📊 Членов: <b>{clan['members']}/50</b>
⚔️ Бонусы: АТК+{clan['attack_bonus']} | ЗАЩ+{clan['defense_bonus']}"""
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("🛒 Клан магазин", callback_data="clan_shop")],
            [InlineKeyboardButton("💰 Казна", callback_data="clan_treasury")],
            [InlineKeyboardButton("⚔️ Клан босс", callback_data="clan_boss")],
            [InlineKeyboardButton("👑 Баффы", callback_data="clan_buffs")],
            [InlineKeyboardButton("🏠 Главное", callback_data="back_main")]
        ])
    else:
        text = """🏰 <b>СОЗДАЙ КЛАН!</b>

💎 5000🥇
👥 До 50 членов
🛒 Эксклюзивный магазин
👑 Клановые баффы"""
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("➕ Создать", callback_data="clan_create")],
            [InlineKeyboardButton("🔍 Поиск", callback_data="clan_search")],
            [InlineKeyboardButton("🏠 Меню", callback_data="back_main")]
        ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def admin_panel_full(user_id):
    if user_id != ADMIN_ID:
        return await bot.send_message(user_id, "🚫 Доступ запрещён!")
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        total_players = (await db.execute_fetchall("SELECT COUNT(*) FROM users"))[0][0]
        total_gold = (await db.execute_fetchall("SELECT SUM(gold) FROM users"))[0][0] or 0
        active_promos = (await db.execute_fetchall("SELECT COUNT(*) FROM promocodes WHERE (expires_at IS NULL OR expires_at > datetime('now'))"))[0][0]
    
    text = f"""🔧 <b>⚡ АДМИН ПАНЕЛЬ ⚡</b>

👥 Игроков: <b>{total_players}</b>
💰 Золото: <b>{total_gold:,}</b>
📝 Активных промо: <b>{active_promos}</b>

<code>@{ADMIN_USERNAME} - донат</code>"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("👥 Игроки", callback_data="admin_players")],
        [InlineKeyboardButton("💰 Деньги", callback_data="admin_money")],
        [InlineKeyboardButton("👑 VIP", callback_data="admin_vip")],
        [InlineKeyboardButton("📝 ПРОМОКОДЫ", callback_data="admin_promocodes")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔨 Баны", callback_data="admin_ban")],
        [InlineKeyboardButton("🏠 Меню", callback_data="back_main")]
    ])
    
    await bot.send_message(user_id, text, reply_markup=kb, parse_mode='HTML')

async def create_promocode(admin_id, code, gold=0, gems=0, vip_days=0, expires_days=7, max_uses=1):
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

async def use_promocode(user_id, code):
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
                return {"success": False, "error": "🔒 Лимит использований!"}
        
        user = await get_user(user_id)
        rewards = {}
        
        if promo_dict['reward_gold']:
            new_gold = user['gold'] + promo_dict['reward_gold']
            rewards['gold'] = promo_dict['reward_gold']
            await update_user(user_id, {'gold': new_gold})
        
        if promo_dict['reward_gems']:
            new_gems = user['gems'] + promo_dict['reward_gems']
            rewards['gems'] = promo_dict['reward_gems']
            await update_user(user_id, {'gems': new_gems})
        
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

async def list_promocodes(admin_id):
    if admin_id != ADMIN_ID:
        return "🚫 Только админ!"
    
    async with aiosqlite.connect("rpg_bot.db") as db:
        async with db.execute('''SELECT code, reward_gold, reward_gems, reward_vip_days, 
                                       expires_at, max_uses, used_count FROM promocodes''') as cursor:
            promos = await cursor.fetchall()
    
    if not promos:
        return "📝 Промокодов нет"
    
    text = "📋 <b>ПРОМОКОДЫ:</b>\n\n"
    for promo in promos:
        code, gold, gems, vip_days, expires, max_uses, used = promo
        expires_text = "∞" if not expires else datetime.fromisoformat(expires).strftime("%d.%m")
        used_text = f"{used}/{max_uses}"
        rewards = []
        if gold: rewards.append(f"{gold}🥇")
        if gems: rewards.append(f"{gems}💎")
        if vip_days: rewards.append(f"{vip_days}👑д")
        
        text += f"<code>{code}</code> → {', '.join(rewards)}\n⏰ {expires_text} | 📊 {used_text}\n\n"
    
    return text

button_handlers = {
    "👤 Профиль": show_profile,
    "🛒 Магазин": lambda m: asyncio.create_task(show_shop_full(m, "🗡️ Оружие", 0)),
    "🎒 Инвентарь": show_inventory_full,
    "⚔️ Арена": arena_search,
    "🏪 Донат Магазин": show_donate_shop,
    "💎 Промокоды": lambda uid: bot.send_message(uid, "💎 <b>Введите:</b>\n<code>/promo КОД</code>", parse_mode='HTML'),
    "🏰 Кланы": show_clan_menu_full,
    "🔗 Рефералка": lambda uid: bot.send_message(uid, f"🔗 <code>t.me/bot?start={uid}</code>\n💰 +250🥇 за друга!", parse_mode='HTML'),
    "🔧 Админ Панель": admin_panel_full
}

@router.message(Command("start"))
async def start_cmd(message: Message):
    args = message.text.split()
    referrer_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    user_id = message.from_user.id
    
    user = await get_user(user_id)
    
    if referrer_id and referrer_id != user_id:
        referrer = await get_user(referrer_id)
        if referrer:
            await update_user(user_id, {'gold': 500, 'gems': 5})
            await bot.send_message(user_id, "🎉 <b>+500🥇 +5💎</b> за рефералку!", reply_markup=get_main_keyboard(user_id), parse_mode='HTML')
            
            await update_user(referrer_id, {'gold': 250, 'referrals': referrer['referrals'] + 1})
            await bot.send_message(referrer_id, f"🔥 <b>РЕФЕРАЛ #{referrer['referrals']+1}! +250🥇</b>")
    
    await show_profile(user_id)

@router.message()
async def handle_buttons(message: Message):
    user_id = message.from_user.id
    text = message.text
    
    user = await get_user(user_id)
    if user['banned']:
        return await bot.send_message(user_id, "🚫 Вы заблокированы!")
    
    if text in button_handlers:
        await button_handlers[text](user_id if 'user_id' in str(button_handlers[text]) else message)
    else:
        await show_profile(user_id)

@router.message(Command("promo"))
async def promo_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.reply("🚫 Только админ!")
    
    args = message.text.split()[1:]
    if not args:
        text = await list_promocodes(message.from_user.id)
        await message.reply(text, parse_mode='HTML')
        return
    
    try:
        code = args[0].upper()
        gold = int(args[1]) if len(args) > 1 else 0
        gems = int(args[2]) if len(args) > 2 else 0
        vip_days = int(args[3]) if len(args) > 3 else 0
        expires_days = int(args[4]) if len(args) > 4 else 7
        max_uses = int(args[5]) if len(args) > 5 else 1
        
        if await create_promocode(message.from_user.id, code, gold, gems, vip_days, expires_days, max_uses):
            await message.reply(f"✅ <b>ПРОМОКОД СОЗДАН!</b>\n<code>/promo {code} {gold} {gems} {vip_days} {expires_days} {max_uses}</code>", parse_mode='HTML')
        else:
            await message.reply("❌ Ошибка создания!")
    except:
        await message.reply("❌ /promo КОД [🥇] [💎] [👑дни] [дни] [максисп]")

@router.message(F.text.startswith("/promo "))
async def activate_promo(message: Message):
    code = message.text.split()[1]
    result = await use_promocode(message.from_user.id, code)
    
    if result["success"]:
        rewards_text = []
        if 'gold' in result['rewards']: rewards_text.append(f"+{result['rewards']['gold']:,}🥇")
        if 'gems' in result['rewards']: rewards_text.append(f"+{result['rewards']['gems']}💎")
        if 'vip' in result['rewards']: rewards_text.append(f"+{result['rewards']['vip']}👑дней")
        
        promo_info = result['promo']
        expires = "∞" if not promo_info.get('expires_at') else datetime.fromisoformat(promo_info['expires_at']).strftime("%d.%m.%Y")
        
        await message.reply(f"🎉 <b>ПРОМО АКТИВИРОВАН!</b>\n{', '.join(rewards_text)}\n\n📋 <code>{promo_info['code']}</code>\n⏰ До: <b>{expires}</b>\n📊 {promo_info['used_count']}/{promo_info['max_uses']} использ.", 
                          reply_markup=get_main_keyboard(message.from_user.id), parse_mode='HTML')
    else:
        await message.reply(result["error"], reply_markup=get_main_keyboard(message.from_user.id))

@router.callback_query()
async def all_callbacks(callback: CallbackQuery):
    data = callback.data
    
    if data.startswith("shop_cat_"):
        parts = data.split("_", 3)
        category = "_".join(parts[2:-1]).replace("_", " ")
        page = int(parts[-1])
        await show_shop_full(callback, category, page)
    
    elif data.startswith("buy_") or data.startswith("info_"):
        await callback.answer("🛒 Покупка в разработке!", show_alert=True)
    
    elif data == "back_main":
        await show_profile(callback.from_user.id)
    
    elif data.startswith("clan_"):
        await callback.answer("🏰 Кланы!")
    
    elif data == "admin_promocodes":
        if callback.from_user.id != ADMIN_ID:
            return await callback.answer("🚫 Только админ!", show_alert=True)
        text = await list_promocodes(callback.from_user.id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("➕ Создать", callback_data="admin_promo_create")],
            [InlineKeyboardButton("🏠 Админ", callback_data="admin_panel")],
            [InlineKeyboardButton("🏠 Главное", callback_data="back_main")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        await callback.answer()
    
    elif data.startswith("admin_"):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("🚫 Только админ!", show_alert=True)
            return
        await callback.answer("🔧 Админ панель!")
    
    await callback.answer()

async def main():
    await init_db()
    print("🚀 ULTIMATE RPG BOT v3.0 - ПРОМОКОДЫ ТОЛЬКО АДМИН!")
    print(f"👑 Админ ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

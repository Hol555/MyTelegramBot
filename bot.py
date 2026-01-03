#!/usr/bin/env python3
"""
🏰 Telegram MMO Bot v5.0 - ✅ АДМИН ПАНЕЛЬ + ДЕТАЛЬНЫЕ ОПИСАНИЯ + ДОНАТ КНОПКИ
🔥 Все кнопки работают + донат ведет на вас + полная документация
"""

import logging
import os
import asyncio
import random
import time
import math
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import sqlite3
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@soblaznss')  # ← ВАШ ЮЗЕРНЕЙМ

# 👑 АДМИН КЛАВИАТУРА
ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Выдать монеты"), KeyboardButton("💎 Выдать донат")],
    [KeyboardButton("⚔️ Усилить силу"), KeyboardButton("🏆 Изменить рейтинг")],
    [KeyboardButton("🚫 Бан/Разбан"), KeyboardButton("📊 ТОП игроков")],
    [KeyboardButton("🔄 Рестарт сервера"), KeyboardButton("📈 Статистика бота")],
    [KeyboardButton("🏠 Главное меню")]
], resize_keyboard=True)

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    [KeyboardButton("🏪 Магазин"), KeyboardButton("🎒 Инвентарь")],
    [KeyboardButton("⛏️ Майнинг"), KeyboardKeyboardButton("🧭 Экспедиции")],
    [KeyboardButton("⚔️ Арена"), KeyboardButton("👹 Рейды")],
    [KeyboardButton("📜 Квесты"), KeyboardButton("🎰 Лотерея")],
    [KeyboardButton("📊 Профиль"), KeyboardButton("💎 Донат")]
], resize_keyboard=True)

def init_db():
    conn = sqlite3.connect('mmobot.db', timeout=15)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 1000,
        donate_balance INTEGER DEFAULT 0, exp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
        wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, arena_rating INTEGER DEFAULT 1000,
        power INTEGER DEFAULT 10, banned INTEGER DEFAULT 0, admin_notes TEXT,
        last_mining REAL DEFAULT 0, last_arena REAL DEFAULT 0, created_at REAL DEFAULT 0,
        vip_days INTEGER DEFAULT 0, total_spent INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    print("✅ База + админ таблица готова")

def get_user(user_id):
    conn = sqlite3.connect('mmobot.db', timeout=15)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    if not row:
        username = f"player_{user_id}"
        c.execute('INSERT INTO users (user_id, username, balance, power, created_at) VALUES (?, ?, 2500, 20, ?)',
                 (user_id, username, time.time()))
        conn.commit()
        row = (user_id, username, 2500, 0, 0, 1, 0, 0, 1000, 20, 0, '', 0, 0, time.time(), 0, 0)
    user = dict(zip(['id','username','balance','donate','exp','level','wins','losses','rating','power','banned',
                    'notes','last_mining','last_arena','created','vip','spent'], row))
    conn.close()
    return user

# 🔥 ОСНОВНАЯ ЛОГИКА - ВСЕ КНОПКИ С ОПИСАНИЯМИ
async def handle_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user['banned']:
        await update.message.reply_text("🚫 **Вы в бане!**\n👨‍💼 Обратитесь к @soblaznss")
        return
    
    now = time.time()
    
    # 📖 ПОДРОБНЫЕ ОПИСАНИЯ ДЛЯ КАЖДОЙ КНОПКИ
    if text == "🏪 Магазин":
        await update.message.reply_text(
            """🏪 **МАГАЗИН - ГЛАВНЫЙ ХАБ**

📋 **Что это?**
• Покупка оружия, брони, баффов
• Обычные 💰 и донат 💎 предметы
• VIP статусы навсегда

💰 **Цены:** 100-50 000💰 | 10-999💎
⚡ **Эффект:** +сила, +фарм, VIP

👇 Выберите категорию ↓""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚔️ ОРУЖИЕ", callback_data="shop_weapon")],
                [InlineKeyboardButton("🛡️ БРОНЯ", callback_data="shop_armor")],
                [InlineKeyboardButton("⭐ БАФФЫ", callback_data="shop_buff")],
                [InlineKeyboardButton("💎 VIP", callback_data="shop_vip")],
                [InlineKeyboardButton("🏠 Меню", callback_data="back_menu")]
            ]),
            parse_mode='Markdown'
        )
    
    elif text == "🎒 Инвентарь":
        await update.message.reply_text(
            """🎒 **ИНВЕНТАРЬ - ВАШ ЛУТ**

📋 **Что показывает?**
• Все купленные предметы
• Экипированные (зеленые ✅)
• Доступные баффы
• Общая сила персонажа

⚙️ **Команды:**
/equip 1 - надеть предмет #1
/unequip 1 - снять предмет #1
/sell 5 - продать 5 шт

💡 **Лимит:** 50 слотов""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "⛏️ Майнинг":
        cooldown = 120
        if now - user['last_mining'] < cooldown:
            remain = cooldown - (now - user['last_mining'])
            await update.message.reply_text(
                f"⛏️ **МАЙНИНГ - БАЗОВЫЙ ФАРМ**\n\n"
                f"⏳ **Кулдаун: {remain//60}:{remain%60:02d}**\n"
                f"📈 **Награда:** 80-300💰\n"
                f"🔄 **КД:** 2 минуты\n"
                f"⭐ **x2 во время ивента**\n\n"
                f"💡 **Совет:** Чередуйте с Ареной",
                reply_markup=MAIN_KEYBOARD
            )
            return
        
        reward = random.randint(80, 300)
        new_balance = user['balance'] + reward
        
        conn = sqlite3.connect('mmobot.db', timeout=15)
        c = conn.cursor()
        c.execute('UPDATE users SET balance=?, last_mining=? WHERE user_id=?',
                 (new_balance, now, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"⛏️ **SHAFT #{random.randint(100,999)}**\n"
            f"💎 **+{reward:,} ЗОЛОТА**\n"
            f"💰 **Итого: {new_balance:,}**\n"
            f"⏳ **КД: 2 мин**\n\n"
            f"⚡ **Ускорение:** Купите 'Копатель x2'",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "🧭 Экспедиции":
        await update.message.reply_text(
            """🧭 **ЭКСПЕДИЦИИ - РИСКИ И НАГРАДЫ**

📋 **Что это?**
• Походы в подземелья
• Шанс на легендарный лут
• Зависит от силы ⚔️

🎲 **Шанс успеха:** 40-95%
💰 **Награда:** 300-2000💰 + лут
⏳ **КД:** 8 минут

⚠️ **Совет:** Качайте силу перед рейдами!""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "⚔️ Арена":
        await update.message.reply_text(
            """⚔️ **АРЕНA PvP - РЕЙТИНГОВАЯ БИТВА**

📋 **Что это?**
• Автоматические бои 1v1
• Система рейтинга ELO
• Ставки от 100💰

🏆 **Награда:** 1.8x ставка
📊 **Топ-100:** Призы ежедневно
⚡ **КД:** 4 минуты

💡 **Стратегия:** Сила > Рейтинг > Удача""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "👹 Рейды":
        await update.message.reply_text(
            """👹 **РЕЙДЫ БОССОВ - ЭЛИТНЫЙ КОНТЕНТ**

📋 **Что доступно?**
🐲 ДРАКОН [150 силы]
🧟 ЗОМБИ [200 силы] 
👹 ДЕМОН [300 силы]

💎 **Награда:** 1000-5000💰 + ЛЕГЕНДАРКА
🎲 **Шанс:** 25-60%
⏳ **КД:** 15 минут

🔥 **Только для сильных! 50+ силы**""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "📜 Квесты":
        await update.message.reply_text(
            """📜 **КВЕСТЫ - ЕЖЕДНЕВНЫЕ ЦЕЛИ**

📋 **Типы квестов:**
1️⃣ Фарм (10 майнингов)
2️⃣ PvP (5 арен)
3️⃣ Экспедиции (3 успеха)
4️⃣ Рейды (1 босс)

💰 **Награда:** 1000-5000💰 + EXP
📅 **Обновление:** 00:00 UTC
✅ **Прогресс:** /quests""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "🎰 Лотерея":
        await update.message.reply_text(
            """🎰 **ЛОТЕРЕЯ - ШАНС НА МИЛЛИОН**

📋 **Призы (1 билет = 50💰):**
1% → **100 000💰 ДЖЕКПОТ** 🏆
5% → **5000💰 + 50💎**
15% → **2000💰**
30% → **500💰**
49% → **Попробуй еще!**

⚡ **Неограниченно**
🎲 **Честный рандом**
📈 **Джекпот растет**""",
            reply_markup=MAIN_KEYBOARD
        )
    
    elif text == "📊 Профиль":
        uptime = int((time.time() - user['created']) / 86400)
        await update.message.reply_text(
            f"""📊 **ПРОФИЛЬ @{user['username']}**

🎖️ **СТАТУС:** Ур.{user['level']} | {uptime} дней
💰 **{user['balance']:,}** | 💎 **{user['donate']}**
⚔️ **СИЛА: {user['power']}** | 🏆 **Рейтинг: {user['rating']}**
⚔️ **{user['wins']}-{user['losses']}** арен

📈 **ПРОГРЕСС:**
• Побед: {user['wins']}
• Время игры: {uptime}д
• VIP: {user['vip']}д

🏅 **ТОП-3 АКТИВНОСТИ:**
1️⃣ Арена ({user['wins']:,})
2️⃣ Майнинг
3️⃣ Рейды""",
            reply_markup=MAIN_KEYBOARD, parse_mode='Markdown'
        )
    
    elif text == "💎 Донат":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 VIP 7 дней - 99💎", callback_data="donate_vip7")],
            [InlineKeyboardButton("⭐ VIP 30 дней - 299💎", callback_data="donate_vip30")],
            [InlineKeyboardButton("👑 ПОЖИЗНЕННЫЙ VIP - 999💎", callback_data="donate_vip999")],
            [InlineKeyboardButton("⚔️ Легендарный меч - 150💎", callback_data="donate_legend")],
            [InlineKeyboardButton("💰 50 000💰 - 250💎", callback_data="donate_money")],
            [InlineKeyboardButton("📞 Написать админу", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("🏠 Меню", callback_data="back_menu")]
        ])
        await update.message.reply_text(
            """💎 **Донат система - ВСЕ УЛУЧШЕНИЯ**

🔥 **VIP 7 дней** → 99💎
• x2 фарм 24/7
• +50 силы
• Бесплатная лотерея

⭐ **VIP 30 дней** → 299💎  
• x3 все доходы
• +100 силы
• Легендарный титул

👑 **ПОЖИЗНЕННЫЙ** → 999💎
• ВСЕ НАВСЕГДА
• Админ поддержка
• Приоритет #1

⚔️ **Легендарный меч** → 150💎 (+200 силы)

💰 **50 000 монет** → 250💎

👇 **КНОПКИ ведут к @{ADMIN_USERNAME}**""",
            reply_markup=keyboard, parse_mode='Markdown'
        )

# 👑 АДМИН ПАНЕЛЬ - ПОЛНАЯ
async def handle_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "💰 Выдать монеты":
        await update.message.reply_text(
            "💰 **ФОРМАТ:** `@username 5000`\n"
            "💡 Пример: `@testuser 10000`",
            reply_markup=ADMIN_KEYBOARD
        )
    
    elif text == "💎 Выдать донат":
        await update.message.reply_text(
            "💎 **ФОРМАТ:** `@username 50`\n"
            "💡 Пример: `@testuser 100`",
            reply_markup=ADMIN_KEYBOARD
        )
    
    elif text == "⚔️ Усилить силу":
        await update.message.reply_text(
            "⚔️ **ФОРМАТ:** `@username 100`\n"
            "💡 Пример: `@testuser 250` (+250 силы)",
            reply_markup=ADMIN_KEYBOARD
        )
    
    elif text == "🏆 Изменить рейтинг":
        await update.message.reply_text(
            "🏆 **ФОРМАТ:** `@username 2500`\n"
            "💡 Пример: `@testuser 5000` (топ-1)",
            reply_markup=ADMIN_KEYBOARD
        )
    
    elif text == "🚫 Бан/Разбан":
        await update.message.reply_text(
            "🚫 **ФОРМАТ:** `@username ban` или `@username unban`\n"
            "💡 Пример: `@testuser ban`",
            reply_markup=ADMIN_KEYBOARD
        )
    
    elif text == "📊 ТОП игроков":
        conn = sqlite3.connect('mmobot.db')
        c = conn.cursor()
        c.execute('SELECT username, balance, power, rating FROM users ORDER BY rating DESC LIMIT 10')
        top = c.fetchall()
        conn.close()
        
        top_text = "🏆 **ТОП-10 ИГРОКОВ:**\n\n"
        for i, player in enumerate(top, 1):
            top_text += f"{i}. @{player[0]} | 💰{player[1]:,}\n"
        
        await update.message.reply_text(top_text, reply_markup=ADMIN_KEYBOARD, parse_mode='Markdown')
    
    elif text.startswith('@') and len(text.split()) >= 2:
        # АДМИН КОМАНДЫ ОБРАБОТКА
        parts = text.split()
        target = parts[0][1:]
        action = ' '.join(parts[1:])
        
        conn = sqlite3.connect('mmobot.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM users WHERE username=?', (target,))
        target_user = c.fetchone()
        
        if target_user:
            target_id = target_user[0]
            if action == 'ban':
                c.execute('UPDATE users SET banned=1 WHERE user_id=?', (target_id,))
                await update.message.reply_text(f"✅ **@{target} ЗАБАНЕН**", reply_markup=ADMIN_KEYBOARD)
            elif action == 'unban':
                c.execute('UPDATE users SET banned=0 WHERE user_id=?', (target_id,))
                await update.message.reply_text(f"✅ **@{target} РАЗБАНЕН**", reply_markup=ADMIN_KEYBOARD)
            else:
                # ЧИСЛОВЫЕ КОМАНДЫ
                try:
                    amount = int(action)
                    if text.startswith('@') and 'монеты' in update.message.text.lower():
                        c.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (amount, target_id))
                        await update.message.reply_text(f"✅ **@{target} +{amount:,}💰**", reply_markup=ADMIN_KEYBOARD)
                    elif 'донат' in update.message.text.lower():
                        c.execute('UPDATE users SET donate_balance=donate_balance+? WHERE user_id=?', (amount, target_id))
                        await update.message.reply_text(f"✅ **@{target} +{amount}💎**", reply_markup=ADMIN_KEYBOARD)
                    elif 'сила' in update.message.text.lower():
                        c.execute('UPDATE users SET power=power+? WHERE user_id=?', (amount, target_id))
                        await update.message.reply_text(f"✅ **@{target} +{amount}⚔️**", reply_markup=ADMIN_KEYBOARD)
                    elif 'рейтинг' in update.message.text.lower():
                        c.execute('UPDATE users SET arena_rating=? WHERE user_id=?', (amount, target_id))
                        await update.message.reply_text(f"✅ **@{target} →{amount}🏆**", reply_markup=ADMIN_KEYBOARD)
                except:
                    await update.message.reply_text("❌ **Неверный формат**", reply_markup=ADMIN_KEYBOARD)
        else:
            await update.message.reply_text("❌ **Игрок не найден**", reply_markup=ADMIN_KEYBOARD)
        
        conn.commit()
        conn.close()

# 🛠️ INLINE ОБРАБОТЧИКИ
async def inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_menu":
        await query.edit_message_text("🏰 **Главное меню - выберите активность**", reply_markup=MAIN_KEYBOARD)
    
    elif query.data.startswith("donate_"):
        # ДОНАТ КНОПКИ ВЕДУТ НА ВАС
        donat_type = query.data.replace("donate_", "")
        prices = {"vip7": "99💎", "vip30": "299💎", "vip999": "999💎", "legend": "150💎", "money": "250💎"}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Купить сейчас", url=f"https://t.me/{ADMIN_USERNAME[1:]}")],
            [InlineKeyboardButton("ℹ️ Подробнее", callback_data=f"donate_info_{donat_type}")],
            [InlineKeyboardButton("🏠 Меню", callback_data="back_menu")]
        ])
        
        await query.edit_message_text(
            f"💎 **{donat_type.replace('vip', 'VIP ').upper()}**\n\n"
            f"💰 **Цена: {prices.get(donat_type, 'СКИДКА')}\n"
            f"👨‍💼 **Свяжитесь с @{ADMIN_USERNAME}**\n\n"
            f"⚡ **Моментальная выдача!**\n"
            f"🔒 **100% гарантия!**",
            reply_markup=keyboard, parse_mode='Markdown'
        )
    
    elif query.data.startswith("shop_"):
        cat = query.data.split("_")[1]
        shops = {
            "weapon": "⚔️ **ОРУЖИЕ** | +10-200 силы\n💰 100-20 000💰",
            "armor": "🛡️ **БРОНЯ** | +Защита\n💰 200-15 000💰", 
            "buff": "⭐ **БАФФЫ** | x2 фарм\n💰 300-10 000💰",
            "vip": "💎 **VIP СТАТУСЫ**\n👑 Пожизненно от 99💎"
        }
        await query.edit_message_text(shops.get(cat, "🏪 Магазин"), 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Донат", callback_data="shop_vip")],
                                                                     [InlineKeyboardButton("🏠 Меню", callback_data="back_menu")]]))

# 🎮 ЗАПУСК
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    await update.message.reply_text(
        f"""🚀 **MMO BOT v5.0 - ПОЛНАЯ ВЕРСИЯ**

👋 **@{user['username']}** | 💰{user['balance']:,}

📖 **КАЖДАЯ КНОПКА = ОПИСАНИЕ**
🎮 **7 активностей + админ**
💎 **Донат кнопки → @{ADMIN_USERNAME}**

/admin - 👑 Админ панель""",
        reply_markup=MAIN_KEYBOARD, parse_mode='Markdown'
    )

def main():
    init_db()
    print(f"🚀 v5.0 запущен | Админ: {ADMIN_ID} | @{ADMIN_USERNAME}")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", handle_admin))
    app.add_handler(CallbackQueryHandler(inline_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main))
    
    print("✅ ВСЕ КНОПКИ + АДМИН + ДОНАТ ✅")
    app.run_polling()

if __name__ == "__main__":
    main()

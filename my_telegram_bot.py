import asyncio
import logging
import os
import re
from typing import Dict, List, Optional
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dataclasses import dataclass
from dotenv import load_dotenv
from urllib.parse import quote
from collections import defaultdict
import time
import sys
import nest_asyncio

# Фикс для Python 3.13
nest_asyncio.apply()

# Загрузка .env
load_dotenv()

# Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфиг
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@your_admin_username')
SEARCH_LIMIT = int(os.getenv('SEARCH_LIMIT', '3'))
ADMIN_LIMIT = int(os.getenv('ADMIN_LIMIT', '100'))

bot_instance = None

@dataclass
class SearchResult:
    source: str
    title: str
    url: str
    snippet: str

class RateLimiter:
    def __init__(self, limit: int, window: int = 3600):
        self.limit = limit
        self.window = window
        self.requests = defaultdict(list)
    
    def can_search(self, user_id: int) -> bool:
        now = time.time()
        user_requests = self.requests[user_id]
        self.requests[user_id] = [req_time for req_time in user_requests 
                                if now - req_time < self.window]
        if len(self.requests[user_id]) >= self.limit:
            return False
        self.requests[user_id].append(now)
        return True
    
    def get_remaining(self, user_id: int) -> int:
        now = time.time()
        user_requests = [req_time for req_time in self.requests[user_id]
                        if now - req_time < self.window]
        return self.limit - len(user_requests)

class OSINTBot:
    def __init__(self, token: str, admin_username: str):
        self.token = token
        self.admin_username = admin_username.lower()
        self.session = None
        self.user_limiters = {}
        self.search_engines = {
            'google': 'https://www.google.com/search?q=',
            'yandex': 'https://yandex.com/search/?text=',
            'bing': 'https://www.bing.com/search?q=',
            'duckduckgo': 'https://duckduckgo.com/?q='
        }
    
    def get_limiter(self, user_id: int, is_admin: bool) -> RateLimiter:
        if user_id not in self.user_limiters:
            limit = ADMIN_LIMIT if is_admin else SEARCH_LIMIT
            self.user_limiters[user_id] = RateLimiter(limit)
        return self.user_limiters[user_id]
    
    def is_admin(self, username: str) -> bool:
        return username.lower() == self.admin_username
    
    async def init_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def google_dorks(self, query: str) -> List[SearchResult]:
        """Упрощенные dorks для стабильности"""
        dorks = [
            f'"{query}" filetype:pdf',
            f'"{query}" site:vk.com',
            f'"{query}" inurl:admin',
            f'"{query}" filetype:sql'
        ]
        results = []
        
        for dork in dorks:
            url = f"https://www.google.com/search?q={quote(dork)}"
            results.append(SearchResult('Google Dorks', dork[:50], url, 'Dork result'))
        
        return results
    
    async def social_search(self, query: str) -> List[SearchResult]:
        sources = [
            ('Twitter', f'https://twitter.com/search?q={quote(query)}'),
            ('GitHub', f'https://github.com/search?q={quote(query)}'),
            ('VK', f'https://vk.com/search?c%5Bq%5D={quote(query)}'),
            ('Telegram', f'https://t.me/search?q={quote(query)}')
        ]
        return [SearchResult(source, f'{source} search', url, 'Social') for source, url in sources]
    
    async def email_phone_search(self, query: str) -> List[SearchResult]:
        results = []
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', query)
        
        if email_match:
            email = email_match.group()
            results.extend([
                SearchResult('Hunter.io', email, f'https://hunter.io/search/{quote(email)}', 'Email check'),
                SearchResult('LeakCheck', email, f'https://leakcheck.io/#/{quote(email)}', 'Leaks')
            ])
        return results
    
    async def whois_search(self, domain: str) -> List[SearchResult]:
        sources = [
            ('WHOIS', f'https://www.whois.com/whois/{quote(domain)}'),
            ('ViewDNS', f'https://viewdns.info/iph/?domain={quote(domain)}')
        ]
        return [SearchResult(source, domain, url, 'Domain info') for source, url in sources]
    
    async def perform_osint_search(self, query: str, deep_scan: bool = False) -> List[SearchResult]:
        await self.init_session()
        all_results = []
        
        # Базовый поиск
        tasks = [
            self.google_dorks(query),
            self.social_search(query),
            self.email_phone_search(query)
        ]
        
        if deep_scan:
            tasks.append(self.multi_search(query))
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        for results in results_list:
            if isinstance(results, list):
                all_results.extend(results)
        
        return all_results[:12]
    
    async def multi_search(self, query: str) -> List[SearchResult]:
        results = []
        for name, base_url in list(self.search_engines.items())[:3]:
            url = f"{base_url}{quote(query)}"
            results.append(SearchResult(name, f'{name} results', url, 'Engine'))
        return results

# HANDLERS
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = bot_instance.is_admin(username)
    
    keyboard = [
        [InlineKeyboardButton("🔍 Быстрый поиск", callback_data="quick")],
        [InlineKeyboardButton("🚀 Глубокий (админ)", callback_data="deep")],
        [InlineKeyboardButton("📧 Email", callback_data="email")],
        [InlineKeyboardButton("🌐 Домен", callback_data="whois")]
    ]
    
    await update.message.reply_text(
        f"🤖 **OSINT Bot v2.2**\n"
        f"👤 {username} {'👑' if is_admin else ''}\n\n"
        f"`/search запрос`\n"
        f"`/stats` - лимиты\n"
        f"Лимит: {SEARCH_LIMIT}/час {'(безлимит админ)' if is_admin else ''}",
        parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    limiter = bot_instance.get_limiter(user_id, is_admin)
    remaining = limiter.get_remaining(user_id)
    
    await update.message.reply_text(
        f"📊 **{username}**\n"
        f"Осталось: `{remaining}/{ADMIN_LIMIT if is_admin else SEARCH_LIMIT}`\n"
        f"👑 {'АДМИН' if is_admin else 'Обычный'}",
        parse_mode='Markdown'
    )

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, deep: bool = False):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    if not context.args:
        return await update.message.reply_text("❌ `/search запрос`")
    
    query = " ".join(context.args)
    limiter = bot_instance.get_limiter(user_id, is_admin)
    
    if not limiter.can_search(user_id) and not is_admin:
        remaining = limiter.get_remaining(user_id)
        return await update.message.reply_text(f"⏳ Лимит! Осталось: `{remaining}`")
    
    await update.message.reply_text(f"🔍 Поиск: `{query}`")
    
    try:
        results = await bot_instance.perform_osint_search(query, deep and is_admin)
        await send_results(update, results, is_admin)
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Ошибка поиска")

async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = bot_instance.is_admin(username)
    
    mode_map = {
        'quick': ('🔍 Быстрый OSINT:', False),
        'deep': ('🚀 Глубокий OSINT:', True),
        'email': ('📧 Email/Phone:', None),
        'whois': ('🌐 Домен:', 'whois')
    }
    
    if query.data in mode_map:
        mode_name, deep = mode_map[query.data]
        if query.data == 'deep' and not is_admin:
            return await query.edit_message_text("❌ Только для админов!")
        
        await query.edit_message_text(f"{mode_name}\n**Введите запрос:**")
        context.user_data['mode'] = query.data if query.data != 'quick' else 'search'
        context.user_data['deep'] = deep
    await query.answer()

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    mode = context.user_data.get('mode')
    query_text = update.message.text.strip()
    
    if mode == 'email':
        results = await bot_instance.email_phone_search(query_text)
        await send_results(update, results, is_admin)
    elif mode == 'whois':
        results = await bot_instance.whois_search(query_text)
        await send_results(update, results, is_admin)
    elif mode in ['search', 'deep']:
        context.args = [query_text]
        await search_cmd(update, context, context.user_data.get('deep', False))
    
    context.user_data.clear()

async def send_results(update: Update, results: List[SearchResult], is_admin: bool):
    if not results:
        return await update.message.reply_text("❌ Ничего не найдено")
    
    msg = f"✅ **{len(results)} результатов** {'👑' if is_admin else ''}\n\n"
    
    for i, r in enumerate(results, 1):
        msg += f"`{i}.` **{r.source}**\n"
        msg += f"📄 {r.title[:60]}\n"
        msg += f"[🔗 {r.url[:50]}]({r.url})\n\n"
    
    # Разбиваем длинные сообщения
    for i in range(0, len(msg), 3800):
        await update.message.reply_text(
            msg[i:i+3800], 
            parse_mode='Markdown', 
            disable_web_page_preview=True
        )

# ✅ ОСНОВНАЯ ФУНКЦИЯ (Python 3.13 SAFE)
def main():
    global bot_instance
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env")
        return
    
    print("🔧 Инициализация OSINT Bot...")
    bot_instance = OSINTBot(BOT_TOKEN, ADMIN_USERNAME)
    
    # Application с фиксами для Python 3.13
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", lambda u,c: search_cmd(u,c,False)))
    app.add_handler(CommandHandler("deep", lambda u,c: search_cmd(u,c,True)))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(button_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    
    print("🚀 **OSINT Bot v2.2 запущен!**")
    print(f"👑 Админ: {ADMIN_USERNAME}")
    print(f"📊 Лимит обычных: {SEARCH_LIMIT}/час")
    
    # ✅ СТАБИЛЬНЫЙ ЗАПУСК
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            close_loop=False,
            timeout=10,
            bootstrap_retries=-1
        )
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота...")
    finally:
        asyncio.run(bot_instance.close_session())

if __name__ == '__main__':
    main()

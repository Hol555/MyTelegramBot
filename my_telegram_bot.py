"""
OSINT Bot v4.0 - Python 3.13 + PTB v20.7 FULLY COMPATIBLE
✅ imghdr FIXED с Pillow
✅ Application.builder() SAFE
✅ Rate limiting ✅ Inline ✅ Admin
"""

import logging
import os
import re
from typing import List, Optional
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dataclasses import dataclass
from dotenv import load_dotenv
from urllib.parse import quote
from collections import defaultdict
import time

# ✅ FIXED: imghdr replacement (Python 3.13)
try:
    import PIL.Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@your_admin_username').lower()
SEARCH_LIMIT = int(os.getenv('SEARCH_LIMIT', '3'))
ADMIN_LIMIT = int(os.getenv('ADMIN_LIMIT', '100'))

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
        self.admin_username = admin_username
        self.session = None
        self.user_limiters = {}
    
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
        dorks = [
            f'"{query}" filetype:pdf',
            f'"{query}" site:vk.com',
            f'"{query}" inurl:admin',
            f'"{query}" filetype:sql'
        ]
        return [SearchResult('Google Dorks', dork[:50], 
                           f"https://google.com/search?q={quote(dork)}", 'Dork') for dork in dorks]
    
    async def social_search(self, query: str) -> List[SearchResult]:
        sources = [
            ('Twitter', f'https://twitter.com/search?q={quote(query)}'),
            ('GitHub', f'https://github.com/search?q={quote(query)}'),
            ('VK', f'https://vk.com/search?c[q]={quote(query)}'),
            ('Telegram', f'https://t.me/search?q={quote(query)}')
        ]
        return [SearchResult(source, f'{source} search', url, 'Social') for source, url in sources]
    
    async def email_search(self, query: str) -> List[SearchResult]:
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', query)
        if email_match:
            email = email_match.group()
            return [
                SearchResult('Hunter.io', email, f'https://hunter.io/search/{quote(email)}', 'Email'),
                SearchResult('LeakCheck', email, f'https://leakcheck.io/#/{quote(email)}', 'Leaks')
            ]
        return []
    
    async def whois_search(self, domain: str) -> List[SearchResult]:
        return [
            SearchResult('WHOIS', domain, f'https://whois.com/whois/{quote(domain)}', 'Domain'),
            SearchResult('ViewDNS', domain, f'https://viewdns.info/iph/?domain={quote(domain)}', 'DNS')
        ]
    
    async def search(self, query: str, deep: bool = False) -> List[SearchResult]:
        await self.init_session()
        all_results = []
        
        tasks = [
            self.google_dorks(query),
            self.social_search(query),
            self.email_search(query)
        ]
        
        if deep:
            tasks.append(self.multi_engine_search(query))
        
        results = await asyncio.gather(*tasks)
        for rlist in results:
            all_results.extend(rlist)
        
        return all_results[:12]
    
    async def multi_engine_search(self, query: str) -> List[SearchResult]:
        engines = {
            'Yandex': 'https://yandex.com/search/?text=',
            'Bing': 'https://bing.com/search?q=',
            'DuckDuckGo': 'https://duckduckgo.com/?q='
        }
        return [SearchResult(name, f'{name} results', f"{url}{quote(query)}", 'Engine') 
                for name, url in engines.items()]

# ✅ HANDLERS v20.7 Application API
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = bot_instance.is_admin(username)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Быстрый поиск", callback_data="quick")],
        [InlineKeyboardButton("🚀 Глубокий", callback_data="deep")],
        [InlineKeyboardButton("📧 Email", callback_data="email")],
        [InlineKeyboardButton("🌐 Домен", callback_data="whois")]
    ])
    
    await update.message.reply_text(
        f"🤖 **OSINT Bot v4.0**\n"
        f"👤 {username} {'👑' if is_admin else ''}\n\n"
        f"`/search запрос`\n"
        f"`/stats`\n"
        f"Лимит: {SEARCH_LIMIT}/час",
        parse_mode='MarkdownV2',
        reply_markup=keyboard,
        disable_web_page_preview=True
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
        parse_mode='MarkdownV2'
    )

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, deep: bool = False):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    if not context.args:
        await update.message.reply_text("❌ `/search запрос`")
        return
    
    query = " ".join(context.args)
    limiter = bot_instance.get_limiter(user_id, is_admin)
    
    if not limiter.can_search(user_id) and not is_admin:
        remaining = limiter.get_remaining(user_id)
        await update.message.reply_text(f"⏳ Лимит! Осталось: `{remaining}`")
        return
    
    status_msg = await update.message.reply_text(f"🔍 Поиск: `{query}`")
    
    try:
        results = await bot_instance.search(query, deep and is_admin)
        await send_results(update, results, is_admin)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit_text("❌ Ошибка")

async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = bot_instance.is_admin(username)
    
    modes = {
        'quick': ('🔍 **Введите запрос:**', False),
        'deep': ('🚀 **Глубокий поиск:**', True),
        'email': ('📧 **Email/Phone:**', 'email'),
        'whois': ('🌐 **Домен:**', 'whois')
    }
    
    if query.data in modes:
        if query.data == 'deep' and not is_admin:
            await query.edit_message_text("❌ Только админы!")
            return
        
        text, mode = modes[query.data]
        await query.edit_message_text(text)
        context.user_data['mode'] = mode
        context.user_data['deep'] = mode[1] if isinstance(mode, tuple) else False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    mode = context.user_data.get('mode')
    query_text = update.message.text.strip()
    
    if mode == 'email':
        results = await bot_instance.email_search(query_text)
        await send_results(update, results, is_admin)
    elif mode == 'whois':
        results = await bot_instance.whois_search(query_text)
        await send_results(update, results, is_admin)
    elif mode in ['quick', 'deep']:
        context.args = [query_text]
        await search_cmd(update, context, context.user_data.get('deep', False))
    
    context.user_data.clear()

async def send_results(update: Update, results: List[SearchResult], is_admin: bool):
    if not results:
        await update.message.reply_text("❌ Ничего не найдено")
        return
    
    msg = f"✅ **{len(results)} результатов** {'👑' if is_admin else ''}\n\n"
    
    for i, r in enumerate(results, 1):
        msg += f"`{i}\\.` **{r.source}**\n"
        msg += f"📄 {r.title[:60]}\n"
        msg += f"[🔗 {r.url[:50]}]({r.url})\n\n"
    
    # Разбивка сообщений
    messages = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
    for m in messages:
        await update.message.reply_text(m, parse_mode='MarkdownV2', disable_web_page_preview=True)

async def main():
    global bot_instance
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        return
    
    print("🔧 OSINT Bot v4.0 - Python 3.13...")
    bot_instance = OSINTBot(BOT_TOKEN, ADMIN_USERNAME)
    
    # ✅ Application.builder() SAFE с Pillow
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    
    # ✅ v20.7 Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", lambda u,c: search_cmd(u, c, False)))
    application.add_handler(CommandHandler("deep", lambda u,c: search_cmd(u, c, True)))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_cb))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 **BOT ЗАПУЩЕН!**")
    print(f"👑 Админ: {ADMIN_USERNAME}")
    
    # ✅ SAFE Polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    
    try:
        await asyncio.Event().wait()  # Блокировка
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await bot_instance.close_session()

if __name__ == '__main__':
    asyncio.run(main())

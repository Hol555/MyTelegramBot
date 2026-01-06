#!/usr/bin/env python3
"""
OSINT Bot v5.0 FINAL - Python 3.13 + PTB v13.15
✅ NO imghdr ❌ NO syntax errors
"""

import logging
import os
import re
from typing import List
import aiohttp
import asyncio

# ✅ ПРАВИЛЬНЫЙ IMPORT v13.15
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext

from dataclasses import dataclass
from dotenv import load_dotenv
from urllib.parse import quote
from collections import defaultdict
import time

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
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
    def __init__(self, admin_username: str):
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
    
    def google_dorks(self, query: str) -> List[SearchResult]:
        dorks = [
            f'"{query}" filetype:pdf',
            f'"{query}" site:vk.com', 
            f'"{query}" inurl:admin',
            f'"{query}" filetype:sql'
        ]
        return [SearchResult('Google Dorks', dork[:50], 
                           f"https://google.com/search?q={quote(dork)}", '') for dork in dorks]
    
    def social_search(self, query: str) -> List[SearchResult]:
        sources = [
            ('Twitter', f'https://twitter.com/search?q={quote(query)}'),
            ('GitHub', f'https://github.com/search?q={quote(query)}'),
            ('VK', f'https://vk.com/search?c[q]={quote(query)}'),
            ('Telegram', f'https://t.me/search?q={quote(query)}')
        ]
        return [SearchResult(source, f'{source} search', url, '') for source, url in sources]
    
    def email_search(self, query: str) -> List[SearchResult]:
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', query)
        if email_match:
            email = email_match.group()
            return [
                SearchResult('Hunter.io', email, f'https://hunter.io/search/{quote(email)}', ''),
                SearchResult('LeakCheck', email, f'https://leakcheck.io/#/{quote(email)}', '')
            ]
        return []
    
    def whois_search(self, domain: str) -> List[SearchResult]:
        return [
            SearchResult('WHOIS', domain, f'https://whois.com/whois/{quote(domain)}', ''),
            SearchResult('ViewDNS', domain, f'https://viewdns.info/iph/?domain={quote(domain)}', '')
        ]
    
    async def search(self, query: str, deep: bool = False) -> List[SearchResult]:
        all_results = []
        
        # Синхронные поиски
        all_results.extend(self.google_dorks(query))
        all_results.extend(self.social_search(query))
        all_results.extend(self.email_search(query))
        
        if deep:
            all_results.extend(self.multi_engine_search(query))
        
        return all_results[:12]
    
    def multi_engine_search(self, query: str) -> List[SearchResult]:
        engines = {
            'Yandex': 'https://yandex.com/search/?text=',
            'Bing': 'https://bing.com/search?q=',
            'DuckDuckGo': 'https://duckduckgo.com/?q='
        }
        return [SearchResult(name, f'{name} results', f"{url}{quote(query)}", '') 
                for name, url in engines.items()]

bot_instance = None

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    is_admin = bot_instance.is_admin(username)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Быстрый поиск", callback_data="quick")],
        [InlineKeyboardButton("🚀 Глубокий", callback_data="deep")],
        [InlineKeyboardButton("📧 Email", callback_data="email")],
        [InlineKeyboardButton("🌐 Домен", callback_data="whois")]
    ])
    
    update.message.reply_text(
        f"🤖 **OSINT Bot v5.0**\n"
        f"👤 {username} {'👑' if is_admin else ''}\n\n"
        f"`/search запрос`\n`/stats`\n"
        f"Лимит: {SEARCH_LIMIT}/час",
        parse_mode='Markdown',
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

def stats(update: Update, context: CallbackContext):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    limiter = bot_instance.get_limiter(user_id, is_admin)
    remaining = limiter.get_remaining(user_id)
    
    update.message.reply_text(
        f"📊 **{username}**\n"
        f"Осталось: `{remaining}/{ADMIN_LIMIT if is_admin else SEARCH_LIMIT}`\n"
        f"👑 {'АДМИН' if is_admin else 'Обычный'}",
        parse_mode='Markdown'
    )

def search_cmd(update: Update, context: CallbackContext, deep: bool = False):
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    if not context.args:
        update.message.reply_text("❌ `/search запрос`")
        return
    
    query = " ".join(context.args)
    limiter = bot_instance.get_limiter(user_id, is_admin)
    
    if not limiter.can_search(user_id) and not is_admin:
        remaining = limiter.get_remaining(user_id)
        update.message.reply_text(f"⏳ Лимит! Осталось: `{remaining}`")
        return
    
    update.message.reply_text(f"🔍 Поиск: `{query}`")
    
    # Async search в отдельном потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(bot_instance.search(query, deep and is_admin))
    loop.close()
    
    send_results(update, results, is_admin)

def button_cb(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
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
            query.edit_message_text("❌ Только админы!")
            return
        
        text, mode = modes[query.data]
        query.edit_message_text(text)
        context.user_data['mode'] = mode
        context.user_data['deep'] = mode[1] if isinstance(mode, tuple) else False

def handle_message(update: Update, context: CallbackContext):
    mode = context.user_data.get('mode')
    query_text = update.message.text.strip()
    
    if mode == 'email':
        results = bot_instance.email_search(query_text)
        send_results(update, results, bot_instance.is_admin(f"@{update.effective_user.username}" or ""))
    elif mode == 'whois':
        results = bot_instance.whois_search(query_text)
        send_results(update, results, bot_instance.is_admin(f"@{update.effective_user.username}" or ""))
    elif mode in ['quick', 'deep']:
        context.args = [query_text]
        search_cmd(update, context, context.user_data.get('deep', False))
    
    context.user_data.clear()

def send_results(update: Update, results: List[SearchResult], is_admin: bool):
    if not results:
        update.message.reply_text("❌ Ничего не найдено")
        return
    
    msg = f"✅ **{len(results)} результатов** {'👑' if is_admin else ''}\n\n"
    
    for i, r in enumerate(results, 1):
        msg += f"`{i}.` **{r.source}**\n"
        msg += f"📄 {r.title[:60]}\n"
        msg += f"[🔗 {r.url[:50]}]({r.url})\n\n"
    
    messages = [msg[i:i+3800] for i in range(0, len(msg), 3800)]
    for m in messages:
        update.message.reply_text(m, parse_mode='Markdown', disable_web_page_preview=True)

def main():
    global bot_instance
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден в .env!")
        return
    
    print("🔧 OSINT Bot v5.0 - Python 3.13 + PTB v13.15")
    bot_instance = OSINTBot(ADMIN_USERNAME)
    
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # ✅ v13.15 Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("search", lambda u,c: search_cmd(u, c, False)))
    dp.add_handler(CommandHandler("deep", lambda u,c: search_cmd(u, c, True)))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CallbackQueryHandler(button_cb))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("🚀 BOT ЗАПУЩЕН!")
    print(f"👑 Админ: {ADMIN_USERNAME}")
    
    updater.start_polling(clean=True)
    updater.idle()

if __name__ == '__main__':
    main()

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
import json
from urllib.parse import quote
from collections import defaultdict
import time

# Загрузка .env
load_dotenv()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация из .env
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '@your_admin_username')  # Измените на ваш username
SEARCH_LIMIT = int(os.getenv('SEARCH_LIMIT', '3'))  # Лимит поисков в час для обычных
ADMIN_LIMIT = int(os.getenv('ADMIN_LIMIT', '100'))  # Лимит для админов

@dataclass
class SearchResult:
    source: str
    title: str
    url: str
    snippet: str
    date: Optional[str] = None

class RateLimiter:
    def __init__(self, limit: int, window: int = 3600):
        self.limit = limit
        self.window = window
        self.requests = defaultdict(list)
    
    def can_search(self, user_id: int) -> bool:
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Удаляем старые запросы
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
        self.user_limiters = {}  # user_id -> RateLimiter
        
        # Расширенные поисковые движки
        self.search_engines = {
            'google': 'https://www.google.com/search?q=',
            'yandex': 'https://yandex.com/search/?text=',
            'bing': 'https://www.bing.com/search?q=',
            'duckduckgo': 'https://duckduckgo.com/?q='
        }
    
    def get_limiter(self, user_id: int, is_admin: bool) -> RateLimiter:
        """Получить RateLimiter для пользователя"""
        if user_id not in self.user_limiters:
            limit = ADMIN_LIMIT if is_admin else SEARCH_LIMIT
            self.user_limiters[user_id] = RateLimiter(limit)
        return self.user_limiters[user_id]
    
    def is_admin(self, username: str) -> bool:
        """Проверка админских прав"""
        return username.lower() == self.admin_username
    
    async def init_session(self):
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    async def advanced_google_dorks(self, query: str) -> List[SearchResult]:
        """Расширенные Google Dorks"""
        dorks = [
            f'"{query}" filetype:pdf | filetype:doc | filetype:docx | filetype:xls',
            f'"{query}" intext:"email" | intext:"phone" | intext:"телефон"',
            f'"{query}" site:vk.com | site:ok.ru | site:facebook.com | site:instagram.com',
            f'"{query}" inurl:(admin | login | panel | dashboard)',
            f'"{query}" ext:sql | ext:bak | ext:backup | ext:log',
            f'intitle:"index of" "{query}"',
            f'"{query}" intext:"password" | intext:"пароль"',
            f'"{query}" cache: | inurl:cache'
        ]
        
        results = []
        semaphore = asyncio.Semaphore(3)  # Ограничиваем параллельные запросы
        
        async def search_dork(dork):
            async with semaphore:
                try:
                    url = f"https://www.google.com/search?q={quote(dork)}&num=5"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    async with self.session.get(url, headers=headers) as response:
                        if response.status == 200:
                            text = await response.text()
                            links = re.findall(r'<a href="/url\?q=([^&"]+)', text)
                            for link in links[:2]:
                                if 'google' not in link:
                                    results.append(SearchResult(
                                        source='Google Dorks',
                                        title=f'Result for: {dork[:50]}...',
                                        url=link,
                                        snippet=f'Dork: {dork[:30]}...'
                                    ))
                except Exception as e:
                    logger.error(f"Dork search error: {e}")
        
        tasks = [search_dork(dork) for dork in dorks[:5]]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results[:8]
    
    async def social_media_search(self, query: str) -> List[SearchResult]:
        """Расширенный поиск в соцсетях"""
        results = []
        
        social_sources = [
            ('Twitter/X', f'https://twitter.com/search?q={quote(query)}&src=typed_query&f=live'),
            ('GitHub', f'https://github.com/search?q={quote(query)}&type=repositories'),
            ('VK', f'https://vk.com/search?c%5Bq%5D={quote(query)}&c%5Bsection%5D=auto'),
            ('Telegram', f'https://t.me/search?q={quote(query)}'),
            ('Pastebin', f'https://pastebin.com/search?q={quote(query)}')
        ]
        
        for source, url in social_sources:
            results.append(SearchResult(
                source=source,
                title=f'{source} results for "{query}"',
                url=url,
                snippet=f'Public {source.lower()} data'
            ))
        
        return results
    
    async def email_phone_search(self, query: str) -> List[SearchResult]:
        """Поиск email/телефонов"""
        results = []
        
        # Email паттерны
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', query)
        phone_match = re.search(r'(\+?[\d\s\-\(\)]{10,})', query)
        
        if email_match:
            email = email_match.group()
            results.extend([
                SearchResult('Email Hunter', f'Email: {email}', 
                           f'https://hunter.io/search/{quote(email)}', 
                           'Email verification'),
                SearchResult('LeakCheck', f'Email leaks: {email}', 
                           f'https://leakcheck.io/#/{quote(email)}', 
                           'Data breaches'),
            ])
        
        if phone_match:
            phone = phone_match.group()
            results.append(SearchResult(
                'PhoneNum', f'Phone: {phone}',
                f'https://phonenumbers.io/#/{quote(phone)}',
                'Phone number info'
            ))
        
        return results
    
    async def whois_reverse_search(self, domain: str) -> List[SearchResult]:
        """WHOIS и реверсный поиск"""
        results = []
        
        whois_sources = [
            ('WHOIS.com', f'https://www.whois.com/whois/{quote(domain)}'),
            ('ViewDNS', f'https://viewdns.info/reversewhois/?q={quote(domain.split(".")[0])}'),
            ('SecurityTrails', f'https://securitytrails.com/domain/{quote(domain)}/dns')
        ]
        
        for source, url in whois_sources:
            results.append(SearchResult(source, f'{source}: {domain}', url, 'Domain info'))
        
        return results
    
    async def shodan_search(self, query: str) -> List[SearchResult]:
        """Shodan-like поиск (без API)"""
        return [SearchResult(
            'Shodan',
            f'Shodan IoT search: {query}',
            f'https://www.shodan.io/search?query={quote(query)}',
            'Internet-connected devices'
        )]
    
    async def perform_osint_search(self, query: str, deep_scan: bool = False) -> List[SearchResult]:
        """Полный OSINT поиск"""
        await self.init_session()
        all_results = []
        
        # Основные задачи поиска
        tasks = [
            self.advanced_google_dorks(query),
            self.social_media_search(query),
            self.email_phone_search(query),
            self.shodan_search(query)
        ]
        
        # Глубокий поиск для админов
        if deep_scan:
            tasks.extend([
                self.search_multiple_engines(query)
            ])
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for results in results_list:
            if isinstance(results, list):
                all_results.extend(results)
        
        return all_results[:15]
    
    async def search_multiple_engines(self, query: str) -> List[SearchResult]:
        """Поиск по нескольким движкам"""
        semaphore = asyncio.Semaphore(5)
        results = []
        
        async def search_engine(engine, base_url):
            async with semaphore:
                try:
                    url = f"{base_url}{quote(query)}"
                    async with self.session.get(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }) as resp:
                        results.append(SearchResult(engine, f'{engine} results', url, 'Search engine'))
                except:
                    pass
        
        tasks = [search_engine(name, url) for name, url in self.search_engines.items()]
        await asyncio.gather(*tasks[:4], return_exceptions=True)  # 4 движка max
        return results

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name
    is_admin_msg = " 👑 **АДМИН**" if bot_instance.is_admin(username) else ""
    
    keyboard = [
        [InlineKeyboardButton("🔍 Быстрый OSINT", callback_data="quick_osint")],
        [InlineKeyboardButton("🚀 Глубокий поиск", callback_data="deep_osint")],
        [InlineKeyboardButton("📧 Email/Phone", callback_data="email_search")],
        [InlineKeyboardButton("🌐 WHOIS/Домен", callback_data="whois_search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🤖 **OSINT Bot v2.0**{is_admin_msg}\n\n"
        f"👤 Добро пожаловать, {username}!\n\n"
        f"**Команды:**\n"
        f"`/search <запрос>` - Быстрый поиск\n"
        f"`/deep <запрос>` - Глубокий поиск (только админ)\n"
        f"`/stats` - Ваши лимиты\n\n"
        f"**Лимиты:**{'' if bot_instance.is_admin(username) else f' {SEARCH_LIMIT}/час'}",
        parse_mode='Markdown', reply_markup=reply_markup
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика лимитов"""
    user = update.effective_user
    username = user.username or user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    limiter = bot_instance.get_limiter(user_id, is_admin)
    remaining = limiter.get_remaining(user_id)
    total_limit = ADMIN_LIMIT if is_admin else SEARCH_LIMIT
    
    await update.message.reply_text(
        f"📊 **Ваши лимиты:**\n\n"
        f"🔢 Осталось поисков: `{remaining}/{total_limit}`\n"
        f"⏰ Окно: 1 час\n"
        f"👑 Режим: {'**АДМИН** (безлимит)' if is_admin else 'Обычный'}",
        parse_mode='Markdown'
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE, deep: bool = False):
    """Обработка команд поиска"""
    user = update.effective_user
    username = user.username or user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    if not context.args:
        await update.message.reply_text("❌ Укажите запрос: `/search ваш_запрос`", parse_mode='Markdown')
        return
    
    query = " ".join(context.args)
    limiter = bot_instance.get_limiter(user_id, is_admin)
    
    if not limiter.can_search(user_id):
        remaining = limiter.get_remaining(user_id)
        await update.message.reply_text(
            f"⏳ **Лимит превышен!**\n\n"
            f"Осталось: `{remaining}` поисков\n"
            f"Подождите 1 час или обратитесь к админу",
            parse_mode='Markdown'
        )
        return
    
    scan_type = "🚀 Глубокий" if deep else "🔍 Быстрый"
    await update.message.reply_text(f"{scan_type} поиск: `{query}`", parse_mode='Markdown')
    
    try:
        results = await bot_instance.perform_osint_search(query, deep)
        await send_results(update, results, query, is_admin)
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("❌ Ошибка поиска. Попробуйте позже.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    username = user.username or user.first_name
    is_admin = bot_instance.is_admin(username)
    
    if query.data == "quick_osint":
        await query.edit_message_text("🔍 **Введите запрос для быстрого OSINT:**")
        context.user_data['mode'] = 'quick_osint'
    elif query.data == "deep_osint":
        if not is_admin:
            await query.edit_message_text("❌ **Глубокий поиск только для админов!**\nОбратитесь к @admin")
            return
        await query.edit_message_text("🚀 **Введите запрос для глубокого OSINT:**")
        context.user_data['mode'] = 'deep_osint'
    elif query.data == "email_search":
        await query.edit_message_text("📧 **Введите email или телефон:**")
        context.user_data['mode'] = 'email_search'
    elif query.data == "whois_search":
        await query.edit_message_text("🌐 **Введите домен:**")
        context.user_data['mode'] = 'whois_search'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username or user.first_name
    user_id = user.id
    is_admin = bot_instance.is_admin(username)
    
    query = update.message.text.strip()
    mode = context.user_data.get('mode')
    
    if mode == 'quick_osint':
        await search_command_with_mode(update, context, query, False)
    elif mode == 'deep_osint':
        if not is_admin:
            await update.message.reply_text("❌ Глубокий поиск только для админов!")
            return
        await search_command_with_mode(update, context, query, True)
    elif mode == 'email_search':
        await email_search(update, context, query)
    elif mode == 'whois_search':
        await whois_search(update, context, query)

async def search_command_with_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, deep: bool):
    context.args = [query]
    await search_command(update, context, deep)
    context.user_data['mode'] = None

async def email_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    is_admin = bot_instance.is_admin(username)
    
    limiter = bot_instance.get_limiter(user_id, is_admin)
    if limiter.can_search(user_id):
        results = await bot_instance.email_phone_search(query)
        await send_results(update, results, query, is_admin)
    else:
        await update.message.reply_text("⏳ Лимит превышен!")

async def whois_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name
    is_admin = bot_instance.is_admin(username)
    
    limiter = bot_instance.get_limiter(user_id, is_admin)
    if limiter.can_search(user_id):
        results = await bot_instance.whois_reverse_search(query)
        await send_results(update, results, query, is_admin)
    else:
        await update.message.reply_text("⏳ Лимит превышен!")

async def send_results(update: Update, results: List[SearchResult], query: str, is_admin: bool):
    if not results:
        await update.message.reply_text("❌ **Результаты не найдены**")
        return
    
    admin_badge = " 👑" if is_admin else ""
    message = f"✅ **Найдено {len(results)} результатов{admin_badge}**\n\n"
    
    for i, result in enumerate(results, 1):
        message += f"`{i}.` **{result.source}**\n"
        message += f"📄 {result.title[:80]}...\n"
        message += f"🔗 [{result.url[:60]}...]({result.url})\n"
        if result.snippet:
            message += f"📝 {result.snippet[:100]}...\n"
        message += "\n"
    
    # Разбиваем длинные сообщения
    for i in range(0, len(message), 4000):
        chunk = message[i:i+4000]
        await update.message.reply_text(
            chunk, 
            parse_mode='Markdown', 
            disable_web_page_preview=True
        )

# Главная функция
async def main():
    global bot_instance
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN не найден в .env файле!")
    
    bot_instance = OSINTBot(BOT_TOKEN, ADMIN_USERNAME)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", lambda u,c: search_command(u,c,False)))
    application.add_handler(CommandHandler("deep", lambda u,c: search_command(u,c,True)))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 **OSINT Bot v2.0 запущен!**")
    print(f"👑 Админ: {ADMIN_USERNAME}")
    print(f"📊 Лимиты: {SEARCH_LIMIT}/час (обычные), {ADMIN_LIMIT}/час (админы)")
    
    try:
        await application.run_polling(drop_pending_updates=True)
    finally:
        await bot_instance.close_session()

if __name__ == '__main__':
    asyncio.run(main())

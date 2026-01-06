# Используем официальный Python 3.12 slim образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей и устанавливаем пакеты
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта в контейнер
COPY . .

# Запускаем бота (замени my_telegram_bot.py на имя твоего файла)
CMD ["python", "my_telegram_bot.py"]

import logging
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler


# --- ХАК ДЛЯ RENDER (чтобы он думал, что мы сайт) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")


def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()


threading.Thread(target=run_dummy_server, daemon=True).start()
# --- КОНЕЦ ХАКА ---

# Робот сам возьмет токен из скрытого сейфа Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ВАЖНО: Укажи тут ссылку на свой сайт на GitHub Pages!
WEBAPP_URL = "https://annakovalevaas.github.io/summer-grind-app/"

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Сюда будем сохранять ID пользователей для рассылки напоминаний
USERS_TO_NOTIFY = set()


# --- КОМАНДА /START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Запоминаем пользователя, чтобы бот мог присылать ему рассылку
    USERS_TO_NOTIFY.add(message.from_user.id)

    # Создаем кнопку под сообщением для открытия Летнего Дневника
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть Летний Дневник ☀️", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )
    await message.answer(
        "Привет! Я твой бот для летней подготовки. Нажми на кнопку ниже, чтобы открыть приложение:",
        reply_markup=markup
    )


# --- ФУНКЦИЯ ПРОВЕРКИ ЭССЕ ---
@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    data = json.loads(message.web_app_data.data)

    if data.get('action') == 'check_essay':
        essay_text = data.get('text')
        wait_msg = await message.answer("⏳ Анализирую эссе с помощью Gemini...")

        try:
            prompt = f"Ты эксперт ЕГЭ по английскому. Проверь эссе, укажи на лексические, грамматические и стилистические ошибки, оцени по критериям ФИПИ и дай советы по улучшению. Текст эссе: {essay_text}"
            response = model.generate_content(prompt)
            await wait_msg.edit_text(response.text)
        except Exception as e:
            await wait_msg.edit_text(f"Ошибка при проверке: {e}")


# --- НАПОМИНАНИЯ (SCHEDULER) ---
async def send_daily_reminders():
    for user_id in USERS_TO_NOTIFY:
        try:
            await bot.send_message(user_id,
                                   "🔥 Пора ботать! Не забудь зайти в летний дневник и отметить прогресс по профильной математике и информатике!")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


# --- ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА (ВЕЧНАЯ БАТАРЕЙКА) ---
async def main():
    # Настраиваем расписание
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Напоминание каждый день в 10:00 утра (можешь поменять время)
    scheduler.add_job(send_daily_reminders, trigger='cron', hour=10, minute=0)
    scheduler.start()

    # Запускаем бота, чтобы он бесконечно ждал сообщений
    print("Бот успешно запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    # Именно эта строчка запускает всё приложение и не дает ему отключиться
    asyncio.run(main())
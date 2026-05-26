import logging
import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
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

# Считываем токены безопасности из скрытых настроек сервера
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Ссылка на твой развернутый GitHub Pages сайт
WEBAPP_URL = "https://annakovalevaas.github.io/summer-grind-app/"

# Настройка нейросети Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище ID пользователей для ежедневной рассылки
USERS_TO_NOTIFY = set()


# --- КОМАНДА /START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    USERS_TO_NOTIFY.add(message.from_user.id)

    # Создаем правильную REPLY клавиатуру внизу экрана телефона
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Открыть Летний Дневник ☀️", web_app=WebAppInfo(url=WEBAPP_URL))]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "Привет! Я твой бот для летней подготовки.\n\n"
        "✨ Доступные команды ИИ:\n"
        "• /words — Сгенерировать новые 5 английских слов дня\n"
        "• /lit [название] — Найти автора, саммари и темы для аргументов сочинения\n\n"
        "Нажми на кнопку ниже, чтобы открыть приложение:",
        reply_markup=markup
    )


# --- ИИ ПРОВЕРКА ЭССЕ ИЗ WEB APP ---
@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    data = json.loads(message.web_app_data.data)

    if data.get('action') == 'check_essay':
        essay_text = data.get('text')
        wait_msg = await message.answer("⏳ Передаю текст нейросети Gemini. Анализирую эссе...")

        try:
            prompt = (
                f"Ты эксперт ЕГЭ по английскому языку. Тщательно проверь эссе, "
                f"укажи на лексические, грамматические и стилистические ошибки, "
                f"оцени по официальным критериям ФИПИ и дай развернутые советы по улучшению.\n"
                f"Текст эссе:\n{essay_text}"
            )
            response = model.generate_content(prompt)
            await wait_msg.edit_text(response.text)
        except Exception as e:
            await wait_msg.edit_text(f"Произошла ошибка ИИ: {e}")


# --- ИИ ГЕНЕРАТОР АРГУМЕНТОВ ЛИТЕРАТУРЫ (/lit) ---
@dp.message(Command("lit"))
async def cmd_lit(message: types.Message):
    book_query = message.text.replace("/lit", "").strip()
    if not book_query:
        await message.answer("Пожалуйста, укажи книгу. Пример: /lit Капитанская дочка")
        return

    wait_msg = await message.answer("⏳ ИИ Gemini ищет автора, пишет краткое содержание и подбирает темы...")
    try:
        prompt = (
            f"Ты эксперт ЕГЭ по литературе и русскому языку. Пользователь написал название книги: '{book_query}'. "
            f"Определи автора и выведи информацию строго в три строчки (для вставки в таблицу аргументов):\n"
            f"1. Правильное форматирование: И.О. Фамилия автора «Название произведения»\n"
            f"2. Краткое саммари сюжета (буквально 2 емких предложения)\n"
            f"3. Темы для аргументов (через запятую, например: Честь, Предательство, Долг)"
        )
        response = model.generate_content(prompt)
        await wait_msg.edit_text(f"📖 Готовые данные для Летнего Дневника:\n\n{response.text}")
    except Exception as e:
        await wait_msg.edit_text(f"Не удалось получить ответ от ИИ: {e}")


# --- ИИ ГЕНЕРАТОР АНГЛИЙСКИХ СЛОВ (/words) ---
@dp.message(Command("words"))
async def cmd_words(message: types.Message):
    wait_msg = await message.answer("⏳ Нейросеть генерирует новую порцию продвинутой лексики...")
    try:
        prompt = (
            "Сгенерируй 5 полезных английских слов уровня B2-C1 с переводом на русский для пополнения словарного запаса. "
            "Выведи их списком, кратко и понятно."
        )
        response = model.generate_content(prompt)
        await wait_msg.edit_text(f"🇬🇧 Новые слова дня от Gemini:\n\n{response.text}")
    except Exception as e:
        await wait_msg.edit_text(f"Ошибка генерации слов: {e}")


# --- ЕЖЕДНЕВНЫЕ НАПОМИНАНИЯ (УВЕДОМЛЕНИЯ) ---
async def send_daily_reminders():
    for user_id in USERS_TO_NOTIFY:
        try:
            await bot.send_message(
                user_id,
                "🔥 Время ботать! Не забудь зайти в летний дневник, проверить эссе, "
                "повторить лексику и отметить сегодняшний прогресс по профильной математике!"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление {user_id}: {e}")


# --- ГЛАВНЫЙ ЦИКЛ ЗАПУСКА ---
async def main():
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    # Рассылка напоминаний каждый день ровно в 10:00 утра
    scheduler.add_job(send_daily_reminders, trigger='cron', hour=10, minute=0)
    scheduler.start()

    print("Робот-помощник успешно запущен!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
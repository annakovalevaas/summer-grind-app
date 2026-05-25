import logging
import asyncio
import json
import google.generativeai as genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
import os

# Робот сам возьмет токен из скрытого сейфа Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ... (оставь свой код для scheduler и USERS_TO_NOTIFY) ...

# --- ФУНКЦИЯ ПРОВЕРКИ ---
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
            await wait_msg.edit_text(f"Ошибка: {e}")

# ... (остальной код main, start и т.д.)
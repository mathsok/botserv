import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

# Вставьте сюда ваш токен
API_TOKEN = 'ВАШ_ТОКЕН_ЗДЕСЬ'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Обработка команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Бот запущен на сервере! Отправь мне что-нибудь, и я повторю.")

# Обработка любых текстовых сообщений (Эхо)
@dp.message()
async def echo_handler(message: types.Message):
    try:
        # Просто отправляем тот же текст обратно
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        # На случай, если прислали не текст (например, стикер)
        await message.answer("Я умею повторять только текст!")

async def main():
    print("Бот вышел на связь...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import openai
import asyncpg
import contextlib

from environs import Env
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ContentType, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from core.middlewares.dbmiddleware import DbSession
from core.utils.dbconnect import Request
from core.handlers import distribute
from core.utils.distribute_state import Steps
from core.utils.distribute_list import DistributeList


env = Env()
env.read_env()
bot_token = env('BOT_TOKEN')
admin_id = env.int('ADMIN_ID')
gpt_id = env.list('GPT_ID', subcast=int)
api_key = env('API_KEY')


async def get_start(message: Message, request: Request):
    await message.answer(f'Привет, {message.from_user.first_name}. Буду скидывать тебе расписание и важные объявления.')
    if message.from_user.id == message.chat.id:
        await request.add_data(message.from_user.id, message.from_user.first_name)
    else:
        await request.add_data(message.chat.id, 'группа')



async def create_pool():
    return await asyncpg.create_pool(user='postgres', password='22848555',
                                     database='school_9', host='127.0.0.1',
                                     port=5432, command_timeout=60)


async def get_chat_gpt(message: Message):
    user_text = message.text
    msg_for_user = await openai_message(msg_for_openai=user_text)
    await message.answer(text=msg_for_user)


async def openai_message(msg_for_openai: str):
    openai.api_key = api_key
    model = 'gpt-3.5-turbo'
    data_openai = [{'role': 'user', 'content': msg_for_openai}]
    responce = openai.ChatCompletion.create(model=model, messages=data_openai)
    return responce.choices[0].message.content


async def start_bot(bot: Bot):
    await bot.send_message(admin_id, text="Бот запущен!")


async def stop_bot(bot: Bot):
    await bot.send_message(admin_id, text="Бот выключен!")


async def start():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] -  %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
    )
    bot = Bot(token=bot_token, parse_mode='HTML')
    pool_connect = await create_pool()

    dp = Dispatcher()

    dp.update.middleware.register(DbSession(pool_connect))
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    dp.message.register(get_start, CommandStart())

    dp.message.register(distribute.get_sender, Command(commands='f'), F.chat.id == (admin_id))
    dp.message.register(distribute.get_message, Steps.get_message)
    dp.callback_query.register(distribute.sender_decide, F.data.in_(['confirm_sender', 'cancel_sender']))
    dp.callback_query.register(distribute.q_button, Steps.q_button)
    dp.message.register(distribute.get_text_button, Steps.get_text_button)
    dp.message.register(distribute.get_url_button, Steps.get_url_button)
    distribute_list = DistributeList(bot, pool_connect)
    dp.message.register(get_chat_gpt, F.text, F.chat.id.in_(gpt_id))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), senderlist=distribute_list)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(start())

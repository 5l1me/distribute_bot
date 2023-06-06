from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from aiogram.filters import CommandObject
from aiogram.fsm.context import FSMContext

from core.utils.distribute_state import Steps
from core.keyboards.inline import get_confirm_button_keyboard
from core.middlewares.dbmiddleware import Request
from core.utils.distribute_list import DistributeList


async def get_sender(message: Message, command: CommandObject, state: FSMContext):
    if not command.args:
        await message.answer(f'Для создания рассылки введите команду /f и имя рассылки')
        return
    await message.answer(f'Приступаем к созданию расслки - {command.args}\r\n\r\n'
                         'Отправь сообщение, которое будем рассылать')

    await state.update_data(name_camp=command.args)
    await state.set_state(Steps.get_message)


async def get_message(message: Message, state: FSMContext):
    await message.answer(f'Хорошо\r\n'
                         f'Добавим кнопку?', reply_markup=get_confirm_button_keyboard())
    await state.update_data(message_id=message.message_id, chat_id=message.from_user.id)
    await state.set_state(Steps.q_button)


async def q_button(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.data == 'add_button':
        await call.message.answer(f'Отправь название кнопки.', reply_markup=None)
        await state.set_state(Steps.get_text_button)
    elif call.data == 'no_button':
        await state.set_state(Steps.get_url_button)
        await call.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        message_id = int(data.get('message_id'))
        chat_id = int(data.get('chat_id'))
        await confirm(call.message, bot, message_id, chat_id)

    await call.answer()


async def get_text_button(message: Message, state: FSMContext):
    await state.update_data(text_button=message.text)
    await message.answer(f'отправь ссылку для неё')
    await state.set_state(Steps.get_url_button)


async def get_url_button(message: Message, bot: Bot, state: FSMContext):
    await state.update_data(url_button=message.text)
    added_keyboards = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=(await state.get_data()).get('text_button'),
                url=f'{message.text}'
            )
        ]
    ])
    data = await state.get_data()
    message_id = int(data.get('message_id'))
    chat_id = int(data.get('chat_id'))
    await confirm(message, bot, message_id, chat_id, added_keyboards)
    await state.set_state(Steps.sender_deside)


async def confirm(message: Message, bot: Bot, message_id: int, chat_id: int, reply_markup: InlineKeyboardMarkup = None):
    await bot.copy_message(chat_id, chat_id, message_id, reply_markup=reply_markup)
    await message.answer(f'это сообщение будет отправлено. Подтвердите.',
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [
                                 InlineKeyboardButton(
                                     text='Подтвердить',
                                     callback_data='confirm_sender'
                                 )
                             ],
                             [
                                 InlineKeyboardButton(
                                     text='Отменить',
                                     callback_data='cancel_sender'
                                 )
                             ]
                         ]))


async def sender_decide(call: CallbackQuery, bot: Bot, state: FSMContext, request: Request, senderlist: DistributeList):
    data = await state.get_data()
    message_id = data.get('message_id')
    chat_id = data.get('chat_id')
    text_button = data.get('text_button')
    url_button = data.get('url_button')
    name_camp = data.get('name_camp')

    if call.data == 'confirm_sender':
        await call.message.edit_text(f'Начинаю рассылку', reply_markup=None)

        if not await request.check_table(name_camp):
            await request.create_table(name_camp)
        count = await senderlist.broadcaster(name_camp, chat_id, message_id, text_button, url_button)
        await call.message.answer(f'Успешно разослали сообщение [{count}] пользователям')
        await request.delete_table(name_camp)


    elif call.data == 'cancel_sender':
        await call.message.edit_text('Отменил рассылку', reply_markup=None)

    await state.clear()


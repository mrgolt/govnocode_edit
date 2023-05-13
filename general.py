import asyncio
import logging
import os
import threading
import time

import schedule as schedule
from aiogram import types
from pymongo import MongoClient
from aiogram.utils.exceptions import BadRequest, MessageNotModified, ChatNotFound, BotKicked
from aiogram.utils import exceptions
from aiogram.dispatcher import FSMContext, Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from handlers import admin_keyboards, manager_keyboards, user_keyboards, test_keyboard
from controllers.db_controller import user_db, test_db, manager_db, admin_db
from controllers.capcha_controller.captcha import Captcha
import uidController
import config
import re
from config import conditions_event, conditions_msg
import randomizer
from controllers import excel_contoller
import texts
import time
from aiogram import Bot
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from configure import cfg
from language.translator import LocalizedTranslator

# Инициализируем бота и диспетчер
storage = MemoryStorage()
bot = Bot(token=cfg['token'])
dp = Dispatcher(bot, storage=storage)

hello = '''
Добро пожаловать в наш конкурсный бот! Я готов помочь вам участвовать в конкурсах и достичь новых высот. Давайте начнем и победим вместе!
По причине того, что ты новый участник, ты должен будет пройти проверку на бота.
Отгадай, пожалуйста, капчу...
'''

data = {}
data_id_random_event = {}
data_conditions = {}


class Email(StatesGroup):
    waiting_for_email = State()


class AddData(StatesGroup):
    waiting_for_add_data = State()


class Captcha_state(StatesGroup):
    send_captcha = State()
    waiting_for_captcha = State()


class MyEvents(StatesGroup):
    my_events = State()


class ControlEvents(StatesGroup):
    control_events = State()


class ManagerStatistic(StatesGroup):
    manager_statistic = State()


class SecurityState(StatesGroup):
    securuty = State()


class SubscriptionState(StatesGroup):
    subscription = State()


class EventState(StatesGroup):
    waiting_for_conditions = State()
    waiting_for_chanell_url = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    waiting_for_add_condition = State()
    waiting_for_winners_count = State()
    waiting_for_time_interval = State()
    waiting_for_duration = State()
    waiting_for_publish_text = State()
    waiting_for_publish = State()
    waiting_for_edit_field = State()


class RerollOrPublishState(StatesGroup):
    waiting_for_choice_action = State()
    waiting_for_reroll = State()


class RerollNumberState(StatesGroup):
    waiting_for_number_winners = State()


class addBotToChannelState(StatesGroup):
    waiting_for_id_channel = State()


async def on_startup(x):
    # Регистрируем задачу в расписании
    schedule.every(10).seconds.do(check_for_new_contests)

    # Бесконечный цикл, в котором выполняется проверка расписания и обработка задач
    while True:
        schedule.run_pending()
        time.sleep(1)


async def admin(message: types.Message):
    if message.chat.id in config.admins:
        try:
            test_db.changeRole(str(message.chat.id), 'admin')
            await message.answer(translate.get(key='no_active_contests'), reply_markup=admin_keyboards.a_start_kb)
        except Exception as ex:
            await message.answer("Ошибка: " + str(ex))


async def user(message: types.Message):
    try:
        test_db.changeRole(str(message.chat.id), 'user')
        await message.answer("Приветствую, Участник!")
    except Exception as ex:
        await message.answer("Ошибка: " + str(ex))


async def manager(message: types.Message):
    try:
        test_db.changeRole(str(message.chat.id), 'manager')
        await message.answer("Приветствую, Организатор!", reply_markup=manager_keyboards.manager_start_kb)
    except Exception as ex:
        await message.answer("Ошибка: " + str(ex))


async def start(message: types.Message):
    role = None
    try:
        role = test_db.getRole(str(message.chat.id))['role']
    except:
        pass
    if role == "user" or role == None:
        try:
            chat_id = str(message.chat.id)
            full_name = message.chat.full_name
            username = message.chat.username

            user_data = {'chat_id': chat_id, 'full_name': full_name, 'username': username}

            payload = message.text.split(' ')
            # нашёл бота в поиске
            if len(payload) == 1:
                result = await user_db.checkUser(chat_id)
                if not result:
                    user_data['role'] = 'manager'
                    await user_db.addUser(user_data)
                    await message.answer(texts.became_a_manager, reply_markup=manager_keyboards.manager_start_kb)
                else:
                    await message.answer('Вы уже организатор', reply_markup=manager_keyboards.manager_start_kb)
            # присоединился по ссылке
            else:
                referral_id = payload[1].split(config.separator)[0]
                event_id = payload[1].split(config.separator)[1]
                result = await user_db.checkActivity(chat_id, event_id)
                if result:
                    await message.answer(text='Вы уже являетесь участником этого конкурса!',
                                         reply_markup=types.ReplyKeyboardRemove())
                else:
                    user_data['event_data'] = [{event_id: ""}]
                    user_data['role'] = 'user'

                    # приглашающий не огранизатор
                    if (not await user_db.isManager(referral_id)):
                        user_data['event_data'][0][event_id] = referral_id

                    result = await user_db.checkEvent(chat_id, event_id)
                    if result:
                        await user_db.updateEvent(chat_id, event_id, user_data['event_data'])
                        await showEvent(chat_id, event_id)
                    else:
                        # есть ли пользовать в БД
                        result = await user_db.checkUser(chat_id)
                        # пользователь впервые в боте
                        if (not result):
                            # не является пользователем бота
                            await user_db.addUser(user_data)
                            await message.answer(hello)
                            try:
                                data[chat_id].update({'event_id': event_id})
                            except:
                                data[chat_id] = {'event_id': event_id}
                            await sendCaptcha(message.chat.id)
                        else:
                            # уже является пользователем бота
                            await user_db.updateEventData(chat_id, user_data['event_data'])
                            # вываливаем конкурс
                            await showEvent(chat_id, event_id)

        except Exception as e:
            print(e)
    elif role == "manager":
        try:
            await message.answer(texts.became_a_manager, reply_markup=manager_keyboards.manager_start_kb)
        except Exception as e:
            print(e)
    else:
        try:
            await message.answer('Приветствую, Администратор!', reply_markup=admin_keyboards.a_start_kb)
        except Exception as e:
            print(e)


async def keyboard_handler(message: types.Message):
    role = test_db.getRole(str(message.chat.id))['role']
    if role == "user":
        try:
            if message.text == "Посты с конкурсами":
                id_user = message.chat.id
                events = user_db.getMyEvents(str(id_user))
                if len(events) != 0:
                    for my_event_id in list(events):
                        event = await user_db.getEvent(my_event_id)
                        id_event = event['_id']
                        title = event['title']
                        description = event['description']
                        photo = event['photo']
                        conditions = event['conditions']
                        additional_condition = event['additional_condition']
                        additional_condition_text = ''
                        if additional_condition != '':
                            additional_condition_text = f"<b>Доп.условие:</b> {additional_condition}\n"
                        winners_count = int(event['winners_count'])
                        chanell_url = event['chanell_url']
                        date_start = event['date_start']
                        date_end = event['date_end']
                        duration = daysBetweenTwoDates(date_start, date_end)

                        chanell_btn = InlineKeyboardButton(f"Подписаться на {chanell_url.split('t.me/')[1]}❌",
                                                           callback_data="channel", url=chanell_url)
                        update_btn = InlineKeyboardButton(f"Проверить подписку и рефералов", callback_data="update")
                        keyboard = InlineKeyboardMarkup().add(chanell_btn).add(update_btn)

                        await bot.send_photo(message.chat.id, photo,
                                             caption=f'<i>{id_event}</i>\n\n<b>{title.upper()}</b>\n<b>Описание:</b> <i>{description}</i>\n<b>Условия:</b> {conditions}\n{additional_condition_text}<b>Кол-во победителей:</b> {winners_count}чел.\n<b>Осталось:</b> {duration}д.',
                                             parse_mode="HTML", reply_markup=keyboard)
                else:
                    await message.answer(f"Активных конкурсов нет")
            elif message.text == "Сменить роль":
                await message.answer("Выберите роль:", reply_markup=test_keyboard.user_kb)
            elif message.text == "Организатор":
                test_db.changeRole(str(message.chat.id), 'manager')
                await message.answer("Приветствую, Организатор!", reply_markup=manager_keyboards.manager_start_kb)
        except Exception as e:
            print(e)
    elif role == "manager":
        try:
            if message.text == "/start":
                try:
                    await message.answer(texts.became_a_manager, reply_markup=manager_keyboards.manager_start_kb)
                except Exception as e:
                    print(e)
            # elif message.text == "Выбрать язык":
            #    await message.answer("Выберите свой язык", reply_markup=manager_keyboards.language)
            #    msg = await message.answer("123", reply_markup=manager_keyboards.back)
            #    await bot.delete_message(message.chat.id, msg.message_id)
            elif message.text == "Раздел конкурсов":
                await message.answer(texts.event_filder, reply_markup=manager_keyboards.manager_start_kb)
            elif message.text == "Действующие":
                await showActivityEvents(message)
            elif message.text == "Завершенные":
                await showFinishedEvents(message)
            elif message.text == "Требующие подведения":
                await showNeedRandomEvents(message)
            elif message.text == "Создать новый конкурс":
                channels = manager_db.getChannels(manager_id=str(message.chat.id))
                if len(channels) > 0:
                    await EventState.waiting_for_conditions.set()
                    await message.answer(texts.cond_event,
                                         reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
                else:
                    await message.answer("У вас нет прикреплённых сообществ",
                                         reply_markup=manager_keyboards.manager_start_kb)
            elif message.text == "Панель управления":
                await message.answer(texts.todo, reply_markup=manager_keyboards.manager_control_panel)
                await ControlEvents.control_events.set()
            elif message.text == "Главное меню":
                await message.answer(texts.main_menu, reply_markup=manager_keyboards.manager_start_kb)
            elif message.text == "FAQ":
                with open('FAQ.docx', 'rb') as pdf_file:
                    # отправляем файл docx
                    await message.answer_document(document=pdf_file, caption=message.text)
            elif message.text == "Добавить канал":
                await message.answer(texts.get_access_six_month, reply_markup=manager_keyboards.get_access_six_month)
                await addBotToChannelState.waiting_for_id_channel.set()
            # elif message.text == "Подписка на бота":
            #    await message.answer(texts.subscription, reply_markup=manager_keyboards.manager_subscription_kb)
            elif message.text == "Написать в поддержку":
                await message.answer(texts.support_folder, parse_mode="HTML", disable_web_page_preview=True,
                                     reply_markup=manager_keyboards.support_kb)
            elif message.text == "Сменить роль":
                await message.answer("Выберите роль:", reply_markup=test_keyboard.manager_kb)
            elif message.text == "Назад":
                await message.answer(texts.main_menu, reply_markup=manager_keyboards.manager_start_kb)
            elif message.text == "Участник":
                test_db.changeRole(str(message.chat.id), 'user')
                await message.answer(texts.from_admin_to_user, reply_markup=types.ReplyKeyboardRemove())
        except Exception as e:
            print(e)
    else:
        try:
            if message.text == "Добавить пользователя":
                await message.answer("Отработка кнопки 'Добавить пользователя'", reply_markup=admin_keyboards.back)
            elif message.text == "Данные участников":
                await message.answer("Отработка кнопки 'Данные участников'",
                                     reply_markup=admin_keyboards.a_download_data_user_kb)
            elif message.text == "Языковой сбор":
                await message.answer("Отработка кнопки 'Языковой сбор'", reply_markup=admin_keyboards.language_data)
            elif message.text == "По каналам":
                await message.answer("Отработка кнопки 'По каналам'",
                                     reply_markup=admin_keyboards.a_download_data_user_kb)
            elif message.text == "Создать рассылку":
                await message.answer("Отработка кнопки 'Создать рассылку'", reply_markup=admin_keyboards.a_mailing_kb)
            elif message.text == "По языковой группе":
                await message.answer("Отработка кнопки 'По языковой группе'",
                                     reply_markup=admin_keyboards.language_mailing)
            elif message.text == "В канал":
                await message.answer("Отработка кнопки 'В канал'", reply_markup=admin_keyboards.a_mailing_kb)
            elif message.text == "Вcем":
                await message.answer("Отработка кнопки 'Забрать права'", reply_markup=admin_keyboards.a_mailing_kb)
            elif message.text == "Забрать права":
                await message.answer("Отработка кнопки 'Забрать права'", reply_markup=admin_keyboards.back)
            elif message.text == "Список каналов":
                await message.answer("Отработка кнопки 'Список каналов'",
                                     reply_markup=admin_keyboards.a_channel_list_kb)
            elif message.text == "Статистика":
                await sendAdminExcel(message=message, admin_id=str(message.chat.id),
                                     excel_path=f'{str(message.chat.id)}.xlsx')
            elif message.text == "Сменить роль":
                await message.answer("Выберите роль:", reply_markup=test_keyboard.admin_kb)
            elif message.text == "Участник":
                test_db.changeRole(str(message.chat.id), 'user')
                await message.answer("Приветствую, Участник!", reply_markup=types.ReplyKeyboardRemove())
            elif message.text == "Организатор":
                test_db.changeRole(str(message.chat.id), 'manager')
                await message.answer("Приветствую, Организатор!", reply_markup=manager_keyboards.manager_start_kb)
            elif message.text == "Назад":
                await message.answer("Обработка кнопки 'Назад'", reply_markup=admin_keyboards.a_start_kb)
        except Exception as e:
            print(e)


async def inline_help_buttons_handler(call: types.CallbackQuery, state: FSMContext):
    role = test_db.getRole(str(call.message.chat.id))['role']
    if role == "user":
        if call.data == "update":
            id_chat = str(call.message.chat.id)

            id_event = call.message.caption.split('ID конкурса: ')[1].split('\n')[0]

            event = await user_db.getEvent(id_event)
            channel_url = event['chanell_url']
            channel_format = f'@{channel_url.split("t.me/")[1]}'
            channel_name = channel_url.split('t.me/')[1]

            # проверка подписки на канал
            received_message = await is_subscribed(int(id_chat), channel_format)
            # есть подписка на канал в посте конкурса
            if received_message == config.subscribed_status[0]:
                # меняем inline button с подпиской
                await changePost(call.message, channel_name, True, id_event)

                hasActivity = await user_db.checkActivity(id_chat, id_event)
                # если пользователь уже участник конкурса
                if (hasActivity):
                    await bot.answer_callback_query(call.id, text="Вы уже являетесь участником")
                    await changePost(call.message, channel_name, True, id_event)
                else:
                    user = await user_db.getUser(id_chat)
                    conditions = ''
                    add_cond = ''
                    if 'Дополнительно' in call.message.caption:
                        add_cond = call.message.caption.split('Дополнительно:\n☑️ ')[1].split('\n')[0]
                        conditions = call.message.caption.split('Условия для участия:\n')[1].split('\nДополнительно:')[
                            0]
                    else:
                        conditions = call.message.caption.split('Условия для участия:\n')[1].split('\n\n\n:')[0]

                    data_conditions[str(call.message.chat.id)] = []
                    data_conditions[str(call.message.chat.id)].append({'conditions': conditions})
                    data_conditions[str(call.message.chat.id)].append({'channel_name': channel_name})
                    data_conditions[str(call.message.chat.id)].append({'id_event': id_event})
                    data_conditions[str(call.message.chat.id)].append({'add_cond': add_cond})
                    data_conditions[str(call.message.chat.id)].append({'phone': ''})
                    data_conditions[str(call.message.chat.id)].append({'email': ''})
                    data_conditions[str(call.message.chat.id)].append({'user_add_cond': ''})

                    result = await checkCondition(conditions, id_chat)
                    await foo(call.message, result)

            elif received_message == config.subscribed_status[1]:
                # меняем inline button с подпиской
                await changePost(call.message, channel_name, False)

        elif call.data == "channel":
            id_event = call.message.caption.split('\n')[0]

            event = await user_db.getEvent(id_event)
            channel_url = event['chanell_url']
            channel_format = f'@{channel_url.split("t.me/")[1]}'
            channel_name = channel_url.split('t.me/')[1]

            channel = f"https://t.me/{channel_url}"
            await bot.send_message(chat_id=call.message.chat.id, text=channel)
    elif role == "manager":
        if call.data == "language_back":
            await call.message.delete()
            await call.message.answer("Добро пожаловать в главное меню",
                                      reply_markup=manager_keyboards.manager_start_kb)
        elif call.data == "manager_rus":
            await call.message.delete()
            await call.message.answer("Смена языка на RUS", reply_markup=manager_keyboards.manager_start_kb)
        elif call.data == "manager_eng":
            await call.message.delete()
            await call.message.answer("Смена языка на ENG", reply_markup=manager_keyboards.manager_start_kb)
        elif call.data == "manager_hindi":
            await call.message.delete()
            await call.message.answer("Смена языка на Хинди", reply_markup=manager_keyboards.manager_start_kb)
        elif call.data == "manager_china":
            await call.message.delete()
            await call.message.answer("Смена языка на Китайский", reply_markup=manager_keyboards.manager_start_kb)
        elif call.data == "random_back":
            await call.message.answer(texts.my_events_control, reply_markup=manager_keyboards.manager_control_panel)
            await ControlEvents.control_events.set()
        elif call.data == "random":
            id_event = call.message.caption.split('ID конкурса: ')[1].split('\n')[0]
            event = await manager_db.getEvent(id_event)
            if event:
                if event['status'] != config.event_statuses[1]:
                    await call.message.answer('Действие выполнить невозможно!',
                                              reply_markup=manager_keyboards.manager_my_events)
                else:
                    id_event = event['_id']
                    id_manager = int(event['id_manager'])
                    caption_event = event['title']
                    publish_text = event['publish_text']
                    photo = event['photo']
                    winners_count = event['winners_count']
                    additional_condition = ''
                    try:
                        additional_condition = event['additional_condition']
                    except Exception:
                        pass

                    pre_winners = await manager_db.getWinners(id_event=id_event)
                    winners_id = randomizer.getDataWinners(winners_count, pre_winners)
                    await manager_db.updateEvent(id_event, {'winners': winners_id})
                    winners_print = ""
                    for winner_id in winners_id:
                        user = await user_db.getUser(winner_id)
                        username = user['username']
                        if username != None:
                            if (additional_condition != ''):
                                activity = await manager_db.getActivity(user['chat_id'], id_event)
                                additional_condition_answer = activity[additional_condition]
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                            else:
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                        else:
                            if (additional_condition != ''):
                                activity = await manager_db.getActivity(user['chat_id'], id_event)
                                additional_condition_answer = activity[additional_condition]
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                            else:
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                    publish_text = f'''
<b>Предварительные итоги конкурса</b>
<b>{caption_event}</b>
<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}
'''
                    global data_id_random_event
                    data_id_random_event[str(call.message.chat.id)] = id_event
                    await bot.send_message(id_manager, text=publish_text, parse_mode="HTML",
                                           disable_web_page_preview=True)
                    await bot.send_message(id_manager, text=texts.publish_or_reroll_event,
                                           reply_markup=manager_keyboards.publish_or_reroll_kb)
                    await RerollOrPublishState.waiting_for_choice_action.set()

        elif call.data == "copy_link":
            id_event = call.message.caption.split('ID конкурса: ')[1].split('\n')[0]
            event = await manager_db.getEvent(id_event)
            if event['status'] != config.event_statuses[0]:
                await call.message.answer('Время на участие истекло! Действие выполнить невозможно',
                                          reply_markup=manager_keyboards.manager_start_kb)
            else:
                referral_url = f"{config.bot_url}?start={call.message.chat.id}{config.separator}{id_event}"

                # Копирование текста в буфер обмена
                # pyperclip.copy(referral_url)
                # subprocess.run(['clip'], input=referral_url.encode('utf-8'), check=True)
                # subprocess.run(['xclip', '-selection', 'clipboard'], input=referral_url.encode('utf-8'), check=True)
                # Отправка сообщения с подтверждением копирования
                await call.message.answer(referral_url, reply_markup=manager_keyboards.manager_my_events)
                await bot.answer_callback_query(call.id, text="Ссылка на приглашение отправлена")
    else:
        if call.data == "mailing_back":
            await call.message.delete()
            await call.message.answer("Добро пожаловать в главное меню", reply_markup=admin_keyboards.a_start_kb)
        elif call.data == "channels_back":
            await call.message.answer("Добро пожаловать в главное меню", reply_markup=admin_keyboards.a_start_kb)
        elif call.data == "mailing_rus":
            await call.message.answer("Языковой сбор по RUS", reply_markup=admin_keyboards.a_mailing_kb)
            await call.message.delete()
        elif call.data == "mailing_eng":
            await call.message.answer("Языковой сбор по ENG", reply_markup=admin_keyboards.a_mailing_kb)
            await call.message.delete()
        elif call.data == "mailing_hindi":
            await call.message.answer("Языковой сбор по Хинди", reply_markup=admin_keyboards.a_mailing_kb)
            await call.message.delete()
        elif call.data == "mailing_china":
            await call.message.answer("Языковой сбор по Китаю", reply_markup=admin_keyboards.a_mailing_kb)
            await call.message.delete()
        elif call.data == "channels_rus":
            await call.message.answer("Список рускоязычных каналов", reply_markup=admin_keyboards.a_start_kb)
            await call.message.delete()
        elif call.data == "channels_eng":
            await call.message.answer("Список англоязычных каналов", reply_markup=admin_keyboards.a_start_kb)
            await call.message.delete()
        elif call.data == "channels_hindi":
            await call.message.answer("Список индоязычных каналов каналов", reply_markup=admin_keyboards.a_start_kb)
            await call.message.delete()
        elif call.data == "channels_china":
            await call.message.answer("Список катайскоязычных каналов", reply_markup=admin_keyboards.a_start_kb)
            await call.message.delete()
        if call.data == "data_back":
            await call.message.delete()
            await call.message.answer("Добро пожаловать в главное меню", reply_markup=admin_keyboards.a_start_kb)
        elif call.data == "data_rus":
            await call.message.answer("Языковой сбор по RUS", reply_markup=admin_keyboards.a_download_data_user_kb)
            await call.message.delete()
        elif call.data == "data_eng":
            await call.message.answer("Языковой сбор по ENG", reply_markup=admin_keyboards.a_download_data_user_kb)
            await call.message.delete()
        elif call.data == "data_hindi":
            await call.message.answer("Языковой сбор по Хинди", reply_markup=admin_keyboards.a_download_data_user_kb)
            await call.message.delete()
        elif call.data == "data_china":
            await call.message.answer("Языковой сбор по Китаю", reply_markup=admin_keyboards.a_download_data_user_kb)
            await call.message.delete()

    await bot.answer_callback_query(callback_query_id=call.id)


async def foo(message: types.Message, result):
    id_chat = str(message.chat.id)
    channel_name = data_conditions[str(message.chat.id)][1]['channel_name']
    id_event = data_conditions[str(message.chat.id)][2]['id_event']
    add_cond = data_conditions[str(message.chat.id)][3]['add_cond']
    phone = data_conditions[str(message.chat.id)][4]['phone']
    email = data_conditions[str(message.chat.id)][5]['email']
    user_add_cond = data_conditions[str(message.chat.id)][6]['user_add_cond']

    if result == "Телефон":
        await message.answer("Предоставить номер телефона", reply_markup=user_keyboards.phone_kb)
    elif result == "Email":
        await message.answer("Предоставьте адрес электронной почты", reply_markup=user_keyboards.back_kb)
        await Email.waiting_for_email.set()
    elif result == "Доп.дата":
        await message.answer(f"{add_cond}", reply_markup=user_keyboards.back_kb)
        await AddData.waiting_for_add_data.set()
    else:
        await user_db.addActivity(
            {'id_user': id_chat, 'id_event': id_event, 'phone': phone, 'email': email, str(add_cond): user_add_cond,
             'ref_count': 0})
        await showEvent(id_chat, id_event)
        await message.answer(texts.became_a_member, reply_markup=types.ReplyKeyboardRemove())
        user_data = await user_db.getUser(id_chat)
        event_data = user_data['event_data']
        for row in event_data:
            key = row.keys()
            id_referral = ""
            if id_event in key:
                id_referral = row.get(id_event)
            if id_referral != "":
                activity = await user_db.getReferralsEvent(id_referral, id_event)
                count_ref = activity['ref_count']
                if count_ref is None:
                    return
                user_db.incrementReferral(id_referral, id_event, count_ref)


# Обработчик сообщений с контактом
async def handle_contact(message: types.Message):
    chat_id = str(message.chat.id)
    id_event = data_conditions[str(message.chat.id)][2]['id_event']
    contact: types.Contact = message.contact

    phone_number = contact.phone_number
    first_name = contact.first_name

    data_conditions[str(message.chat.id)][4]['phone'] = phone_number

    # Делаем что-то с полученными данными
    # Например, отправляем сообщение с благодарностью
    await message.answer(f"Спасибо, {first_name}! Ваш номер телефона: {phone_number}",
                         reply_markup=types.ReplyKeyboardRemove())
    result = await checkCondition(data_conditions[str(message.chat.id)][0]['conditions'], chat_id)
    await foo(message, result)


# Обработчик адреса электронной почты
async def handle_email(message: types.Message, state: FSMContext):
    chat_id = str(message.chat.id)
    id_event = data_conditions[str(message.chat.id)][2]['id_event']
    # Проверяем, является ли введенный текст адресом электронной почты
    receive_message = message.text
    if (receive_message != "Назад"):
        if isEmailValid(receive_message):
            # Адрес электронной почты действителен, сохраняем его и сообщаем пользователю
            await user_db.updateActivity(str(message.chat.id), id_event, {'email': receive_message})
            await bot.send_message(message.chat.id, "Спасибо! Ваш адрес электронной почты сохранен.",
                                   reply_markup=types.ReplyKeyboardRemove())
            data_conditions[str(message.chat.id)][5]['email'] = receive_message

            await state.finish()
            user = await user_db.getUser(str(message.chat.id))
            result = await checkCondition(data_conditions[str(message.chat.id)][0]['conditions'], chat_id)
            await foo(message, result)
        else:
            # Адрес электронной почты недействителен, просим пользователя ввести его заново
            await bot.send_message(message.chat.id, "Неверный адрес электронной почты. Пожалуйста, введите его заново.",
                                   reply_markup=user_keyboards.back_kb)
    else:
        state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=user_keyboards.user_verification_kb)


# Обработчик капчи
async def handle_captcha(message: types.Message, state: FSMContext):
    # Проверяем, является ли введенный текст ответом на капчу
    received_message = message.text
    if received_message != "Назад":
        captcha_text_photo = data[str(message.chat.id)]['captcha']
        if (received_message == captcha_text_photo):
            # Проверка на робота прошла успешно
            await user_db.updateUser(str(message.chat.id), {'captcha': True})
            await bot.send_message(message.chat.id, "Спасибо! Вы подтвердили что вы не робот.",
                                   reply_markup=types.ReplyKeyboardRemove())
            await state.update_data(captcha_text=received_message)
            await state.finish()
            await showEvent(message.chat.id, data[str(message.chat.id)]['event_id'])
            del data[str(message.chat.id)]
        else:
            # Неверно разгадана капча
            await bot.send_message(message.chat.id, "Неверно разгадана капча, попробуйте ещё.")
            await sendCaptcha(message.chat.id)
    else:
        state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!")


# Обработчик доп. данных
async def handle_add_data(message: types.Message, state: FSMContext):
    chat_id = str(message.chat.id)
    id_event = data_conditions[str(message.chat.id)][2]['id_event']
    add_cond = data_conditions[str(message.chat.id)][3]['add_cond']
    received_message = message.text
    if received_message != "Назад":
        data_conditions[str(message.chat.id)][6]['user_add_cond'] = received_message

        await bot.send_message(message.chat.id, "Спасибо за предоставленные данные",
                               reply_markup=types.ReplyKeyboardRemove())

        await state.finish()

        result = await checkCondition(data_conditions[str(message.chat.id)][0]['conditions'], chat_id)
        await foo(message, result)

    else:
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!")


# Обработчик адреса электронной почты
async def handle_email(message: types.Message, state: FSMContext):
    chat_id = str(message.chat.id)
    id_event = data_conditions[str(message.chat.id)][2]['id_event']
    # Проверяем, является ли введенный текст адресом электронной почты
    receive_message = message.text
    if (receive_message != "Назад"):
        if isEmailValid(receive_message):
            # Адрес электронной почты действителен, сохраняем его и сообщаем пользователю
            data_conditions[str(message.chat.id)][5]['email'] = receive_message
            await bot.send_message(message.chat.id, "Спасибо! Ваш адрес электронной почты сохранен.",
                                   reply_markup=types.ReplyKeyboardRemove())
            await state.update_data(email=receive_message)

            await state.finish()

            result = await checkCondition(data_conditions[str(message.chat.id)][0]['conditions'], chat_id)
            await foo(message, result)

        else:
            # Адрес электронной почты недействителен, просим пользователя ввести его заново
            await bot.send_message(message.chat.id, "Неверный адрес электронной почты. Пожалуйста, введите его заново.",
                                   reply_markup=user_keyboards.back_kb)
    else:
        state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=user_keyboards.user_verification_kb)


async def sendCaptcha(id):
    chat_id = str(id)
    captcha = Captcha()
    await captcha.generate_captcha_picture(chat_id)

    try:
        data[str(id)].update({'captcha': captcha.captcha_text})
    except:
        data[str(id)] = {'captcha': captcha.captcha_text}

    try:
        path_captcha_folder = 'controllers/capcha_controller/capcha_images'
        photo = InputFile(f'{path_captcha_folder}/{chat_id}.jpg')

        await bot.send_photo(id, photo, caption=f'<b>Отгадайте капчу</b>', parse_mode="HTML")
        await Captcha_state.waiting_for_captcha.set()
    except:
        try:
            path_captcha_folder = '/home/root/bin/bot/controllers/capcha_controller/capcha_images'
            photo = InputFile(f'{path_captcha_folder}/{chat_id}.jpg')

            await bot.send_photo(id, photo, caption=f'<b>Отгадайте капчу</b>', parse_mode="HTML")
            await Captcha_state.waiting_for_captcha.set()
        except:
            try:
                path_captcha_folder = '/bin/bot/controllers/capcha_controller/capcha_images'
                photo = InputFile(f'{path_captcha_folder}/{chat_id}.jpg')

                await bot.send_photo(id, photo, caption=f'<b>Отгадайте капчу</b>', parse_mode="HTML")
                await Captcha_state.waiting_for_captcha.set()
            except:
                path_captcha_folder = '/controllers/capcha_controller/capcha_images'
                photo = InputFile(f'{path_captcha_folder}/{chat_id}.jpg')

                await bot.send_photo(id, photo, caption=f'<b>Отгадайте капчу</b>', parse_mode="HTML")
                await Captcha_state.waiting_for_captcha.set()


def daysBetweenTwoDates(date_start, date_end):
    # Парсим строку в объект даты
    date_obj_start = datetime.strptime(date_start, '%Y-%m-%d').date()
    date_obj_end = datetime.strptime(date_end, '%Y-%m-%d').date()

    # Вычисляем количество дней между двумя датами
    delta = date_obj_end - date_obj_start
    days = delta.days

    return days


def isEmailValid(email):
    # Регулярное выражение для проверки электронной почты
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    # Проверка электронной почты на соответствие регулярному выражению
    match = re.match(pattern, email)

    if match:
        return True
    return False


async def is_subscribed(user_id: int, channel_username: str) -> str:
    try:
        chat_member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        if chat_member.status == 'member' or chat_member.status == 'administrator' or chat_member.status == 'creator':
            return config.subscribed_status[0]
        else:
            return config.subscribed_status[1]
    except BadRequest as e:
        return config.subscribed_status[2]


# функция возвращает состояние проверки выполнения нужных условий конкурса
async def checkCondition(conditions, chat_id) -> str:
    add_cond = data_conditions[chat_id][3]['add_cond']
    phone = data_conditions[chat_id][4]['phone']
    email = data_conditions[chat_id][5]['email']
    user_add_cond = data_conditions[chat_id][6]['user_add_cond']

    # подписка на канал
    if conditions == config.conditions_event['condition1'][4::] and add_cond == '':
        return "ОК"
    # подписка + подтверждение телефона
    elif conditions == config.conditions_event['condition2'][4::] and add_cond == '':
        if phone != "":
            return "ОК"
        else:
            return "Телефон"
    # подписка + номер телефона + доп.персональные данные
    elif conditions == config.conditions_event['condition3'][4::] and add_cond != '':
        if phone == "":
            return "Телефон"
        elif user_add_cond == "":
            return "Доп.дата"
        return "ОК"

    # подписка + телефон + почта
    elif conditions == config.conditions_event['condition4'][4::] and add_cond == '':
        if phone == "":
            return "Телефон"
        elif email == "":
            return "Email"
        return "ОК"

    # подписка + номер телефона + почта + доп.данные
    elif conditions == config.conditions_event['condition5'][4::] and add_cond != '':
        if phone == "":
            return "Телефон"
        elif email == "":
            return "Email"
        elif user_add_cond == "":
            return "Доп.дата"
        return "ОК"


async def showEvent(user_id, event_id):
    event = await user_db.getEvent(event_id)
    id_event = event['_id']
    title = event['title']
    description = event['description']
    photo = event['photo']
    conditions = event['conditions']
    additional_condition = event['additional_condition']
    additional_condition_text = ''
    if additional_condition != '':
        additional_condition_text = f"<b>Дополнительно:</b>\n{config.add_condition_event}{additional_condition}"
    winners_count = int(event['winners_count'])
    chanell_url = event['chanell_url']
    time_start = event['time_start']
    time_end = event['time_end']
    duration = int(time_end - time_start)

    # Создаем объект datetime с начальной датой
    start_date = datetime.datetime(1970, 1, 1, 3)
    # Добавляем нужное количество секунд
    date = start_date + datetime.timedelta(seconds=time_start)
    # Преобразуем дату в нужный формат
    formatted_start_date = date.strftime('%d.%m.%Y %H:%M:%S')

    # Создаем объект datetime с начальной датой
    start_date = datetime.datetime(1970, 1, 1, 3)
    # Добавляем нужное количество секунд
    date = start_date + datetime.timedelta(seconds=time_end)
    # Преобразуем дату в нужный формат
    formatted_end_date = date.strftime('%d.%m.%Y %H:%M:%S')

    # Вычисляем разницу между датами
    diff = int(time_end - int(time.time()))
    formatted_duration_date = 'ЗАВЕРШЕН'
    if diff > 0:
        # Получаем количество секунд
        days = int(diff // (24 * 3600))
        hours = int(diff % (24 * 3600)) // 3600
        minutes = int(diff % 3600) // 60
        seconds = int(diff % 60)
        # Форматируем вывод
        formatted_duration_date = f"{days}:{hours}:{minutes}:{seconds}"

    icons = ['❌', '✅']
    icon = icons[0]
    referral_text = ""

    result = await user_db.checkActivity(user_id, event_id)
    if result:
        icon = icons[1]
        referral_text = await getReferralText(user_id, event_id)
        referral_text = "\n\n" + referral_text

    # event = await user_db.getEvent(id_event)
    # channel_url = event['chanell_url']
    # channel_format = f'@{channel_url.split("t.me/")[1]}'
    #
    ## проверка подписки на канал
    # received_message = await is_subscribed(int(user_id), channel_format)
    ## есть подписка на канал в посте конкурса
    # if received_message == config.subscribed_status[0]:
    #    icon = icons[1]

    header = f'''
<b>{title}</b>

{description}
'''

    body = f'''
<b>Условия для участия:</b>
{conditions}
{additional_condition_text}
'''

    footer = f'''
ID конкурса: {id_event} 4
Количество призовых мест: {winners_count}
Начало конкурса {formatted_start_date} (GMT +3)
Конец конкурса {formatted_end_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
        '''

    chanell_btn = InlineKeyboardButton(f"Подписаться на {chanell_url.split('t.me/')[1]}{icon}", callback_data="channel",
                                       url=chanell_url)
    update_btn = InlineKeyboardButton(f"Обновить", callback_data="update")
    keyboard = InlineKeyboardMarkup().add(chanell_btn).add(update_btn)

    await bot.send_photo(user_id, photo, caption=header + body + footer + referral_text, parse_mode="HTML",
                         reply_markup=keyboard)


# меняем конкурс
async def changePost(message, channel, status, id_event=None):
    icons = ['❌', '✅']
    icon = icons[1] if status else icons[0]
    chanell_btn = InlineKeyboardButton(f"Подписаться на {channel}{icon}", callback_data="channel",
                                       url=f'http://t.me/{channel}')
    update_btn = InlineKeyboardButton(f"Обновить", callback_data="update")
    keyboard = InlineKeyboardMarkup().add(chanell_btn).add(update_btn)

    referral_text = await getReferralText(message.chat.id, id_event)

    text_1 = 'Привлечённых рефералов:'
    text_2 = 'Реф.ссылка:'

    caption = message.caption
    if icon == '✅' and id_event != None and "Привлечённых рефералов" not in caption:
        caption += f"\n{referral_text}"
    if "Привлечённых рефералов" in message.caption:
        ref_count_text = caption.split(text_1)[1].split('\n')[0]
        ref_url = caption.split(text_2)[1].split('\n')[1]
        caption = caption.replace(text_1 + ref_count_text + '\n' + text_2 + ref_url, referral_text)
    message_id = message.message_id
    try:
        await bot.edit_message_caption(chat_id=message.chat.id, message_id=message_id, caption=caption,
                                       reply_markup=keyboard)
    except Exception:
        pass


# показывание реферала и ссылки
async def getReferralText(user_id, id_event):
    referral_text = ""
    hasActivity = await user_db.checkActivity(str(user_id), str(id_event))
    if hasActivity:
        activity = await user_db.getReferralsEvent(str(user_id), str(id_event))
        ref_count = activity['ref_count']
        referral_url = f"{config.bot_url}?start={user_id}{config.separator}{id_event}"
        referral_text = f'Привлечённых рефералов: {ref_count}\nРеф.ссылка: {referral_url}'

    return referral_text


######################################################################
# МЕНЕДЖЕР
######################################################################

# с этой функцией работаем после перехода в раздел 'Мои конкурсы'
async def handle_my_events_folder(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.finish()
        await ControlEvents.control_events.set()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_control_panel)
    elif message.text == "Главное меню":
        await message.answer("Добро пожаловать в главное меню", reply_markup=manager_keyboards.manager_start_kb)
        await state.finish()
    elif message.text == "Действующие":
        await showActivityEvents(message)
        await state.finish()
    elif message.text == "Завершенные":
        await showFinishedEvents(message)
        await state.finish()
    elif message.text == "Требующие подведения":
        await showNeedRandomEvents(message)


# с этой функцией работаем после перехода в раздел 'Статистика'
async def handle_manager_statistic(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.finish()
        await ControlEvents.control_events.set()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_control_panel)
    elif message.text == "Главное меню":
        await message.answer("Добро пожаловать в главное меню", reply_markup=manager_keyboards.manager_start_kb)
        await state.finish()

    # с этой функцией работаем после перехода в раздел 'Управлять'


async def handle_control_events(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.finish()
        await bot.send_message(message.chat.id, texts.main_menu, reply_markup=manager_keyboards.manager_start_kb)
    elif message.text == "Мои конкурсы":
        await message.answer(texts.my_events_folder, reply_markup=manager_keyboards.manager_my_events)
        await state.finish()
        await MyEvents.my_events.set()
    elif message.text == "Статистика":
        await state.finish()
        await ManagerStatistic.manager_statistic.set()
        await sendExcel(message=message, manager_id=str(message.chat.id), excel_path=f'{str(message.chat.id)}.xlsx')
    elif message.text == "Поставить на охрану":
        await message.answer(texts.security, reply_markup=manager_keyboards.manager_channels_security_kb)
        await state.finish()
        await SecurityState.securuty.set()


# с этой функцией работаем после перехода в раздел 'Поставить на охрану'
async def handle_security_folder(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.finish()
        await ControlEvents.control_events.set()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_control_panel)
    elif message.text == "Главное меню":
        await message.answer("Добро пожаловать в главное меню", reply_markup=manager_keyboards.manager_start_kb)
        await state.finish()
    elif message.text == "Чат":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Канал":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Всё":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Стоп слова":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Запрет ссылок":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Капча при добавлении на канал":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)
    elif message.text == "Предупреждение (1 из 3)":
        await message.answer(texts.todo, reply_markup=manager_keyboards.manager_channels_security_kb)


async def showActivityEvents(message: types.Message):
    chat_id = message.chat.id
    events = manager_db.getEvents(str(chat_id), config.event_statuses[0])
    print(events)
    if events != None:
        for event in events:
            event_status = event['status']
            if event_status == config.event_statuses[0]:
                id_event = event['_id']
                title = event['title']
                description = event['description']
                photo = event['photo']
                conditions = event['conditions']
                # if event['additional_condition'] is not None:
                #     additional_condition = event['additional_condition']
                #     additional_condition_text = ''
                #     if additional_condition != '':
                #         additional_condition_text = f"<b>Дополнительно:</b>\n{config.add_condition_event}{additional_condition}"
                winners_count = int(event['winners_count'])
                time_start = event['time_start']
                time_end = event['time_end']
                duration = int(time_end - time_start)

                # Создаем объект datetime с начальной датой
                start_date = datetime.datetime(1970, 1, 1, 3)
                # Добавляем нужное количество секунд
                date = start_date + datetime.timedelta(seconds=time_start)
                # Преобразуем дату в нужный формат
                formatted_start_date = date.strftime('%d.%m.%Y %H:%M:%S')

                # Создаем объект datetime с начальной датой
                start_date = datetime.datetime(1970, 1, 1, 3)
                # Добавляем нужное количество секунд
                date = start_date + datetime.timedelta(seconds=time_end)
                # Преобразуем дату в нужный формат
                formatted_end_date = date.strftime('%d.%m.%Y %H:%M:%S')

                # Вычисляем разницу между датами
                diff = int(time_end - int(time.time()))
                formatted_duration_date = 'ЗАВЕРШЕН'
                if diff > 0:
                    # Получаем количество секунд
                    days = int(diff // (24 * 3600))
                    hours = int(diff % (24 * 3600)) // 3600
                    minutes = int(diff % 3600) // 60
                    seconds = int(diff % 60)
                    # Форматируем вывод
                    formatted_duration_date = f"{days}:{hours}:{minutes}:{seconds}"

                take_part = f"<a href='{config.bot_url}?start={chat_id}{config.separator}{id_event}'>\nУчаствовать</a>\n"

                header = f'''
<b>{title}</b>

{description}
'''

                body = f'''
<b>Условия для участия:</b>
{conditions}

'''

                footer = f'''
ID конкурса: {id_event} 5
Количество призовых мест: {winners_count}
Начало конкурса {formatted_start_date} (GMT +3)
Конец конкурса {formatted_end_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
''' #{additional_condition_text}

                await bot.send_photo(message.chat.id, photo, caption=header + body + footer + take_part,
                                     parse_mode="HTML", reply_markup=manager_keyboards.take_part)


async def showNeedRandomEvents(message: types.Message):
    chat_id = message.chat.id
    events = manager_db.getEvents(str(chat_id), config.event_statuses[1])
    if events != None:
        for event in events:
            event_status = event['status']
            if event_status == config.event_statuses[1]:
                id_event = event['_id']
                title = event['title']
                description = event['description']
                photo = event['photo']
                conditions = event['conditions']
                #additional_condition = event['additional_condition']
                # additional_condition_text = ''
                # if additional_condition != '':
                #     additional_condition_text = f"<b>Дополнительно:</b>\n{config.add_condition_event}{additional_condition}"
                winners_count = int(event['winners_count'])
                time_start = event['time_start']
                time_end = event['time_end']
                duration = int(time_end - time_start)

                # Создаем объект datetime с начальной датой
                start_date = datetime.datetime(1970, 1, 1, 3)
                # Добавляем нужное количество секунд
                date = start_date + datetime.timedelta(seconds=time_start)
                # Преобразуем дату в нужный формат
                formatted_start_date = date.strftime('%d.%m.%Y %H:%M:%S')

                # Создаем объект datetime с начальной датой
                start_date = datetime.datetime(1970, 1, 1, 3)
                # Добавляем нужное количество секунд
                date = start_date + datetime.timedelta(seconds=time_end)
                # Преобразуем дату в нужный формат
                formatted_end_date = date.strftime('%d.%m.%Y %H:%M:%S')

                # Вычисляем разницу между датами
                diff = int(time_end - int(time.time()))
                formatted_duration_date = 'ЗАВЕРШЕН'
                if diff > 0:
                    # Получаем количество секунд
                    days = diff // (24 * 3600)
                    hours = (diff % (24 * 3600)) // 3600
                    minutes = (diff % 3600) // 60
                    seconds = diff % 60
                    # Форматируем вывод
                    formatted_duration_date = f"{days}:{hours}:{minutes}:{seconds}"

                header = f'''
<b>{title}</b>

{description}
'''

                body = f'''
<b>Условия для участия:</b>
{conditions}
'''

                footer = f'''
ID конкурса: {id_event}  1
Количество призовых мест: {winners_count}
Начало конкурса {formatted_start_date} (GMT +3)
Конец конкурса {formatted_end_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
''' #{additional_condition_text}
                await message.answer("Конкурсы требующие подтверждения",
                                     reply_markup=manager_keyboards.manager_my_events)
                await bot.send_photo(message.chat.id, photo, caption=header + body + footer, parse_mode="HTML",
                                     reply_markup=manager_keyboards.random)
                await MyEvents.my_events.set()


async def showFinishedEvents(message: types.Message):
    try:
        chat_id = message.chat.id
        events = manager_db.getEvents(str(chat_id), config.event_statuses[2])
        if events != None:
            for event in events:
                event_status = event['status']
                if event_status == config.event_statuses[2]:
                    id_event = event['_id']
                    id_manager = int(event['id_manager'])
                    caption_event = event['title']
                    publish_text = event['publish_text']
                    photo = event['photo']
                    channel_id = event['channel_id']
                    winners_count = event['winners_count']
                    additional_condition = ''
                    try:
                        additional_condition = event['additional_condition']
                    except Exception:
                        pass

                    winners_id = list(event['winners'])
                    winners_print = ""
                    for winner_id in winners_id:
                        user = await user_db.getUser(winner_id)
                        username = user['username']
                        if username != None:
                            if (additional_condition != ''):
                                activity = await manager_db.getActivity(user['chat_id'], id_event)
                                try:
                                    additional_condition_answer = activity[additional_condition]
                                except:
                                    additional_condition_answer = ''
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                            else:
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                        else:
                            if (additional_condition != ''):
                                activity = await manager_db.getActivity(user['chat_id'], id_event)
                                try:
                                    additional_condition_answer = activity[additional_condition]
                                except:
                                    additional_condition_answer = ''
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                            else:
                                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                    publish_text = f'''
<b>Подведение итогов</b>

<b>{caption_event}</b>

{publish_text}

<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}    
'''

                    await bot.send_message(id_manager, text=publish_text, parse_mode="HTML",
                                           disable_web_page_preview=True,
                                           reply_markup=manager_keyboards.manager_my_events)
    except Exception as ex:
        print(ex)


# Обработчик получения conditions
async def handle_conditions(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, texts.main_menu, reply_markup=manager_keyboards.manager_start_kb)
    else:
        try:
            if message.text not in config.digits:
                raise Exception
            try:
                data = await state.get_data()
                is_event_edit = data.get("edit_event")
                if is_event_edit:
                    async with state.proxy() as data:
                        data['conditions'] = message.text
                    await EventState.waiting_for_publish.set()
                    await prePublishEvent(data, message)
                    await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                else:
                    async with state.proxy() as data:
                        data['conditions'] = message.text
                        data['channels_urls'] = []

                    channels = manager_db.getChannels(str(message.chat.id))
                    count = 0
                    channels_text = ""
                    for channel in channels:
                        channel_info = await getChannelInfo(channel['channel_id'])
                        channels_text += f"\n\n{config.digits[count]} {channel_info.username}"
                        async with state.proxy() as data:
                            print(await channel_info.get_url())
                            channel_url = await channel_info.get_url()
                            data['channels_urls'].append({f'{channel_url}': int(channel['channel_id'])})
                        count += 1
                    if count == 0:
                        pass
                    elif count == 1:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_1)
                    elif count == 2:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_2)
                    elif count == 3:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_3)
                    await EventState.next()
            except Exception as ex:
                print(f"Ошибка handle_conditions: {ex}")
                async with state.proxy() as data:
                    data['conditions'] = message.text
                    data['channels_urls'] = []

                    channels = manager_db.getChannels(str(message.chat.id))
                    count = 0
                    channels_text = ""
                    for channel in channels:
                        channel_info = await getChannelInfo(channel['channel_id'])
                        channels_text += f"\n\n{config.digits[count]} {channel_info.username}"
                        async with state.proxy() as data:
                            print(await channel_info.get_url())
                            channel_url = await channel_info.get_url()
                            data['channels_urls'].append({f'{channel_url}': int(channel['channel_id'])})
                        count += 1
                    if count == 0:
                        pass
                    elif count == 1:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_1)
                    elif count == 2:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_2)
                    elif count == 3:
                        await message.answer(f"Выбери канал:{channels_text}",
                                             reply_markup=manager_keyboards.exit_create_event_3)
                    await message.answer(texts.event_create, reply_markup=manager_keyboards.manager_start_kb)
                    await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения chanell_url
async def handle_chanell_url(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(conditions_msg, reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
        await EventState.waiting_for_conditions.set()
    else:
        try:
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['chanell_url'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['chanell_url'] = message.text
                await message.answer(texts.event_create, reply_markup=manager_keyboards.exit_create_event)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения title
async def handle_title(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        try:
            channels = manager_db.getChannels(str(message.chat.id))
            count = 0
            channels_text = ""
            for channel in channels:
                channel_info = await getChannelInfo(channel['channel_id'])
                channels_text += f"\n\n{config.digits[count]} {channel_info.active_usernames[0]}"
                async with state.proxy() as data:
                    print(await channel_info.get_url())
                    data['channels_urls'].append(await channel_info.get_url())
                count += 1
            if count == 0:
                pass
            elif count == 1:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_1)
            elif count == 2:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_2)
            elif count == 3:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_3)
            await EventState.waiting_for_chanell_url.set()
        except Exception as ex:
            print(ex)
    else:
        try:
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['title'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['title'] = message.text
                await message.answer(texts.description_event, reply_markup=manager_keyboards.exit_create_event)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения description
async def handle_description(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.event_create, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_title.set()
    else:
        try:
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['description'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['description'] = message.text
                await message.answer(texts.photo_event, reply_markup=manager_keyboards.exit_create_event)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения photo
async def handle_photo(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.description_event, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_description.set()
    else:
        try:
            if not message.photo:
                raise Exception
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['photo'] = message.photo[-1].file_id
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['photo'] = message.photo[-1].file_id

                if (data['conditions'] == config.digits[2] or data['conditions'] == config.digits[4]):
                    await message.answer(texts.add_cond, reply_markup=manager_keyboards.exit_create_event)
                    await EventState.next()
                else:
                    await message.answer(texts.win_places_event, reply_markup=manager_keyboards.exit_create_event)
                    await EventState.waiting_for_winners_count.set()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.exit_create_event)
            print(e)


# Обработчик получения add_condition
async def handle_add_condition(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await EventState.waiting_for_photo.set()
        await message.answer(texts.photo_event, reply_markup=manager_keyboards.exit_create_event)
    else:
        try:
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['add_condition'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['add_condition'] = message.text
                await message.answer(texts.win_places_event, reply_markup=manager_keyboards.exit_create_event)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения winners_count
async def handle_winners_count(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.add_cond, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_add_condition.set()
    else:
        try:
            if not message.text.isdigit():
                raise Exception
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['winners_count'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['winners_count'] = message.text
                await message.answer(texts.duration_event_1, reply_markup=manager_keyboards.duration_kb)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
            print(e)


# Обработчик получения time_interval
async def handle_time_interval(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.win_places_event, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_winners_count.set()
    # минуты
    elif (message.text in config.time_intervals):
        try:
            async with state.proxy() as data:
                data['time_interval'] = message.text
            await message.answer(texts.duration_event_2, reply_markup=manager_keyboards.exit_create_event)
            await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.manager_start_kb)
            print(e)


# Обработчик получения duration
async def handle_duration(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.duration_event_1, reply_markup=manager_keyboards.duration_kb)
        await EventState.waiting_for_time_interval.set()
    else:
        try:
            if not message.text.isdigit():
                raise Exception
            data = await state.get_data()
            is_event_edit = data.get("edit_event")
            if is_event_edit:
                async with state.proxy() as data:
                    data['duration'] = message.text
                await prePublishEvent(data, message)
                await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
                await EventState.waiting_for_publish.set()
            else:
                async with state.proxy() as data:
                    data['duration'] = message.text
                await message.answer(texts.publish_text, reply_markup=manager_keyboards.exit_create_event)
                await EventState.next()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.exit_create_event)
            print(e)


# Обработчик получения duration
async def handle_publish_text(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.duration_event_1, reply_markup=manager_keyboards.duration_kb)
        await EventState.waiting_for_time_interval.set()
    else:
        try:
            async with state.proxy() as data:
                data['publish_text'] = message.text
            event_data = await state.get_data()
            await prePublishEvent(event_data, message)
            await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
            await EventState.waiting_for_publish.set()
        except(Exception) as e:
            await message.answer("Сообщение имело невернный ввод, попробуйте ещё раз:",
                                 reply_markup=manager_keyboards.exit_create_event)
            print(e)


# Обработчик согласия на публикацию
async def handle_event_publish(message: types.Message, state: FSMContext):
    if (message.text == "Выйти из создания конкурса"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer(texts.duration_event_2, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_duration.set()
    elif (message.text == config.publish_choice[0]):
        event_data = await state.get_data()
        await message.answer(texts.publish_event, reply_markup=manager_keyboards.manager_start_kb)
        await createEvent(event_data, message)
        await state.finish()
    elif (message.text == config.publish_choice[1]):
        async with state.proxy() as data:
            data['edit_event'] = True
        await message.answer(texts.edit_field_event, reply_markup=manager_keyboards.edit_event_field_kb)
        await EventState.waiting_for_edit_field.set()


# Обработчик редактирования полей
async def handle_edit_field(message: types.Message, state: FSMContext):
    translate: LocalizedTranslator = config.translator(language=str(message.from_user.locale))
    if (message.text == translate.get(key='exit_contest_creation')):
        await state.finish()
        await bot.send_message(message.chat.id, translate.get(key='some_other_time'),
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        async with state.proxy() as data:
            data['edit_event'] = False
        event_data = await state.get_data()
        await prePublishEvent(event_data, message)
        await message.answer(texts.pre_publish_event, reply_markup=manager_keyboards.publish_kb)
        await EventState.waiting_for_publish.set()
    # условия
    elif (message.text == config.event_fields[0]):
        await message.answer(conditions_msg, reply_markup=manager_keyboards.manager_channels_create_event_conditions_kb)
        await EventState.waiting_for_conditions.set()
    # выбор канала
    elif (message.text == config.event_fields[1]):
        try:
            channels = manager_db.getChannels(str(message.chat.id))
            count = 0
            channels_text = ""
            for channel in channels:
                channel_info = await getChannelInfo(channel['channel_id'])
                channels_text += f"\n\n{config.digits[count]} {channel_info.active_usernames[0]}"
                async with state.proxy() as data:
                    print(await channel_info.get_url())
                    data['channels_urls'].append(await channel_info.get_url())
                count += 1
            if count == 0:
                pass
            elif count == 1:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_1)
            elif count == 2:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_2)
            elif count == 3:
                await message.answer(f"Выбери канал:{channels_text}",
                                     reply_markup=manager_keyboards.exit_create_event_3)
            await EventState.waiting_for_chanell_url.set()
        except Exception as ex:
            print(ex)
    # название
    elif (message.text == config.event_fields[2]):
        await message.answer(texts.event_create, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_title.set()
    # описание
    elif (message.text == config.event_fields[3]):
        await message.answer(texts.description_event, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_description.set()
    # фотография
    elif (message.text == config.event_fields[4]):
        await EventState.waiting_for_photo.set()
        await message.answer(texts.photo_event, reply_markup=manager_keyboards.exit_create_event)
    # кол-во призовых мест
    elif (message.text == config.event_fields[5]):
        await message.answer(texts.win_places_event, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_winners_count.set()
    # доп.данные
    elif (message.text == config.event_fields[6]):
        await message.answer(texts.add_cond, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_add_condition.set()
    # время (начиная с интервала)
    elif (message.text == config.event_fields[7]):
        await message.answer(texts.duration_event_1, reply_markup=manager_keyboards.duration_kb)
        await EventState.waiting_for_time_interval.set()
    # публикационный текст
    elif (message.text == config.event_fields[8]):
        await message.answer(texts.publish_text, reply_markup=manager_keyboards.exit_create_event)
        await EventState.waiting_for_publish_text.set()


# Обработчик согласия на публикацию результатов
async def handle_publish_results(message: types.Message, state: FSMContext):
    global data_id_random_event
    id_event = data_id_random_event[str(message.chat.id)]
    if (message.text == "Главное меню"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        await message.answer("Добро пожаловать в панель управления",
                             reply_markup=manager_keyboards.manager_control_panel)
        await ControlEvents.control_events.set()
    elif (message.text == config.reroll_or_publish_event[3]):
        await state.finish()
        await MyEvents.my_events.set()
        await message.answer(texts.my_events_folder, reply_markup=manager_keyboards.manager_my_events)
    elif (message.text == config.reroll_or_publish_event[0]):
        event = await manager_db.getEvent(id_event)
        if event:
            if event['status'] != config.event_statuses[1]:
                await message.answer('Действие выполнить невозможно!', reply_markup=manager_keyboards.manager_my_events)
            else:
                id_event = event['_id']
                id_manager = int(event['id_manager'])
                caption_event = event['title']
                publish_text = event['publish_text']
                photo = event['photo']
                channel_id = event['channel_id']
                winners_count = event['winners_count']
                additional_condition = ''
                try:
                    additional_condition = event['additional_condition']
                except Exception:
                    pass

                pre_winners = await manager_db.getWinners(id_event=id_event)
                winners_id = randomizer.getDataWinners(winners_count, pre_winners)
                winners_print = ""
                for winner_id in winners_id:
                    user = await user_db.getUser(winner_id)
                    username = user['username']
                    if username != None:
                        winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                    else:
                        winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                publish_text = f'''
<b>Подведение итогов</b>

<b>{caption_event}</b>

{publish_text}

<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}    
'''

                await manager_db.updateEvent(id_event, {'status': config.event_statuses[2]})
                await bot.send_message(channel_id, text=publish_text, parse_mode="HTML", disable_web_page_preview=True)
                await bot.send_message(id_manager, text="Успех! Результаты опубликованы!", parse_mode="HTML",
                                       reply_markup=manager_keyboards.manager_my_events)
                await state.finish()
    elif (message.text == config.reroll_or_publish_event[1]):
        event = await manager_db.getEvent(id_event)
        if event:
            if event['status'] != config.event_statuses[1]:
                await message.answer('Действие выполнить невозможно!', reply_markup=manager_keyboards.manager_my_events)
            else:
                try:
                    ban_winners = list(event['ban'])
                    if len(ban_winners) > 0:
                        for winner in list(event['winners']):
                            ban_winners.append(winner)
                        await manager_db.updateEvent(id_event, {'ban': ban_winners})
                except Exception:
                    await manager_db.updateEvent(id_event, {'ban': event['winners']})
                event = await manager_db.getEvent(id_event)
                id_event = event['_id']
                id_manager = int(event['id_manager'])
                caption_event = event['title']
                publish_text = event['publish_text']
                photo = event['photo']
                winners_count = event['winners_count']
                additional_condition = ''
                try:
                    additional_condition = event['additional_condition']
                except Exception:
                    pass

                ban_winners = list(event['ban'])
                pre_winners = await manager_db.getWinners(id_event=id_event)
                pre_winners = list(pre_winners)
                filtered_list = [d for d in pre_winners if d['id_user'] not in ban_winners]

                winners_id = randomizer.getDataWinners(winners_count, filtered_list)
                await manager_db.updateEvent(id_event, {'winners': winners_id})
                winners_print = ""
                for winner_id in winners_id:
                    user = await user_db.getUser(winner_id)
                    username = user['username']
                    if username != None:
                        if (additional_condition != ''):
                            activity = await manager_db.getActivity(user['chat_id'], id_event)
                            additional_condition_answer = activity[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                    else:
                        if (additional_condition != ''):
                            activity = await manager_db.getActivity(user['chat_id'], id_event)
                            additional_condition_answer = activity[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                publish_text = f'''
<b>Предварительные итоги конкурса</b>
<b>{caption_event}</b>
<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}
'''
                await bot.send_message(id_manager, text=publish_text, parse_mode="HTML", disable_web_page_preview=True)
                await bot.send_message(id_manager, text=texts.publish_or_reroll_event,
                                       reply_markup=manager_keyboards.publish_or_reroll_kb)
    elif (message.text == config.reroll_or_publish_event[2]):
        await message.answer(texts.reroll_numbers, reply_markup=manager_keyboards.back_and_main_menu_kb)
        await RerollNumberState.waiting_for_number_winners.set()


# Обработчик получения реролла по номерам
async def handle_reroll_numbers(message: types.Message, state: FSMContext):
    global data_id_random_event
    id_event = data_id_random_event[str(message.chat.id)]
    if (message.text == "Главное меню"):
        await state.finish()
        await bot.send_message(message.chat.id, "Как-нибудь в другой раз!",
                               reply_markup=manager_keyboards.manager_start_kb)
    elif (message.text == "Назад"):
        event = await manager_db.getEvent(id_event)
        if event:
            if event['status'] != config.event_statuses[1]:
                await message.answer('Действие выполнить невозможно!', reply_markup=manager_keyboards.manager_my_events)
            else:
                id_event = event['_id']
                id_manager = int(event['id_manager'])
                caption_event = event['title']
                publish_text = event['publish_text']
                photo = event['photo']
                winners_count = event['winners_count']
                additional_condition = ''
                try:
                    additional_condition = event['additional_condition']
                except Exception:
                    pass

                winners_id = list(event['winners'])
                winners_print = ""
                for winner_id in winners_id:
                    user = await user_db.getUser(winner_id)
                    username = user['username']
                    if username != None:
                        if (additional_condition != ''):
                            additional_condition_answer = user[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                    else:
                        if (additional_condition != ''):
                            additional_condition_answer = user[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                publish_text = f'''
<b>Предварительные итоги конкурса</b>
<b>{caption_event}</b>
<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}
'''
                await bot.send_message(id_manager, text=publish_text, parse_mode="HTML")
                await bot.send_message(id_manager, text=texts.publish_or_reroll_event,
                                       reply_markup=manager_keyboards.publish_or_reroll_kb)
    else:
        isAllDigits = True
        list_numbers = []
        list_numbers_text = message.text.split(' ')
        for digit in list_numbers_text:
            if not digit.isdigit():
                await message.answer('Неверный формат, попробуйте ещё')
                isAllDigits = False
                break
            else:
                list_numbers.append(int(digit))
        if (isAllDigits):
            list_numbers = list(set(list_numbers))

            event = await manager_db.getEvent(id_event)

            if max(list_numbers) > len(list(event['winners'])):
                await message.answer('Неверный формат, попробуйте ещё')
            else:
                try:
                    new_ban_winners = []
                    for position in range(0, len(list(event['winners']))):
                        if (position + 1) in list_numbers:
                            new_ban_winners.append(list(event['winners'])[position])

                    ban_winners = list(event['ban'])
                    if len(ban_winners) > 0:
                        for ban in new_ban_winners:
                            ban_winners.append(ban)
                        await manager_db.updateEvent(id_event, {'ban': ban_winners})
                except Exception:
                    await manager_db.updateEvent(id_event, {'ban': new_ban_winners})

                event = await manager_db.getEvent(id_event)
                id_event = event['_id']
                id_manager = int(event['id_manager'])
                caption_event = event['title']
                publish_text = event['publish_text']
                photo = event['photo']
                winners_count = event['winners_count']
                additional_condition = ''
                try:
                    additional_condition = event['additional_condition']
                except Exception:
                    pass

                ban_winners = list(event['ban'])
                pre_winners = await manager_db.getWinners(id_event=id_event)
                pre_winners = list(pre_winners)
                filtered_list = [d for d in pre_winners if d['id_user'] not in ban_winners]

                winners_id = randomizer.getDataWinners(winners_count, filtered_list)
                await manager_db.updateEvent(id_event, {'winners': winners_id})
                winners_print = ""
                for winner_id in winners_id:
                    user = await user_db.getUser(winner_id)
                    username = user['username']
                    if username != None:
                        if (additional_condition != ''):
                            activity = await manager_db.getActivity(user['chat_id'], id_event)
                            additional_condition_answer = activity[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
                    else:
                        if (additional_condition != ''):
                            activity = await manager_db.getActivity(user['chat_id'], id_event)
                            additional_condition_answer = activity[additional_condition]
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}\n"
                        else:
                            winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

                publish_text = f'''
<b>Предварительные итоги конкурса</b>
<b>{caption_event}</b>
<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}
'''
                await bot.send_message(id_manager, text=publish_text, parse_mode="HTML", disable_web_page_preview=True)
                await bot.send_message(id_manager, text=texts.publish_or_reroll_event,
                                       reply_markup=manager_keyboards.publish_or_reroll_kb)
                await RerollOrPublishState.waiting_for_choice_action.set()


# функция проверяющая статус бота на введённом сообществе
async def handle_addBotToChannel(message: types.Message, state: FSMContext):
    if message.text == "Назад":
        await state.finish()
        await bot.send_message(message.chat.id, texts.main_menu, reply_markup=manager_keyboards.manager_start_kb)
    elif message.text == "Написать в поддержку":
        await message.answer(texts.support_folder, parse_mode="HTML", disable_web_page_preview=True,
                             reply_markup=manager_keyboards.main_menu)
        await state.finish()
    else:
        channel_id = message.text
        try:
            # Get the chat member object for the bot in the channel
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)

            # Check if the bot is an administrator of the channel
            if bot_member.status == 'administrator':
                retuls = manager_db.checkChannel(channel_id)
                if retuls:
                    await message.answer("Сообщество уже подтверждёно, можете попробовать другое",
                                         reply_markup=manager_keyboards.back)
                else:
                    manager_db.addChannel(str(message.chat.id), channel_id)
                    await message.answer("Сообщество подтверждено, теперь можете перейти к созданию Конкурса",
                                         reply_markup=manager_keyboards.manager_start_kb)
                    await state.finish()
            else:
                await message.answer("Бот, возможно, ещё не добавлен", reply_markup=manager_keyboards.back)
        except ChatNotFound:
            await bot.send_message(message.chat.id, "Такой чат не найден, попробуйте другой!",
                                   reply_markup=manager_keyboards.back)
        except BotKicked:
            await bot.send_message(message.chat.id, "Бот был кикнут!", reply_markup=manager_keyboards.back)


async def getChannelInfo(channel_id):
    return await bot.get_chat(chat_id=channel_id)


def daysBetweenTwoDates(date_start, date_end):
    # Парсим строку в объект даты
    date_obj_start = datetime.strptime(date_start, '%Y-%m-%d').date()
    date_obj_end = datetime.strptime(date_end, '%Y-%m-%d').date()

    # Вычисляем количество дней между двумя датами
    delta = date_obj_end - date_obj_start
    days = delta.days

    return days


async def prePublishEvent(data, message):
    try:
        conditions = data['conditions']
        add_condition = ""

        if conditions == '1️⃣':
            conditions = conditions_event['condition1'][4::]
        elif conditions == '2️⃣':
            conditions = conditions_event['condition2'][4::]
        elif conditions == '3️⃣':
            conditions = conditions_event['condition3'][4::]
            add_condition = f"<b>Дополнительно:</b>\n{config.add_condition_event}{data['add_condition']}"
        elif conditions == '4️⃣':
            conditions = conditions_event['condition4'][4::]
        elif conditions == '5️⃣':
            conditions = conditions_event['condition5'][4::]
            add_condition = f"<b>Дополнительно:</b>\n{config.add_condition_event}{data['add_condition']}"

        id = str(message.chat.id)
        title = data['title']
        photo = data['photo']
        description = data['description']
        winners_count = int(data['winners_count'])
        time_interval = data['time_interval']
        duration = int(data['duration'])
        publish_text = data['publish_text']
        duration_absolute_seconds = 0

        chanell_url = data['chanell_url']

        if chanell_url == '1️⃣':
            chanell_url = list(data['channels_urls'][0].keys())[0]
        if chanell_url == '2️⃣':
            chanell_url = list(data['channels_urls'][1].keys())[0]
        if chanell_url == '3️⃣':
            chanell_url = list(data['channels_urls'][2].keys())[0]

        # минуты
        if time_interval == config.time_intervals[0]:
            duration_absolute_seconds = duration * 60
        # часы
        elif time_interval == config.time_intervals[1]:
            duration_absolute_seconds = duration * 60 * 60
        # дни
        elif time_interval == config.time_intervals[2]:
            duration_absolute_seconds = duration * 24 * 60 * 60

        # Получаем текущую дату и время
        now = datetime.datetime.now()
        # Получаем текущую дату в формате
        formatted_now = now.strftime('%d.%m.%Y %H:%M:%S')
        # Прибавляем duration_absolute_seconds к дате и времени
        new_date = now + datetime.timedelta(seconds=duration_absolute_seconds)
        # Преобразуем новую дату и время в нужный формат
        formatted_new_date = new_date.strftime('%d.%m.%Y %H:%M:%S')

        # Вычисляем разницу между датами
        diff = int((new_date - now).total_seconds())
        # Получаем количество секунд
        days = int(diff // (24 * 3600))
        hours = int(diff % (24 * 3600)) // 3600
        minutes = int(diff % 3600) // 60
        seconds = int(diff % 60)
        # Форматируем вывод
        formatted_duration_date = f"{days}:{hours}:{minutes}:{seconds}"

        id_event = uidController.generate_id()

        header = f'''
<b>{title}</b>

{description}
'''

        body = f'''
<b>Условия для участия:</b>
{conditions}
{add_condition}
'''

        footer = f'''
ID конкурса: {id_event} 2
Количество призовых мест: {winners_count}
Начало конкурса {formatted_now} (GMT +3)
Конец конкурса {formatted_new_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
        '''

        await bot.send_photo(message.chat.id, photo, caption=header + body + footer, parse_mode="HTML",
                             reply_markup=manager_keyboards.publish_kb)
        await bot.send_message(message.chat.id,
                               text='<b>Ваш текст для поста с результатами вашего конкурса:</b>\n\n' + publish_text,
                               parse_mode="HTML", reply_markup=manager_keyboards.publish_kb)

    except(Exception) as e:
        print(e)


async def createEvent(data, message):
    print(data, message)
    # try:
    conditions = data['conditions']
    add_condition = ""

    if conditions == '1️⃣':
        conditions = conditions_event['condition1'][4::]
    elif conditions == '2️⃣':
        conditions = conditions_event['condition2'][4::]
    elif conditions == '3️⃣':
        conditions = conditions_event['condition3'][4::]
        add_condition = f"<b>Дополнительно:</b>\n{config.add_condition_event}{data['add_condition']}"
    elif conditions == '4️⃣':
        conditions = conditions_event['condition4'][4::]
    elif conditions == '5️⃣':
        conditions = conditions_event['condition5'][4::]
        add_condition = f"<b>Дополнительно:</b>\n{config.add_condition_event}{data['add_condition']}"

    id = str(message.chat.id)
    title = data['title']
    photo = data['photo']
    description = data['description']
    winners_count = int(data['winners_count'])
    time_interval = data['time_interval']
    duration = int(data['duration'])
    publish_text = data['publish_text']
    duration_absolute_seconds = 0

    chanell_url = data['chanell_url']
    channel_id = 0

    if chanell_url == '1️⃣':
        chanell_url = list(data['channels_urls'][0].keys())[0]
        channel_id = list(data['channels_urls'][0].values())[0]
    if chanell_url == '2️⃣':
        chanell_url = list(data['channels_urls'][1].keys())[0]
        channel_id = list(data['channels_urls'][1].values())[0]
    if chanell_url == '3️⃣':
        chanell_url = list(data['channels_urls'][2].keys())[0]
        channel_id = list(data['channels_urls'][2].values())[0]
    print(channel_id)
    # минуты
    if time_interval == config.time_intervals[0]:
        duration_absolute_seconds = duration * 60
    # часы
    elif time_interval == config.time_intervals[1]:
        duration_absolute_seconds = duration * 60 * 60
    # дни
    elif time_interval == config.time_intervals[2]:
        duration_absolute_seconds = duration * 24 * 60 * 60

    # Получаем текущую дату и время
    now = datetime.datetime.now()
    # Получаем текущую дату в формате
    formatted_now = now.strftime('%d.%m.%Y %H:%M:%S')
    # Прибавляем duration_absolute_seconds к дате и времени
    new_date = now + datetime.timedelta(seconds=duration_absolute_seconds)
    # Преобразуем новую дату и время в нужный формат
    formatted_new_date = new_date.strftime('%d.%m.%Y %H:%M:%S')

    # Вычисляем разницу между датами
    diff = int((new_date - now).total_seconds())
    # Получаем количество секунд
    days = int(diff // (24 * 3600))
    hours = int(diff % (24 * 3600)) // 3600
    minutes = int(diff % 3600) // 60
    seconds = int(diff % 60)
    # Форматируем вывод
    formatted_duration_date = f"{days}:{hours}:{minutes}:{seconds}"

    id_event = uidController.generate_id()
    event_data = {'_id': id_event, 'id_manager': id, 'title': title, 'photo': photo, 'description': description,
                  'winners_count': winners_count, 'conditions': conditions,
                  'chanell_url': chanell_url, 'channel_id': channel_id,
                  'publish_text': publish_text, 'time_start': time.time(),
                  'time_end': time.time() + duration_absolute_seconds, 'status': config.event_statuses[0]}

    await manager_db.addEvent(event_data)

    take_part = f"<a href='{config.bot_url}?start={int(id)}{config.separator}{id_event}'>\nУчаствовать</a>\n"

    header = f'''
<b>{title}</b>

{description}
'''

    body = f'''
<b>Условия для участия:</b>
{conditions}
{add_condition}
'''

    footer = f'''
ID конкурса: {id_event} 3
Количество призовых мест: {winners_count}
Начало конкурса {formatted_now} (GMT +3)
Конец конкурса {formatted_new_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
'''

    footer_channel = f'''
Количество призовых мест: {winners_count}
Начало конкурса {formatted_now} (GMT +3)
Конец конкурса {formatted_new_date} (GMT +3)
Осталось до завершения {formatted_duration_date}
    '''

    await bot.send_photo(message.chat.id, photo, caption=header + body + footer + take_part, parse_mode="HTML",
                         reply_markup=manager_keyboards.take_part)
    print(channel_id)
    await bot.send_photo(channel_id, photo, caption=header + body + footer_channel + take_part, parse_mode="HTML")
# except(Exception) as e:
#     print(e, 'ex')

# Функция для проверки базы данных на наличие новых конкурсов
def check_for_new_contests():
    pass
    # Подключение к базе данных
    client = MongoClient(
        "mongodb+srv://pythonnemo:pythonnemo@cluster0.gd2mzdl.mongodb.net/?retryWrites=true&w=majority")

    db = client['prizehunt']
    contests = db['events']

    # Выбираем все конкурсы, у которых время окончания меньше текущего времени
    contests_to_delete = []
    for contest in contests.find({"time_end": {"$lt": time.time()}}):
        if contest['status'] == config.event_statuses[0]:
            try:
                CHAT_ID = contest['id_manager']
                bot = Bot(token=cfg['token'])
                template = f'''
<b>Ваш конкурс завершен:</b>
{contest['title']}

(Время вашего конкурса подошло к концу. Теперь требует подведения результатов и его публикация, зайдите в раздел <b>Панель управления-Мои конкурсы-Требующие подведения</b>
'''
                asyncio.run(bot.send_message(
                    CHAT_ID,
                    f"{template}\n",
                    parse_mode="HTML",
                ))

                asyncio.run(manager_db.updateEvent(contest['_id'], {'status': config.event_statuses[1]}), )
                # Добавляем конкурс для удаления
                contests_to_delete.append(contest['_id'])
            except exceptions.BotBlocked:
                print(f"Bot was blocked by user {CHAT_ID}")
            except exceptions.ChatNotFound:
                print(f"Chat not found: {CHAT_ID}")
            except exceptions.RetryAfter as e:
                print(f"Flood control exceeded. Sleep {e.timeout} seconds.")
                time.sleep(e.timeout)
            except exceptions.TelegramAPIError:
                print(f"Error occurred while sending message to {CHAT_ID}")

    # Удаляем завершенные конкурсы из базы данных
    # for contest_id in contests_to_delete:
    #    contests.delete_one({"_id": contest_id})


async def resultEvent(contest):
    bot = Bot(token=cfg['token'])
    id_event = contest['_id']
    id_manager = int(contest['id_manager'])
    caption_event = contest['title']
    publish_text = contest['publish_text']
    photo = contest['photo']
    winners_count = contest['winners_count']
    additional_condition = ''
    try:
        additional_condition = contest['additional_condition']
    except Exception:
        pass

    pre_winners = await manager_db.getWinners(id_event=id_event)
    winners_id = randomizer.getDataWinners(winners_count, pre_winners)
    winners_print = ""
    for winner_id in winners_id:
        user = await user_db.getUser(winner_id)
        username = user['username']
        if username != None:
            if (additional_condition != ''):
                additional_condition_answer = user[additional_condition]
                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n<b>{additional_condition} -</b> {additional_condition_answer}"
            else:
                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> <a href='https://t.me/{username}?start=chat'>{username}</a>\n"
        else:
            if (additional_condition != ''):
                additional_condition_answer = user[additional_condition]
                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n<b>{additional_condition} -</b> {additional_condition_answer}"
            else:
                winners_print += f"<b>{winners_id.index(winner_id) + 1} МЕСТО:</b> {winner_id} (@имя отсутствует)\n"

    publish_text = f'''
<b>Подведение итогов</b>

<b>{caption_event}</b>

{publish_text}

<b>Количество победителей:</b> {len(winners_id)}

<b>Победители:</b>\n{winners_print}    
'''

    await bot.send_photo(id_manager, photo, caption=publish_text, parse_mode="HTML")
    await bot.send_message(id_manager, text=texts.publish_or_reroll_event,
                           reply_markup=manager_keyboards.publish_or_reroll_kb)
    await RerollOrPublishState.waiting_for_choice_action.set()


async def sendExcel(message, manager_id, excel_path):
    try:
        data = {}
        data[config.excel_fields[0]] = []
        data[config.excel_fields[1]] = []
        data[config.excel_fields[2]] = []
        data[config.excel_fields[3]] = []
        data[config.excel_fields[4]] = []
        data[config.excel_fields[5]] = []
        data[config.excel_fields[6]] = []
        # список каналов организатора
        channels = manager_db.getChannels(manager_id)
        try:
            channel = channels[0]
        except:
            await message.answer("У вас нет привязанных сообществ", reply_markup=manager_keyboards.statistic)
            return
        else:
            channel = channels[0]
            channel_info = await getChannelInfo(channel['channel_id'])
            channel_url = "https://t.me/" + channel_info.username
            # список айди конкурсов
            event_id_list = await manager_db.getEventIdList(channel_url)
            if not event_id_list:
                await message.answer("Вы ещё не проводили конкурсы", reply_markup=manager_keyboards.statistic)
            else:
                for event_id in event_id_list:
                    # список айди пользователей
                    activity_list = await manager_db.getActivitiesToExcel(event_id['_id'])
                    for activity in activity_list:
                        if activity['id_user'] not in data[config.excel_fields[1]]:
                            user = await user_db.getUser(activity['id_user'])
                            add_cond_value = ''
                            keys_list = list(activity.keys())
                            for key in keys_list:
                                if key not in config.activity_params:
                                    add_cond_value = f"{key} - {activity[key]}"
                                    break

                            data[config.excel_fields[0]].append(channel_url)
                            data[config.excel_fields[1]].append(activity['id_user'])
                            data[config.excel_fields[2]].append(user['full_name'])
                            data[config.excel_fields[3]].append(user['username'])
                            try:
                                data[config.excel_fields[4]].append(activity['phone'])
                            except:
                                data[config.excel_fields[4]].append(" ")
                            try:
                                data[config.excel_fields[5]].append(activity['email'])
                            except:
                                data[config.excel_fields[5]].append(" ")
                            try:
                                data[config.excel_fields[6]].append(add_cond_value)
                            except Exception as ex:
                                data[config.excel_fields[6]].append(" ")

        await excel_contoller.save_to_excel(data, manager_id)

        if os.path.exists(excel_path):
            # Upload the Excel file and attach it to a message
            document = types.InputFile(excel_path, filename=excel_path)
            caption = "Наш бот сформировал для вас файл с участниками ваших конкурсов"
            await bot.send_document(message.chat.id, document=document, caption=caption,
                                    reply_markup=manager_keyboards.statistic)

            excel_contoller.delete_excel(excel_path)
    except Exception as ex:
        print(ex)
        await message.answer("Ошибка при формировании документа: " + str(ex), reply_markup=manager_keyboards.statistic)


######################################################################
# АДМИНИСТРАТОР
######################################################################

async def sendAdminExcel(message, admin_id, excel_path):
    try:
        data = {}
        data[config.excel_fields[0]] = []
        data[config.excel_fields[1]] = []
        data[config.excel_fields[2]] = []
        data[config.excel_fields[3]] = []
        data[config.excel_fields[4]] = []
        data[config.excel_fields[5]] = []
        data[config.excel_fields[6]] = []

        # список каналов организатора
        channels = admin_db.getChannels()
        if not channels:
            await message.answer("Сообществ не обнаружено", reply_markup=admin_keyboards.a_start_kb)
        else:
            activity_list = await admin_db.getAllActivities()
            for activity in activity_list:
                user = await user_db.getUser(activity['id_user'])
                add_cond_value = ''
                keys_list = list(activity.keys())
                for key in keys_list:
                    if key not in config.activity_params:
                        add_cond_value = f"{key} - {activity[key]}"
                        break

                event = await admin_db.getIdManager(activity['id_event'])

                channel = await admin_db.getChannel(event['id_manager'])
                channel_info = await getChannelInfo(channel['channel_id'])
                channel_url = "https://t.me/" + channel_info.username

                data[config.excel_fields[0]].append(channel_url)
                data[config.excel_fields[1]].append(activity['id_user'])
                data[config.excel_fields[2]].append(user['full_name'])
                data[config.excel_fields[3]].append(user['username'])
                try:
                    data[config.excel_fields[4]].append(activity['phone'])
                except:
                    data[config.excel_fields[4]].append(" ")
                try:
                    data[config.excel_fields[5]].append(activity['email'])
                except:
                    data[config.excel_fields[5]].append(" ")
                try:
                    data[config.excel_fields[6]].append(add_cond_value)
                except Exception as ex:
                    data[config.excel_fields[6]].append(" ")

        await excel_contoller.save_to_excel(data, admin_id)

        if os.path.exists(excel_path):
            # Upload the Excel file and attach it to a message
            document = types.InputFile(excel_path, filename=excel_path)
            caption = "Пожалуйста, статистика по всем участникам"
            await bot.send_document(message.chat.id, document=document, caption=caption)

            excel_contoller.delete_excel(excel_path)


    except Exception as ex:
        print(ex)


def register():
    dp.register_message_handler(start, commands="start")
    dp.register_message_handler(admin, commands="admin")
    dp.register_message_handler(user, commands="user")
    dp.register_message_handler(manager, commands="manager")
    dp.register_message_handler(keyboard_handler, state=None)
    dp.register_callback_query_handler(inline_help_buttons_handler)
    dp.register_callback_query_handler(inline_help_buttons_handler,
                                       state=RerollOrPublishState.waiting_for_choice_action)
    dp.register_callback_query_handler(inline_help_buttons_handler, state=RerollOrPublishState.waiting_for_reroll)
    dp.register_callback_query_handler(inline_help_buttons_handler, state=MyEvents.my_events)
    dp.register_message_handler(handle_contact, content_types=types.ContentType.CONTACT)

    # переход в состояние ввода почты
    dp.register_message_handler(handle_email, state=Email.waiting_for_email)

    dp.register_message_handler(handle_add_data, state=AddData.waiting_for_add_data)

    # переход в состояние ввода капчи
    dp.register_message_handler(handle_captcha, state=Captcha_state.waiting_for_captcha)
    dp.register_message_handler(sendCaptcha, state=Captcha_state.send_captcha)

    # переход в состояние создания конкурса
    dp.register_message_handler(handle_conditions, state=EventState.waiting_for_conditions)
    dp.register_message_handler(handle_chanell_url, state=EventState.waiting_for_chanell_url)
    dp.register_message_handler(handle_title, state=EventState.waiting_for_title)
    dp.register_message_handler(handle_description, state=EventState.waiting_for_description)
    dp.register_message_handler(handle_photo, state=EventState.waiting_for_photo, content_types=['any'])
    dp.register_message_handler(handle_add_condition, state=EventState.waiting_for_add_condition)
    dp.register_message_handler(handle_winners_count, state=EventState.waiting_for_winners_count)
    dp.register_message_handler(handle_time_interval, state=EventState.waiting_for_time_interval)
    dp.register_message_handler(handle_duration, state=EventState.waiting_for_duration)
    dp.register_message_handler(handle_publish_text, state=EventState.waiting_for_publish_text)
    dp.register_message_handler(handle_event_publish, state=EventState.waiting_for_publish)
    dp.register_message_handler(handle_edit_field, state=EventState.waiting_for_edit_field)

    dp.register_message_handler(handle_publish_results, state=RerollOrPublishState.waiting_for_choice_action)
    # dp.register_message_handler(handle_reroll_results, state=RerollOrPublishState.waiting_for_reroll)

    dp.register_message_handler(handle_reroll_numbers, state=RerollNumberState.waiting_for_number_winners)

    dp.register_message_handler(handle_my_events_folder, state=MyEvents.my_events)

    dp.register_message_handler(handle_control_events, state=ControlEvents.control_events)

    dp.register_message_handler(handle_manager_statistic, state=ManagerStatistic.manager_statistic)

    dp.register_message_handler(handle_security_folder, state=SecurityState.securuty)

    dp.register_message_handler(handle_addBotToChannel, state=addBotToChannelState.waiting_for_id_channel)


register()

# запускаем приложение aiogram
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=u'%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s',
    )
    # Регистрируем задачу в расписании
    schedule.every(10).seconds.do(check_for_new_contests)

    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=asyncio.run, args=(dp.start_polling(None, None, None, None, True),))
    bot_thread.start()

    # Бесконечный цикл, в котором выполняется проверка расписания и обработка задач
    while True:
        schedule.run_pending()
        time.sleep(1)

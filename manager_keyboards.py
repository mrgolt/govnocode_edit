from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
import config

manager_start_kb = ReplyKeyboardMarkup(resize_keyboard=True)
manager_languages_kb = ReplyKeyboardMarkup(resize_keyboard=True)
manager_subscription_kb = ReplyKeyboardMarkup(resize_keyboard=True)
manager_channels_events_kb = ReplyKeyboardMarkup(resize_keyboard=True)
manager_channels_security_kb = ReplyKeyboardMarkup(resize_keyboard=True)
manager_channels_create_event_conditions_kb = ReplyKeyboardMarkup(resize_keyboard=True)

language = InlineKeyboardMarkup(row_width=4)
language_rus = InlineKeyboardButton("RUS", callback_data="manager_rus")
language_eng = InlineKeyboardButton("ENG", callback_data="manager_eng")
language_hindi = InlineKeyboardButton("Хинди", callback_data="manager_hindi")
language_china = InlineKeyboardButton("Китай", callback_data="manager_china")
language_back = InlineKeyboardButton("Назад", callback_data="language_back")

language.insert(language_rus)
language.insert(language_eng)
language.insert(language_hindi)
language.insert(language_china)
language.insert(language_back)

# клавиатура из кнопки "Назад"
exit_create_event = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
exit_create_event.add("Назад").add("Выйти из создания конкурса")

# клавиатура из кнопки "Назад" на этапе выбора канала
exit_create_event_1 = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
exit_create_event_1.row('1️⃣').add("Выйти из создания конкурса")

# клавиатура из кнопки "Назад" на этапе выбора канала
exit_create_event_2 = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
exit_create_event_2.row('1️⃣', '2️⃣').add("Выйти из создания конкурса")

# клавиатура из кнопки "Назад" на этапе выбора канала
exit_create_event_3 = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
exit_create_event_3.row('1️⃣', '2️⃣', '3️⃣').add("Выйти из создания конкурса")

# клавиатура интервалов времени
duration_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
duration_kb.row(config.time_intervals[0], config.time_intervals[1], config.time_intervals[2]).add("Назад").add("Выйти из создания конкурса")

# клавиатура выбора публикации
publish_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
publish_kb.row(config.publish_choice[0], config.publish_choice[1]).add("Назад").add("Выйти из создания конкурса")

# клавиатура выбора публикации
edit_event_field_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
edit_event_field_kb.row(config.event_fields[0], config.event_fields[1], config.event_fields[2]).add(config.event_fields[3], config.event_fields[4], config.event_fields[5]).add(config.event_fields[6], config.event_fields[7]).add(config.event_fields[8]).add("Назад").add("Выйти из создания конкурса")

# клавиатура публикации или реролла
publish_or_reroll_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
publish_or_reroll_kb.row(config.reroll_or_publish_event[0]).add(config.reroll_or_publish_event[1], config.reroll_or_publish_event[2]).add(config.reroll_or_publish_event[3])

# клавиатура из кнопки "Назад"
back = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
back.add("Назад")

# клавиатура из кнопки "Назад"
support_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
support_kb.add("FAQ").add("Назад")

# клавиатура из кнопки "Назад"
back_and_main_menu_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
back_and_main_menu_kb.add("Назад").add('Главное меню')

# клавиатура из кнопки "Главное меню"
main_menu= ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
main_menu.add("Главное меню")

# плавающие кнопки для подведения итогов в конкурсах (макс 3)
random = InlineKeyboardMarkup(row_width=1).add(InlineKeyboardButton("Подвести итоги", callback_data="random"))

# плавающая кнопка для участия в конкурсе
take_part = InlineKeyboardMarkup().add(InlineKeyboardButton("Получить ссылку на конкурс", callback_data="copy_link"))

manager_start_kb.row(
    'Добавить канал').add(
    'Создать новый конкурс').add(
    'Панель управления').add(
    'Написать в поддержку')

manager_languages_kb.row(
    'RUS').add(
        'ENG', 'Хинди', 'Китай')

manager_my_events = ReplyKeyboardMarkup(resize_keyboard=True)
manager_my_events.add("Действующие", "Требующие подведения").add("Завершенные").add("Назад").add("Главное меню")

statistic = ReplyKeyboardMarkup(resize_keyboard=True)
statistic.add("Назад").add("Главное меню")

manager_control_panel = ReplyKeyboardMarkup(resize_keyboard=True)
manager_control_panel.add('Мои конкурсы', 'Статистика').add("Назад")

# условия конкурса
manager_channels_create_event_conditions_kb.row('1️⃣', '2️⃣').add('3️⃣', '4️⃣', '5️⃣').add('Выйти из создания конкурса')

manager_channels_security_kb.row(
    'Чат', 'Канал', 'Всё').add(
        'Стоп слова', 'Запрет ссылок').add(
            'Капча при добавлении на канал', 'Предупреждение (1 из 3)').add(
    'Назад', 'Главное меню')

manager_subscription_kb.add('Добавить канал').add('Назад')

get_access_six_month = ReplyKeyboardMarkup(resize_keyboard=True)
get_access_six_month.add("Написать в поддержку").add("Назад")
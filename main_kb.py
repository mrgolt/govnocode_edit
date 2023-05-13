import re
from transliterate import translit

# Читаем исходный файл
with open('manager_keyboards.py', 'r', encoding='utf8') as f:
    source_code = f.read()

# Находим все строки с русским текстом в кавычках

patterns = [
    #r"InlineKeyboardButton\((['\"]{1}[а-яА-Я\s]*?['\"]){1},"
    r"(['\"]{1}[.а-яА-ЯёЁ\s]*?['\"]{1})"
            ]

for pattern in patterns:
    strings = re.findall(pattern, source_code)

    # Создаем новый файл для инициализации переменных
    with open('kb_2.py', 'w', encoding='utf8') as new_file:
        # Создаем новый файл для присвоения переменных
        with open('ru.ftl', 'a', encoding='utf8') as assign_file:
            existing_variables = set()  # Множество для отслеживания существующих переменных
            for i, string in enumerate(strings):
                text = string.strip("'\"")  # Значение переменной (русский текст в кавычках)

                # Транслитерируем текст
                variable_name = translit(text, 'ru', reversed=True)

                # Удаляем все символы, кроме букв, цифр и знаков подчеркивания
                variable_name = re.sub(r'[^a-zA-Z0-9_]', '', variable_name)

                # Если имя переменной становится пустым, добавляем суффикс "_text"
                if not variable_name:
                    variable_name = f'text_{i}'

                # Проверяем, что переменная не была уже записана в файл
                if variable_name not in existing_variables:
                    # Формируем строку вида "имя_переменной = значение_переменной"
                    pattern = r"(['\"])(.*?)(\1)"
                    variable_assignment = f'{variable_name} = \n    {re.sub(pattern, lambda match: match.group(2), string)}\n'

                    # Записываем присвоение значения переменной в файл присвоения переменных
                    assign_file.write(variable_assignment)

                    # Добавляем переменную в множество существующих переменных
                    existing_variables.add(variable_name)

                # Заменяем текст в исходном коде на вызов функции translate.get()
                source_code = source_code.replace(string, f"translate.get(key='{variable_name}')\n")

            # Записываем остаток исходного кода в новый файл
            new_file.write(source_code)

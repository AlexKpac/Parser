import re
import io
import csv
import requests
import configparser
import time
import os
from datetime import datetime
import multiprocessing
from enum import Enum, auto

import telebot
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

import bd
import header as h

# Получить все модели телефона по частичному названию
get_products_query = """
    SELECT id_product, brand_name, model_name
    FROM products_table
    WHERE CONCAT(brand_name, ' ', model_name) LIKE '%%' || %s || '%%' 
"""

# Получить версии телефона по его id_prod
get_versions_query = """
    SELECT id_ver_phone, ram, rom
    FROM versions_phones_table
    WHERE id_product = %s
"""
# Получить все актуальные данные по id версии
get_all_act_data_by_id_ver_query = """
    SELECT price, id_shop_name, color, general_table.url_product
    FROM general_table
    JOIN (
        SELECT url_product, MAX(datetime) as MaxDate 
        FROM general_table
        WHERE id_ver_phone = %s
        GROUP BY url_product
    ) AS group_table
    ON general_table.datetime = group_table.MaxDate AND 
       general_table.url_product = group_table.url_product
    ORDER BY price
"""

# Поиск всех цен (исторических) по названию бренда, модели, ROM и RAM и сортировка по убыванию
search_all_prices_by_version_query = """
    SELECT price, id_shop_name, color, datetime, general_table.url_product
    FROM general_table
    WHERE id_ver_phone = %s
    ORDER BY datetime DESC
"""

# Поиск всех цен (исторических) по названию бренда, модели, ROM и RAM и сортировка по убыванию
search_model_info_by_version_query = """
    SELECT brand_name, model_name, ram, rom, img_url
    FROM general_table
    WHERE id_ver_phone = %s
    LIMIT 1
"""

TEXT_NO_RESULT_IN_BD = ':(\nНет совпадений в базе, проверьте правильность ввода или попробуйте найти другую модель'
TEXT_TOO_MANY_RESULTS_FROM_DB = ':(\nНайдено слишком много совпадений, попробуйте уточнить модель получше'
TEXT_OUT_RESULT_FROM_DB = 'Вот что я нашел по вашему запросу, выберите нужную модель:'
TEXT_AN_ERROR_HAS_OCCURRED = ':((\nПроизошла ошибка, повторите запрос еще раз'
TEXT_SELECT_VERSION = "На модель <b>{}</b> имеется несколько комплектаций, выберите подходящую:"
TEXT_NOT_FOUND = ":(\nНичего не найдено, попробуйте запросить другую модель"
TEXT_HELLO = 'Приветствую тебя, новый пользователь!'
TEXT_HELLO_AGAIN = 'Сервис уже запущен. Если непонятно что делать, введи /help'
TEXT_HELP = '<b>Краткая инструкция</b>\n\n' \
            'Этого бота нужно использовать для поиска информации о смартфонах: их <b>цен и наличия</b> в разных ' \
            'магазинах, <b>графики изменения цен</b> и расширенные <b>истории изменения цен</b> в текстовом виде.\n\n' \
            'Всё что от вас требуется - <b>написать в этот чат название интересующей модели</b>, не обязательно ' \
            'в полном виде. Бот вас поймет, а если нет, то задаст пару уточняющих вопросов, чтобы ' \
            'точно определиться с вашими пожеланиями.\n\n' \
            'После всех уточнений бот пришлет сообщение со списком актуальных цен в разных магазинах. ' \
            'Цены указаны с учетом наличия и отсортированы <b>по возрастанию</b>.\n\n' \
            'Также обратите внимание, что под сообщением располагаются <b>кнопки</b>: кнопка выбора страницы (если данные не ' \
            'поместились в один пост) и кнопка "дополнительные опции". Последняя открывает доступ ' \
            'к двум функциям: посмотреть <b>график изменения цены</b> и загрузить <b>расширенный ' \
            'файл истории цен.</b>'

PATH_HISTORY_FILE = 'history/'
PATH_CHARTS = 'charts/'

BUTTON_ACTUAL_TEXT = "Актуальные цены"
BUTTON_CHART_TEXT = "График прошлых цен"
BUTTON_HISTORY_TEXT = "Подробная история цен"
BUTTON_SHOW_ALL_OPT_TEXT = "Дополнительные опции"

TOKEN = '1533268483:AAHIoxsy1cKUz5eHVLLeaxPdO5WDgsJI7WU'
MAX_OFFER_MODELS = 15
MAX_LEN_TEXT = 3000
DN = True
DNR = False

USERS_KNOWN = []
USERS_STAT_REQ = {}
USERS_ACTUAL_TEXT = {}
USERS_LAST_MSG = {}
USERS_LAST_OFFER_ID = {}
USERS_CUR_MODEL_INFO = {}
USERS_DISABLE_DOWNLOAD = {}
USERS_OPEN_ALL_OPTIONS = {}

bot = telebot.TeleBot(TOKEN)
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}

q = multiprocessing.Queue()


# Вывод ошибки в лог и в чат
def print_error(chat_id, error_text):
    print(error_text)
    bot.send_message(chat_id, TEXT_AN_ERROR_HAS_OCCURRED)


# Чтение словаря исключений названий моделей
def load_exceptions_model_names_telegram():
    with open(h.EXCEPT_MODEL_NAMES_TELEGRAM_PATH, 'r', encoding='UTF-8') as f:
        for line in f:
            res = re.findall(r"\[.+?]", line)
            # Отсечь кривые записи
            if len(res) != 2:
                continue
            # Добавить в словарь
            EXCEPT_MODEL_NAMES_TELEGRAM_DICT[res[0].replace('[', '').replace(']', '')] = \
                res[1].replace('[', '').replace(']', '')


# Поиск в строке названия фраз из списка исключения и их замена
def find_and_replace_except_model_name(model_name):
    if not EXCEPT_MODEL_NAMES_TELEGRAM_DICT:
        return model_name

    for key, value in EXCEPT_MODEL_NAMES_TELEGRAM_DICT.items():
        if key in model_name:
            model_name = model_name.replace(key, value)

    return model_name


# Удалить последний оффер, если пользователь ввел новый запрос
def delete_last_offer(chat_id):
    id_last_offer = USERS_LAST_OFFER_ID.get(chat_id)
    if not id_last_offer:
        print("НЕТ ID ОФФЕРА ДЛЯ УДАЛЕНИЯ")
        return

    try:
        bot.delete_message(chat_id=chat_id, message_id=id_last_offer)
    except telebot.apihelper.ApiTelegramException as e:
        USERS_LAST_OFFER_ID[chat_id] = 0
        print('delete_last_offer = {}'.format(e))


# Конвертировать URL для реферальной ссылки
def convert_url_for_ref_link(url):
    return url.replace(':', '%3A').replace('/', '%2F').strip()


# Получить реферальную ссылку
def get_ref_link(url):
    # Мвидео
    if 'mvideo.ru' in url:
        return 'https://ad.admitad.com/g/c9f1ad68bcd7a46ff3053a3184f61a/?ulp=' + convert_url_for_ref_link(url)
    # МТС
    if 'mts.ru' in url:
        return 'https://ad.admitad.com/g/eca1415c7dd7a46ff3051ebfd6fcfa/?ulp=' + convert_url_for_ref_link(url)
    # Ситилинк
    if 'citilink.ru' in url:
        return 'https://ad.admitad.com/g/bl69o59ui4d7a46ff3052b16fb31c7/?ulp=' + convert_url_for_ref_link(url)
    # Эльдорадо
    if 'eldorado.ru' in url:
        return 'https://ad.admitad.com/g/uvkws8py62d7a46ff305824224cf5a/?ulp=' + convert_url_for_ref_link(url)

    return url


# Получить уникальные значения из списка
def get_unique_numbers(value_list):
    unique = []
    for value in value_list:
        if value not in unique:
            unique.append(value)
    return unique


# Группировка файлов расширенной истории по цветам
def history_group_color(res_list):
    pos_price, pos_shop, pos_color, pos_date, pos_url = 0, 1, 2, 3, 4

    grouped_res_list = []
    while res_list:
        item_0 = res_list[0]
        grouped_list = []

        for item in res_list:
            if (item_0[pos_date] - item[pos_date]).seconds < 2 and item[pos_price] == item_0[pos_price]:
                grouped_list.append(item)
            else:
                break

        # Удаляем уже сгруппированные элементы из исходного списка
        for it in grouped_list:
            res_list.remove(it)

        # Группировка элементов по цвету
        colors = ', '.join(col[pos_color].title() for col in grouped_list)
        grouped_res_list.append(
            (grouped_list[0][pos_price], grouped_list[0][pos_shop], colors, grouped_list[0][pos_date]))

    return grouped_res_list


# Получение всех соответствий моделей из базы на основе того, что ввел пользователь
def search_models_in_db(user_request):
    text = user_request.lower().strip()
    brand_name = text.split()[0]
    model_name = text.replace(brand_name, '').strip()

    full_name = '{} {}'.format(brand_name, model_name).strip().replace(' ', '%')
    print('full_name = "{}"'.format(full_name))
    # Получение значений из БД и формирование списка
    res = db.execute_read_query(get_products_query, (full_name,))
    search_res_list = [(id, '{} {}'.format(brand, model)) for id, brand, model in res]

    return search_res_list


# -------------------------------- СТАТИСТИКА -------------------------------- #

# Увеличить счетчик статистики запросов пользователя
def inc_user_stat_req(user_id):
    if user_id in USERS_STAT_REQ:
        USERS_STAT_REQ[user_id] += 1
    else:
        USERS_STAT_REQ[user_id] = 1

    for key, value in USERS_STAT_REQ.items():
        print('user "{}" -> {}'.format(key, value))


# -------------------------------- СОЗДАНИЕ КЛАВИАТУР -------------------------------- #

# Получить клавиатуру для поста с актуальными ценами
def get_actual_keyboard(message, id_ver, cur_page, max_page):
    add_options_keys = InlineKeyboardMarkup(row_width=1)

    # Проверка запрета кнопки скачивать историю
    message_id = USERS_DISABLE_DOWNLOAD.get(message.chat.id)
    dis_hist = message_id and message_id == message.id

    # Проверка всегда развернутого меню
    message_id = USERS_OPEN_ALL_OPTIONS.get(message.chat.id)
    always_open = message_id and message_id == message.id

    # ГЕНЕРАЦИЯ КЛАВИАТУРЫ
    # Пагинация: опцинально, если есть страницы
    if max_page > 1:
        add_options_keys.add(InlineKeyboardButton("Страница {}".format(((cur_page + 1) % max_page) + 1),
                                                  callback_data="options_next,{},{}".format(id_ver, cur_page)))
    # 2 варианта: скрытое меню или развернутое
    if not always_open:
        # Обязательная кнопка с доп. опциями
        add_options_keys.add(InlineKeyboardButton("Дополнительные опции",
                                                  callback_data="options_show,{},{},{}".
                                                  format(id_ver, cur_page, max_page)))
    else:
        # График - обязательно
        add_options_keys.add(
            InlineKeyboardButton(BUTTON_CHART_TEXT, callback_data="options_chart,{}".format(id_ver)))

        # Загрузить историю: опцинально, если еще не запрашивалась для этого сообщения
        if not dis_hist:
            add_options_keys.add(
                InlineKeyboardButton(BUTTON_HISTORY_TEXT,
                                     callback_data="options_history,{},{},{}".format(id_ver, cur_page, max_page)))

    return add_options_keys


# Получить клавиатуру для поста с графиком
def get_chart_keyboard(id_ver):
    keys = InlineKeyboardMarkup(row_width=1)
    keys.add(InlineKeyboardButton("Назад", callback_data="options_back,{}".format(id_ver)))

    return keys


# -------------------------------- ГЕНЕРАЦИЯ ТЕКСТОВ -------------------------------- #

# Генерация текста для заголовка
def generating_header(model_info):
    pos_brand, pos_model, pos_ram, pos_rom, pos_img = 0, 1, 2, 3, 4

    # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
    header = find_and_replace_except_model_name('<b>Смартфон {} {}</b>\n'.format(
        model_info[pos_brand].title(), model_info[pos_model].title()))

    # КОМПЛЕКТАЦИЯ
    header += '<b>{}/{} GB</b>\n'.format(model_info[pos_ram], model_info[pos_rom]) \
        if (model_info[pos_ram] and model_info[pos_brand] != 'apple') \
        else '<b>{} GB</b>\n'.format(model_info[pos_rom])

    return header


# Генерация текста для актуальных цен
def generating_actual_text(model_info, prod_list):
    pos_price, pos_shop, pos_color, pos_url = 0, 1, 2, 3
    # Генерация заголовка
    header = generating_header(model_info)
    # Получение уникального списка названий магазинов, не изменяя сортировку
    shops_set = get_unique_numbers([item[pos_shop] for item in prod_list])

    text = ''
    texts_list = []
    for shop in shops_set:
        urls = ''
        for product in prod_list:
            if product[pos_shop] == shop:
                urls += '► <b>{}</b> ₽ - <a href="{}">{}</a>\n'.format(f'{product[pos_price]:,}'.replace(',', ' '),
                                                                       get_ref_link(product[pos_url]),
                                                                       product[pos_color].title())
        # Генерация поста
        text += '\nЦены в <b>{}</b>:\n'.format(h.TRUE_SHOP_NAMES[shop - 1])
        text += urls

        # Если размер текущего текста больше дозволенного - добавление в список для разных страниц
        if len(text) > MAX_LEN_TEXT:
            texts_list.append(header + text)
            text = ''

    # Если что-то осталось - добавляем в список
    texts_list.append(header + text)

    return texts_list


# Генерация файла с расширенной историей цен
def generating_history_text(prod_list):
    pos_price, pos_shop, pos_color, pos_date, pos_url = 0, 1, 2, 3, 4
    # Получение уникального списка названий магазинов
    shops_set = list(set(item[pos_shop] for item in prod_list))

    text = ''
    for shop in shops_set:
        prod_one_shop_list = []
        for product in prod_list:
            if product[pos_shop] == shop:
                prod_one_shop_list.append(product)

        grouped_list = history_group_color(prod_one_shop_list)

        text += '\nИстория цен в {}:\n'.format(h.TRUE_SHOP_NAMES[shop - 1])
        for item in grouped_list:
            text += '{} - {} ₽ ({})\n'.format(item[pos_date].strftime("%d.%m.%Y %H:%M"), item[pos_price],
                                              item[pos_color])

    text += '\n\n\nОтчет подготовлен с помощью @ProdavachAssistantBot\n{}'.format(
        datetime.now().strftime('%d.%m.%Y %H:%M'))

    return text


# Сгенерировать файл полной истории цен
def generate_full_history_file(chat_id, id_ver):
    model_info = USERS_CUR_MODEL_INFO.get(chat_id)
    if not model_info:
        print_error(chat_id, "НЕ УДАЛОСЬ ПОЛУЧИТЬ ДАННЫЕ О МОДЕЛИ В СЛОВАРЕ")
        return

    # Получить все цены модели
    prod_list = db.execute_read_query(search_all_prices_by_version_query, (id_ver,))
    if not prod_list:
        print_error(chat_id, "НЕ ПОЛУЧИЛОСЬ ЗАПРОСИТЬ ВСЕ ЦЕНЫ МОДЕЛИ")
        return

    header = generating_header(model_info).replace('<b>', '').replace('</b>', '')
    texts_list = generating_history_text(prod_list)

    # Создание файла и отправка
    file_name = '{}{}-{}.txt'.format(PATH_HISTORY_FILE, chat_id, id_ver)
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write(header + texts_list)

    bot.send_document(chat_id, open(file_name, 'rb'), caption='<b>{}</b>'.format(header), parse_mode='html')

    # Удаление файла с диска
    if os.path.isfile(file_name):
        os.remove(file_name)
        print("ФАЙЛ ИСТОРИИ УСПЕШНО УДАЛЕН")
    else:
        print("НЕ УДАЛОСЬ УДАЛИТЬ ФАЙЛ ИСТОРИИ")


# -------------------------------- ОФФЕРЫ -------------------------------- #

# Предложить выбрать одну из моделей, название которой похоже на то, что ввел пользователь
def offer_model_for_user(message, products_list):
    models_keys = InlineKeyboardMarkup(row_width=1)
    for item in products_list:
        true_name = find_and_replace_except_model_name(item[1].title())
        models_keys.add(InlineKeyboardButton(true_name, callback_data='model,{},{}'.format(item[0], true_name)))

    models_keys.add(InlineKeyboardButton('Выход', callback_data='model,exit'))
    resp = bot.send_message(message.chat.id, TEXT_OUT_RESULT_FROM_DB, reply_markup=models_keys, disable_notification=DN)

    # Добавить id оффера в словарь
    USERS_LAST_OFFER_ID[message.chat.id] = resp.id


# Предложить пользователю выбрать версию, если их больше, чем одна
def offer_version_for_user(message, full_name, versions_list):
    versions_keys = InlineKeyboardMarkup()
    for ver in versions_list:
        text_button = '{}/{} Gb (RAM/ROM)'.format(ver[1], ver[2]) if ver[1] else '{} Gb (ROM)'.format(ver[2])
        versions_keys.add(InlineKeyboardButton(text_button, callback_data='version,' + str(ver[0])))

    versions_keys.add(InlineKeyboardButton('Выход', callback_data='version,exit'))
    resp = bot.send_message(message.chat.id, TEXT_SELECT_VERSION.format(full_name), parse_mode='html',
                            reply_markup=versions_keys, disable_notification=DN)

    # Добавить id оффера в словарь
    USERS_LAST_OFFER_ID[message.chat.id] = resp.id


# -------------------------------- ВЫВОД РЕЗУЛЬТАТОВ -------------------------------- #

# Вывод первоначального поста
def print_post(message, id_ver):
    # Получить всю информацию о модели
    model_info = db.execute_read_query(search_model_info_by_version_query, (id_ver,))
    if not model_info:
        print_error(message.chat.id, "НЕ ПОЛУЧИЛОСЬ ЗАПРОСИТЬ ИНФОРМАЦИЮ О МОДЕЛИ")
        return

    # Удалить у предыдущего поста клавиатуру
    id_last_msg = USERS_LAST_MSG.get(message.chat.id)
    if id_last_msg:
        bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=id_last_msg, reply_markup=None)

    # Т.к. офферы удалились, обнуляем их id в словаре
    USERS_LAST_OFFER_ID[message.chat.id] = 0
    # Заполнение словаря с информацией о текущей модели
    USERS_CUR_MODEL_INFO[message.chat.id] = model_info[0]
    # Т.к. это новый пост, очистить историю
    USERS_ACTUAL_TEXT[message.chat.id] = ''

    # Т.к. главный пост - это пост с актуальными ценами, то вывод его
    give_actual_price(message, id_ver, edit=False)


# Отображение только актуальных цен
def give_actual_price(message, id_ver, edit=False):
    # Получить название модели
    model_info = USERS_CUR_MODEL_INFO.get(message.chat.id)
    if not model_info:
        print_error(message.chat.id, "СЛОВАРЬ С ИНФОРМАЦИЕЙ МОДЕЛИ ПУСТ")
        return

    # Получить текст. Если его нет (первый запуск) - значит сгенерировать
    texts_list = USERS_ACTUAL_TEXT.get(message.chat.id)
    if not texts_list:
        # Получить все актуальные цены модели
        prod_list = db.execute_read_query(get_all_act_data_by_id_ver_query, (id_ver,))
        if not prod_list:
            print_error(message.chat.id, "НЕ ПОЛУЧИЛОСЬ ЗАПРОСИТЬ АКТУАЛЬНЫЕ ЦЕНЫ МОДЕЛИ")
            return

        texts_list = generating_actual_text(model_info, prod_list)
        # Сохранить новый текст в словарь
        USERS_ACTUAL_TEXT[message.chat.id] = texts_list

    # Генерация поста
    text = texts_list[0]
    max_page = len(texts_list)
    if max_page > 1:
        text += "\nСтраница <b>{}</b> из <b>{}</b>".format(1, max_page)

    # В зависимости от флага пост или выкладывается или редактируется
    if edit:
        bot.edit_message_media(chat_id=message.chat.id, message_id=message.id,
                               reply_markup=get_actual_keyboard(message, id_ver, 0, max_page),
                               media=types.InputMediaPhoto(media=model_info[4], caption=text, parse_mode='html'))
    else:
        resp = bot.send_photo(chat_id=message.chat.id, photo=model_info[4], caption=text, parse_mode='html',
                              reply_markup=get_actual_keyboard(message, id_ver, 0, max_page), disable_notification=DNR)

        # Добавление id текущего поста в словарь
        USERS_LAST_MSG[message.chat.id] = resp.id


# Отображение детальной истории цен
def give_detailed_price_history(message, id_ver, cur_page, max_page):
    generate_full_history_file(message.chat.id, id_ver)
    USERS_DISABLE_DOWNLOAD[message.chat.id] = message.id

    bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=message.id,
                                  reply_markup=get_actual_keyboard(message, id_ver, cur_page, max_page))


# Отображение графика исторических цен
def give_price_chart(message, id_ver):
    photo = open('charts/olo.jpg', 'rb')
    text = '<b>text</b>'

    bot.edit_message_media(chat_id=message.chat.id, message_id=message.id, reply_markup=get_chart_keyboard(id_ver),
                           media=types.InputMediaPhoto(media=photo, caption=text, parse_mode='html'))


# Обновление постов при нажатии на кнопки пагинации
def give_next_page(message, id_ver, prev_page):
    text = USERS_ACTUAL_TEXT.get(message.chat.id)

    if not text or type(prev_page) != int:
        print("В NEXT PAGE ACTUAL НЕТ ТЕКСТА ИЛИ ОШИБКА СТРАНИЦЫ")
        return

    max_page = len(text)
    cur_page = (prev_page + 1) % max_page
    new_text = text[cur_page]
    keys = get_actual_keyboard(message, id_ver, cur_page, max_page)

    # Если текст разбит на несколько блоков - вывести кнопку и дополнить текст
    if max_page > 1:
        new_text += "\nСтраница <b>{}</b> из <b>{}</b>".format(cur_page + 1, max_page)

    # Редактирование поста
    bot.edit_message_caption(chat_id=message.chat.id, message_id=message.id, caption=new_text, parse_mode='html',
                             reply_markup=keys)


# Отображение дополнительных кнопок при нажатии на кнопку "Дополнительные опции"
def give_all_options(message, id_ver, cur_page, max_page):

    bot.edit_message_reply_markup(message.chat.id, message.id,
                                  reply_markup=get_actual_keyboard(message, id_ver, cur_page, max_page))


# -------------------------------- ОБРАБОТКА КОМАНД ОЧЕРЕДИ -------------------------------- #

def cmd_text_start(message):
    user_id = message.chat.id

    if user_id not in USERS_KNOWN:
        print("Новый пользователь = {}".format(user_id))
        USERS_KNOWN.append(user_id)
        bot.send_message(user_id, TEXT_HELLO)
        help_command(message)
    else:
        bot.send_message(user_id, TEXT_HELLO_AGAIN)


# -------------------------------- ХЭНДЛЕРЫ -------------------------------- #

@bot.message_handler(commands=['start'])
def start_command(message):
    q.put([Cmd.text_start, message, ()])


@bot.message_handler(commands=['stop'])
def stop_command(message):
    bot.send_message(message.chat.id, 'stop ok')


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, TEXT_HELP, parse_mode='html')


@bot.message_handler(content_types=['text'])
def text_messages(message):
    bot.send_chat_action(message.chat.id, 'typing')
    inc_user_stat_req(message.chat.id)
    products_list = search_models_in_db(message.text)
    delete_last_offer(message.chat.id)

    if not products_list:
        bot.send_message(message.chat.id, TEXT_NO_RESULT_IN_BD)
        USERS_LAST_OFFER_ID[message.chat.id] = 0
    elif len(products_list) > MAX_OFFER_MODELS:
        bot.send_message(message.chat.id, TEXT_TOO_MANY_RESULTS_FROM_DB)
        USERS_LAST_OFFER_ID[message.chat.id] = 0
    elif len(products_list) == 1:

        version_list = db.execute_read_query(get_versions_query, (int(products_list[0][0]),))
        if not version_list:
            print("СПИСОК КОМПЛЕКТАЦИЙ ПУСТ В text_messages")
            bot.send_message(message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        elif len(version_list) == 1:
            print_post(message, version_list[0][0])
        else:
            true_name = find_and_replace_except_model_name(products_list[0][1].title())
            offer_version_for_user(message, true_name, version_list)
    else:
        offer_model_for_user(message, products_list)


# Узнать какую модель телефона выбрал пользователь
@bot.callback_query_handler(func=lambda call: call.data.startswith('model'))
def models_list_callback(query):
    bot.answer_callback_query(query.id)
    bot.delete_message(query.message.chat.id, query.message.id)

    if 'exit' in query.data:
        return

    bot.send_chat_action(query.message.chat.id, 'typing')
    param = query.data.split(',')

    id_prod = param[1] if (param and len(param) > 1) else ''
    if not id_prod or not id_prod.isdigit:
        print("НЕКОРРЕКТНЫЙ ID_PROD В MODELS_CALLBACK")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        return
    else:
        id_prod = int(id_prod)

    # Получение всех версий по id_prod
    version_list = db.execute_read_query(get_versions_query, (id_prod,))
    if not version_list:
        print("СПИСОК КОМПЛЕКТАЦИЙ ПУСТ В models_list_callback")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
    elif len(version_list) == 1:
        version = version_list[0]
        print_post(query.message, version[0])
    else:
        offer_version_for_user(query.message, param[2], version_list)


# Узнать какую версию телефона выбрал пользователь
@bot.callback_query_handler(func=lambda call: call.data.startswith('version'))
def versions_list_callback(query):
    bot.answer_callback_query(query.id)
    bot.delete_message(query.message.chat.id, query.message.id)

    if 'exit' in query.data:
        return

    bot.send_chat_action(query.message.chat.id, 'typing')
    param = query.data.split(',')

    id_ver = param[1] if (param and len(param) > 1) else ''
    if not id_ver or not id_ver.isdigit:
        print("НЕКОРРЕКТНЫЙ ID_VER В VERSIONS_CALLBACK")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        return
    else:
        id_ver = int(id_ver)

    print_post(query.message, id_ver)


# Узнать какую версию телефона выбрал пользователь
@bot.callback_query_handler(func=lambda call: call.data.startswith('options'))
def options_list_callback(query):
    bot.answer_callback_query(query.id)
    bot.send_chat_action(query.message.chat.id, 'typing')

    param = query.data.split(',')
    command = param[0]
    id_ver = int(param[1])

    if 'back' in command:
        give_actual_price(query.message, id_ver, edit=True)
    elif 'next' in command:
        prev_page = int(param[2])
        give_next_page(query.message, id_ver, prev_page)
        bot.send_chat_action(query.message.chat.id, 'cancel')
    elif 'show' in command:
        USERS_OPEN_ALL_OPTIONS[query.message.chat.id] = query.message.id
        cur_page = int(param[2])
        max_page = int(param[3])
        give_all_options(query.message, id_ver, cur_page, max_page)
        bot.send_chat_action(query.message.chat.id, 'cancel')
    elif 'chart' in command:
        give_price_chart(query.message, id_ver)
    elif 'history' in command:
        cur_page = int(param[2])
        max_page = int(param[3])
        give_detailed_price_history(query.message, id_ver, cur_page, max_page)
    else:
        print("НЕКОРРЕКТНЫЙ OPTIONS")
        return


##############
# [command, message, (args)]
# args = (id_ver, cur_page, max_page, )
# [commands]:
# - text_start
# - text_help
# - text_stop
# - text_req
# - offer_model
# - offer_version
# - but_back
# - but_page
# - but_show
# - but_chart
# - but_history

class Cmd(Enum):
    text_start = auto()
    text_help = auto()
    text_stop = auto()
    text_req = auto()
    offer_model = auto()
    offer_version = auto()
    but_back = auto()
    but_page = auto()
    but_show = auto()
    but_chart = auto()
    but_history = auto()


def queue_event_handling(queue):
    pos_cmd, pos_msg, pos_args = 0, 1, 2
    while True:
        if not queue.empty():
            param = queue.get()
            cmd = param[pos_cmd]
            message = param[pos_msg]
            args = param[pos_args]

            if param[pos_cmd] == Cmd.text_start:
                print("--text_start")
                cmd_text_start(message)
            elif param[pos_cmd] == Cmd.text_help:
                print("--text_help")
            elif param[pos_cmd] == Cmd.text_stop:
                print("--text_stop")
            elif param[pos_cmd] == Cmd.text_req:
                print("--text_req")
            elif param[pos_cmd] == Cmd.offer_model:
                print("--offer_model")
            elif param[pos_cmd] == Cmd.offer_version:
                print("--offer_version")
            elif param[pos_cmd] == Cmd.but_back:
                print("--but_back")
            elif param[pos_cmd] == Cmd.but_page:
                print("--but_page")
            elif param[pos_cmd] == Cmd.but_show:
                print("--but_show")
            elif param[pos_cmd] == Cmd.but_chart:
                print("--but_chart")
            elif param[pos_cmd] == Cmd.but_history:
                print("--but_history")
            else:
                pass


if __name__ == '__main__':
    load_exceptions_model_names_telegram()
    db = bd.DataBase()
    db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
    print("Bot launched!")

    p = multiprocessing.Process(target=queue_event_handling, args=(q,))
    p.start()
    bot.polling(none_stop=False, interval=0)
    p.join()

    for item in Cmd:
        print(item)


import re
import io
import csv
import requests
import configparser
import time

import telebot
from telebot import types

import bd
import header as h
import sql_req as sr

TOKEN = '1533268483:AAHIoxsy1cKUz5eHVLLeaxPdO5WDgsJI7WU'

# Получить все модели телефона по частичному названию WHERE brand_name = %s       AND
get_products_query = """
    SELECT id_product, brand_name, model_name
    FROM products_table
    WHERE brand_name LIKE '%%' || %s || '%%'       AND 
          model_name LIKE '%%' || %s || '%%'
"""
# Получить версии телефона по его id_prod
get_versions_query = """
    SELECT id_ver_phone, ram, rom
    FROM versions_phones_table
    WHERE id_product = %s
"""
# Получить все актуальные данные по id версии
get_all_act_data_by_id_ver_query = """
    SELECT brand_name, model_name, ram, rom, img_url, price, id_shop_name, color, general_table.url_product
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

TEXT_NO_RESULT_IN_BD = ':(\nНет совпадений в базе, проверьте правильность ввода или попробуйте найти другую модель'
TEXT_TOO_MANY_RESULTS_FROM_DB = ':(\nНайдено слишком много совпадений, попробуйте уточнить модель получше'
TEXT_OUT_RESULT_FROM_DB = 'Вот что я нашел по вашему запросу, выберите нужную модель:'
TEXT_AN_ERROR_HAS_OCCURRED = ':((\nПроизошла ошибка, повторите запрос еще раз'
TEXT_SELECT_VERSION = "На эту модель имеется несколько комплектаций, выберите подходящую:"
TEXT_NOT_FOUND = ":(\nНичего не найдено, попробуйте запросить другую модель"

bot = telebot.TeleBot(TOKEN)
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}


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
    # Поиск: есть ли какой-нибудь элемент из списка исключений в строке названия
    res = re.findall(r'|'.join(EXCEPT_MODEL_NAMES_TELEGRAM_DICT.keys()), model_name)
    # Если есть - подменяем
    if res:
        res = res[0]
        model_name = model_name.replace(res, EXCEPT_MODEL_NAMES_TELEGRAM_DICT.get(res))

    return model_name


# Получить уникальные значения из списка
def get_unique_numbers(value_list):
    unique = []
    for value in value_list:
        if value not in unique:
            unique.append(value)
    return unique


# Получение всех соответствий моделей из базы на основе того, что ввел пользователь
def search_data_in_db(user_request):
    text = user_request.lower().strip()
    brand_name = text.split()[0]
    model_name = text.replace(brand_name, '').strip()

    print("brand = '{}', model = '{}'".format(brand_name, model_name))

    # Получение значений из БД и формирование списка
    res = db.execute_read_query(get_products_query, (brand_name, model_name))
    search_res_list = [(id, '{} {}'.format(brand, model)) for id, brand, model in res]

    return search_res_list


# Узнать какую модель телефона выбрал пользователь
def find_out_model_which_user_chosen(query):
    bot.answer_callback_query(query.id)
    bot.delete_message(query.message.chat.id, query.message.id)

    if 'exit' in query.data:
        return

    bot.send_chat_action(query.message.chat.id, 'typing')
    print(query.data)

    id_prod = query.data.replace('model ', '')
    if not id_prod or not id_prod.isdigit:
        print("Ошибка с передачей id продукта")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        return

    # Получение всех версий по id_prod
    version_list = db.execute_read_query(get_versions_query, (int(id_prod),))
    if not version_list:
        print("Ошибка поиска версий - не найдено ни одной")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        return

    # Если версий больше, чем одна, то вывести форму выбора версии
    if len(version_list) > 1:
        offer_version_for_user(query.message, version_list)
    else:
        version = version_list[0]
        print_result(query.message, version[0])


# Узнать какую версию телефона выбрал пользователь
def find_out_version_which_user_chosen(query):
    bot.answer_callback_query(query.id)
    bot.delete_message(query.message.chat.id, query.message.id)

    if 'exit' in query.data:
        return

    bot.send_chat_action(query.message.chat.id, 'typing')
    print(query.data)

    id_ver = query.data.replace('version ', '')
    if not id_ver or not id_ver.isdigit:
        print("Ошибка с передачей id версии")
        bot.send_message(query.message.chat.id, TEXT_AN_ERROR_HAS_OCCURRED)
        return

    print_result(query.message, int(id_ver))


# Предложить выбрать одну из моделей, название которой похоже на то, что ввел пользователь
def offer_model_for_user(message, products_list):
    models_keys = telebot.types.InlineKeyboardMarkup(row_width=1)
    for item in products_list:
        models_keys.add(telebot.types.InlineKeyboardButton(find_and_replace_except_model_name(item[1].title()),
                                                           callback_data='model ' + str(item[0])))

    models_keys.add(telebot.types.InlineKeyboardButton('Выход', callback_data='model exit'))
    bot.send_message(message.chat.id, TEXT_OUT_RESULT_FROM_DB, reply_markup=models_keys)


# Предложить пользователю выбрать версию, если их больше, чем одна
def offer_version_for_user(message, versions_list):
    versions_keys = telebot.types.InlineKeyboardMarkup()
    for ver in versions_list:
        text_button = '{}/{} Gb (RAM/ROM)'.format(ver[1], ver[2]) if ver[1] else '{} Gb (ROM)'.format(ver[2])
        versions_keys.add(telebot.types.InlineKeyboardButton(text_button, callback_data='version ' + str(ver[0])))

    versions_keys.add(telebot.types.InlineKeyboardButton('Выход', callback_data='version exit'))
    bot.send_message(message.chat.id, TEXT_SELECT_VERSION, reply_markup=versions_keys)


def generating_text(prod_list):
    pos_brand, pos_model, pos_ram, pos_rom, pos_img, pos_price, pos_shop, pos_color, pos_url = 0, 1, 2, 3, 4, 5, 6, 7, 8
    item = prod_list[0]

    # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
    text = find_and_replace_except_model_name('<b>Смартфон {} {}</b>\n'.format(
        item[pos_brand].title(), item[pos_model].title()))

    # КОМПЛЕКТАЦИЯ
    text += '<b>{}/{} GB</b>\n'.format(item[pos_ram], item[pos_rom]) \
        if (item[pos_ram] and item[pos_brand] != 'apple') \
        else '<b>{} GB</b>\n'.format(item[pos_rom])

    # ГЕНЕРАЦИЯ ЦЕН, ССЫЛОК И МАГАЗИНОВ
    # text += '<b>Список цен:</b>\n'
    # old_price = prod_list[0][pos_price]
    # for product in prod_list:
    #     if old_price != product[pos_price]:
    #         old_price = product[pos_price]
    #         text += '\n'
    #
    #     text += '◦ {} ₽ - <a href="{}">{}</a> (<b>{}</b>)\n'.format(f'{product[pos_price]:,}'.replace(',', ' '),
    #                                                                 product[pos_url], product[pos_color].title(),
    #                                                                 h.TRUE_SHOP_NAMES[product[pos_shop] - 1])


    # СПИСОК ССЫЛОК ДЛЯ ПОКУПКИ
    # shops_set = list(set(item[pos_shop] for item in prod_list))
    shops_set = get_unique_numbers([item[pos_shop] for item in prod_list])

    # Группировка позиций по магазину и создание списка ссылок на разные магазины с разными цветами
    links_shop_list = []
    for shop in shops_set:
        # Генерация ссылок
        urls = ''
        for product in prod_list:
            if product[pos_shop] == shop:
                urls += '► <b>{}</b> ₽ - <a href="{}">{}</a>\n'.format(f'{product[pos_price]:,}'.replace(',', ' '),
                                                                       product[pos_url], product[pos_color].title())
        links_shop_list.append(urls)

    # Генерация ссылок
    indx = 0
    for link_set in links_shop_list:
        text += '\nЦены в <b>{}</b>:\n'.format(h.TRUE_SHOP_NAMES[shops_set[indx] - 1])
        text += link_set
        indx += 1

    return text


# Вывод конечного результата по запросу пользователя
def print_result(message, id_ver):
    prod_list = db.execute_read_query(get_all_act_data_by_id_ver_query, (id_ver,))
    if not prod_list:
        print("Не найдено ни одного товара")
        bot.send_message(message.chat.id, TEXT_NOT_FOUND)
        return

    text = generating_text(prod_list)
    resp = bot.send_photo(chat_id=message.chat.id, photo=prod_list[0][4], caption=text, parse_mode='Html')


@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, 'start ok')


@bot.message_handler(commands=['stop'])
def stop_command(message):
    bot.send_message(message.chat.id, 'stop ok')


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, 'help ok')


@bot.message_handler(content_types=['text'])
def text_messages(message):
    bot.send_chat_action(message.chat.id, 'typing')
    products_list = search_data_in_db(message.text)

    if not products_list:
        bot.send_message(message.chat.id, TEXT_NO_RESULT_IN_BD)
    elif len(products_list) > 10:
        bot.send_message(message.chat.id, TEXT_TOO_MANY_RESULTS_FROM_DB)
    else:
        offer_model_for_user(message, products_list)


@bot.callback_query_handler(func=lambda call: True)
def choice_model_callback(query):
    data = query.data
    if data.startswith('model'):
        print("Выбрана модель")
        find_out_model_which_user_chosen(query)
    if data.startswith('version'):
        print("Выбрана версия")
        find_out_version_which_user_chosen(query)


if __name__ == '__main__':
    load_exceptions_model_names_telegram()
    db = bd.DataBase()
    db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
    print("start bot")
    bot.polling(none_stop=True, interval=0)

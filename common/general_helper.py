"""
Главный общий файл-хэлпер с общими для многих файлов функциями и константами
"""

import collections
import logging
import random
import os
from datetime import datetime, timedelta


log_name = "logs/log-" + datetime.now().strftime("%Y.%m.%d-%H.%M") + ".txt"
# logging.basicConfig(handlers=[logging.FileHandler(filename=log_name, encoding='utf-8', mode='w')],
#                     level=logging.INFO)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('header')


def del_old_logs():
    """
    Удаление старых логов
    """
    name = "log-" + (datetime.now() - timedelta(days=2)).strftime("%Y.%m.%d-")

    for element in os.scandir("logs/"):
        if element.is_file() and name in element.name:
            os.remove("logs/" + element.name)


def get_proxy():
    """
    Получить proxy из файла
    """
    with open(PROXY_PATH) as f:
        proxy_list = f.read().splitlines()

    if proxy_list:
        proxy = proxy_list[random.randint(0, len(proxy_list) - 1)]
        print("Выбран PROXY: {}".format(proxy))
    else:
        print("ОШИБКА PROXY, СПИСОК ПУСТ")
        return []

    return proxy


def find_and_replace_except_model_name(model_name):
    """
    Поиск в строке названия фраз из списка исключения и их замена
    """
    if not EXCEPT_MODEL_NAMES_DICT:
        return model_name

    for key, value in EXCEPT_MODEL_NAMES_DICT.items():
        if key in model_name:
            model_name = model_name.replace(key, value)
            logger.info("Нашел модель в словаре исключений, key={}".format(key))

    return model_name


def find_allowed_model_names(model_name):
    """
    Поиск названия из списка известных моделей
    """
    for item in ALLOWED_MODEL_NAMES_LIST_FOR_BASE:
        if item.lower() == model_name.lower():
            return True

    return False


def save_undefined_model_name(model_name):
    """
    Сохранить отсутствующее в белом списке название модели в файл для дальнейшей
    отправки в ServiceBot
    """
    with open(PATH_UNDEFINED_MODEL_NAME_LIST, 'a', encoding='UTF-8') as f:
        f.write(model_name + '\n')


def find_in_namedtuple_list(namedtuple_list, brand_name=None, model_name=None, shop=None, category=None, color=None,
                            ram=None, rom=None, cur_price=None, img_url=None, url=None, rating=None, num_rating=None,
                            product_code=None, date_time=None, avg_actual_price=None,
                            hist_min_price=None, hist_min_shop=None, hist_min_date=None, diff_cur_avg=None,
                            limit_one=False):
    """
    Поиск элемента по любым параметрам в любом namedtuple
    """
    if not namedtuple_list:
        return []

    result_list = []
    for item in namedtuple_list:
        if brand_name and getattr(item, 'brand_name', None) != brand_name:
            continue
        if model_name and getattr(item, 'model_name', None) != model_name:
            continue
        if shop and getattr(item, 'shop', None) != shop:
            continue
        if category and getattr(item, 'category', None) != category:
            continue
        if color and getattr(item, 'color', None) != color:
            continue
        if ram and getattr(item, 'ram', None) != ram:
            continue
        if rom and getattr(item, 'rom', None) != rom:
            continue
        if img_url and getattr(item, 'img_url', None) != img_url:
            continue
        if url and getattr(item, 'url', None) != url:
            continue
        if rating and getattr(item, 'rating', None) != rating:
            continue
        if num_rating and getattr(item, 'num_rating', None) != num_rating:
            continue
        if product_code and getattr(item, 'product_code', None) != product_code:
            continue
        if date_time and getattr(item, 'date_time', None) != date_time:
            continue
        if cur_price and getattr(item, 'cur_price', None) != cur_price:
            continue
        if avg_actual_price and getattr(item, 'avg_actual_price', None) != avg_actual_price:
            continue
        if hist_min_price and getattr(item, 'hist_min_price', None) != hist_min_price:
            continue
        if hist_min_shop and getattr(item, 'hist_min_shop', None) != hist_min_shop:
            continue
        if hist_min_date and getattr(item, 'hist_min_date', None) != hist_min_date:
            continue
        if diff_cur_avg and getattr(item, 'diff_cur_avg', None) != diff_cur_avg:
            continue

        result_list.append(item)
        if limit_one:
            break

    return result_list


def per_num_of_num(a, b):
    """
    Процент числа от числа
    """
    return float(100.0 - (a / b * 100.0))


# ----------------------------- НАСТРОЙКИ -----------------------------

# Путь к webdriver
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
# Путь для файла с логами изменений цен
PRICE_CHANGES_PATH = "data/cache/dif_price.csv"
# Путь для файла с результатами парсинга
CSV_PATH = "data/cache/goods.csv"
CSV_PATH_RAW = "data/cache/"
# Путь к proxy
PROXY_PATH = 'data/proxy/proxy.txt'
# Пути к словарям
EXCEPT_MODEL_NAMES_PATH = "data/dictionaries/except_model_names.dic"
EXCEPT_MODEL_NAMES_TELEGRAM_PATH = "data/dictionaries/except_model_names_telegram.dic"
STATS_PRODS_DICTIONARY_PATH = "data/dictionaries/stats_prods_from_telegram.dic"
STATS_SHOPS_DICTIONARY_PATH = "data/dictionaries/stats_shops_from_telegram.dic"
MESSAGES_IN_TELEGRAM_LIST_PATH = "data/databases/msg_in_telegram.csv"
NUM_POSTS_IN_TELEGRAM_PATH = "data/databases/num_posts_in_telegram.data"
PATH_LIST_MODEL_NAMES_BASE = "data/databases/list_model_names_base.dat"
PATH_UNDEFINED_MODEL_NAME_LIST = "data/databases/undefined_model_name.dat"
PATH_UNDEFINED_MODEL_NAME_LIST_LOCK = "data/databases/undefined_model_name.lock"

# ----------------------------- КОЛЛЕКЦИЯ -----------------------------

# Список разрешенных названий моделей для добавления в БД
ALLOWED_MODEL_NAMES_LIST_FOR_BASE = []
# Словарь исключений названий моделей
EXCEPT_MODEL_NAMES_DICT = {}
# Единое название для всех восстановленных айфонов
REBUILT_IPHONE_NAME = ""
# Список слов, которые необходимо исключать из названий цветов
IGNORE_WORDS_FOR_COLOR = []

# Коллекция для хранения результатов парсинга одного товара (смартфоны)
ParseResult = collections.namedtuple(
    'ParseResult',
    (
        'shop',
        'category',
        'brand_name',
        'model_name',
        'color',
        'ram',
        'rom',
        'cur_price',
        'img_url',
        'url',
        'rating',
        'num_rating',
        'product_code',
    ),
)
# Заголовок для csv файлов (смартфоны)
HEADERS = (
    'Магазин',
    'Категория',
    'Бренд',
    'Модель',
    'Цвет',
    'RAM',
    'ROM',
    'Цена',
    'Ссылка на изображение',
    'Ссылка',
    'Рейтинг',
    'Кол-во отзывов',
    'Код продукта'
)

# Коллекция для хранения результатов парсинга одного товара (смартфоны)
PriceChanges = collections.namedtuple(
    'PriceChanges',
    (
        'shop',
        'category',
        'brand_name',
        'model_name',
        'color',
        'ram',
        'rom',
        'img_url',
        'url',
        'date_time',
        'cur_price',
        'avg_actual_price',
        'hist_min_price',
        'hist_min_shop',
        'hist_min_date',
        'diff_cur_avg',
    ),
)
# Заголовок для csv файлов (изменения цен смартфонов)
HEADERS_PRICE_CHANGES = (
    'Магазин',
    'Категория',
    'Бренд',
    'Модель',
    'Цвет',
    'RAM',
    'ROM',
    'Ссылка на изображение',
    'Ссылка',
    'Дата и время',
    'Текущая цена',
    'Средняя цена',
    'Историческая мин. цена',
    'Исторический мин. магазин',
    'Исторический мин. дата',
    'Разница цены от средней',
)

# -------------------- СПИСОК СООБЩЕНИЙ ТЕЛЕГРАМ ---------------------- #

# Коллекция для хранения результатов парсинга одного товара (смартфоны)
MessagesInTelegram = collections.namedtuple(
    'MessagesInTelegram',
    (
        'message_id',
        'category',
        'brand_name',
        'model_name',
        'ram',
        'rom',
        'cur_price',
        'avg_actual_price',
        'img_url',
        'where_buy_list',
        'hist_min_price',
        'hist_min_shop',
        'hist_min_date',
        'post_datetime',
        'text_hash',
        'is_actual',
    ),
)

HEADERS_MSG_IN_TELEGRAM = (
    'Message_ID',
    'Category',
    'Brand',
    'Model',
    'RAM',
    'ROM',
    'Cur_Price',
    'Avg_Price',
    'Img_URL',
    'Where_Buy_List',
    'Hist_Min_Price',
    'Hist_Min_Shop',
    'Hist_Min_Date',
    'Post_Datetime',
    'Text_Hash',
    'Actual',
)

# -------------------- НАЗВАНИЯ МАГАЗИНОВ ДЛЯ ТЕЛЕГРАМ ---------------------- #

TRUE_SHOP_NAMES = [
    'М.видео',
    'Эльдорадо',
    'DNS',
    'DNS Технопоинт',
    'МТС',
    'Ситилинк',
    'RBT.ru',
    'Онлайнтрейд',
    'Связной',
    'ТехноСити',
    'Билайн',
    'МегаФон',
    'е2е4',
    'НОУ-ХАУ',
    're:Store',
    'Официальный интернет-магазин Samsung',
    'Официальный интернет-магазин Huawei',
    'Ozon',
    'Wildberries',
    'Sony Store',
    'Tmall',
]

# ----------------------------- ТАБЛИЦЫ В БД ----------------------------- #

# Список названий магазинов
SHOPS_NAME_LIST = [
    ('мвидео',),
    ('эльдорадо',),
    ('dns',),
    ('технопоинт',),
    ('мтс',),
    ('ситилинк',),
    ('rbt',),
    ('онлайнтрейд',),
    ('связной',),
    ('техносити',),
    ('билайн',),
    ('мегафон',),
    ('e2e4',),
    ('ноу-хау',),
]
# Список категорий
CATEGORIES_NAME_LIST = [
    ('смартфоны',),
    ('ноутбуки',),
]

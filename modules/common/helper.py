"""
Главный общий файл-хэлпер с общими для многих файлов функциями и константами
"""
import sys
import collections
import logging
import random
import os
from datetime import datetime, timedelta
import modules.common.file_worker as fw


log_name = "logs/log-" + datetime.now().strftime("%Y.%m.%d-%H.%M") + ".txt"
# Следующие 2 строчки: расскомментировать, если бой, закомментировать, если тест.
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
    proxy_list = fw.FileWorker.list_data.load(PROXY_PATH)

    if not proxy_list:
        logger.error("ОШИБКА PROXY, СПИСОК ПУСТ")
        return None

    proxy = proxy_list[random.randint(0, len(proxy_list) - 1)]
    logger.info("Выбран PROXY: {}".format(proxy))

    return proxy


def is_all_elem_equal_in_tuple_list(elements, pos):
    """
    Проверить все элементы на равенство по заданной позиции
    """
    if not elements or len(elements) == 1:
        return True

    data = elements[0][pos]
    for item in elements:
        if item[pos] != data:
            return False

    return True


def replace_value_from_dictionary(dictionary: dict, value):
    """
    Проверка наличия @key_name в словаре замен. В случае, если такой ключ найден -
    возвращается значение из словаря.
    """
    if not dictionary:
        return value

    # Поиск в строке названия фраз из списка исключения и их замена
    for key, val in dictionary.items():
        if key in value:
            value = value.replace(key, val)
            logger.info("Нашел модель в словаре исключений телеграм, key={}".format(key))

    return value


def find_allowed_model_names(model_name):
    """
    Поиск названия из списка известных моделей
    """
    for item in ALLOWED_MODEL_NAMES_LIST_FOR_BASE:
        if item.lower() == model_name.lower():
            return True

    return False


def find_in_namedtuple_list(namedtuple_list, brand_name=None, model_name=None, shop=None, category=None, color=None,
                            ram=None, rom=None, price=None, img_url=None, url=None, rating=None, num_rating=None,
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
        if price and getattr(item, 'price', None) != price:
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


def find_min_price_in_prices_list(price_list):
    """
    Вернет список с одним или несколькими магазинами и разными цветами, но с самыми низкими ценами
    """
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    # Если в списке все цены равны (не важно сколько магазинов) или список пуст - возвращаем список без изменений
    if is_all_elem_equal_in_tuple_list(price_list, pos_price):
        return price_list

    # Если в списке цены разные, но магазин один или несколько - находим самые низкие цены не зависимо от магазина
    result = []
    min_price = min(price_list)[pos_price]
    for item in price_list:
        if item[pos_price] == min_price:
            result.append(item)

    return result


def per_num_of_num(a, b):
    """
    Процент числа от числа
    """
    return float(100.0 - (a / b * 100.0))


# ----------------------------- ПУТИ -----------------------------
ROOT_PATH = "C:/Py_Projects/ParserOnlineShop/"  # sys.path[1] + '/'
# Путь к webdriver
WD_PATH = ROOT_PATH + "venv/WebDriverManager/chromedriver.exe"
# Путь для файла с логами изменений цен
PRICE_CHANGES_PATH = ROOT_PATH + "data/cache/dif_price.csv"
# Путь для файла с результатами парсинга
CSV_PATH = ROOT_PATH + "data/cache/goods.csv"
CSV_PATH_RAW = ROOT_PATH + "data/cache/"
# Путь к proxy
PROXY_PATH = ROOT_PATH + "data/proxy/proxy.txt"
# Пути к словарям
EXCEPT_MODEL_NAMES_PATH = ROOT_PATH + "data/dictionaries/except_model_names.dic"
EXCEPT_MODEL_NAMES_TELEGRAM_PATH = ROOT_PATH + "data/dictionaries/except_model_names_telegram.dic"
STATS_PRODS_DICTIONARY_PATH = ROOT_PATH + "data/dictionaries/stats_prods_from_telegram.dic"
STATS_SHOPS_DICTIONARY_PATH = ROOT_PATH + "data/dictionaries/stats_shops_from_telegram.dic"
MESSAGES_IN_TELEGRAM_LIST_PATH = ROOT_PATH + "data/databases/msg_in_telegram.csv"
NUM_POSTS_IN_TELEGRAM_PATH = ROOT_PATH + "data/databases/num_posts_in_telegram.data"
LIST_MODEL_NAMES_BASE_PATH = ROOT_PATH + "data/databases/list_model_names_base.dat"
UNDEFINED_MODEL_NAME_LIST_PATH = ROOT_PATH + "data/databases/undefined_model_name.dat"
UNDEFINED_MODEL_NAME_LIST_LOCK_PATH = ROOT_PATH + "data/databases/undefined_model_name.lock"
CRASH_DATA_PATH = ROOT_PATH + "data/databases/crash_data.dat"
BOT_ACCOUNT_PATH = ROOT_PATH + "modules/data_sender/telegram/my_account"
IMAGE_FOR_SEND_IN_TELEGRAM_PATH = ROOT_PATH + "data/cache/for_send/"

# ----------------------------- КОЛЛЕКЦИЯ -----------------------------

# Список разрешенных названий моделей для добавления в БД
ALLOWED_MODEL_NAMES_LIST_FOR_BASE = []
# Словарь исключений названий моделей
EXCEPT_MODEL_NAMES_DICT = {}
# Единое название для всех восстановленных айфонов
REBUILT_IPHONE_NAME = ""
# Список слов, которые необходимо исключать из названий цветов
IGNORE_WORDS_FOR_COLOR = []


# ---------------- ПЕРЕМЕННЫЕ ДЛЯ РЕФЕРАЛЬНЫХ ССЫЛОК ----------------
REF_LINK_MVIDEO = ''
REF_LINK_MTS = ''
REF_LINK_ELDORADO = ''
REF_LINK_CITILINK = ''

DOMAIN_DNS = 'dns.ru'
DOMAIN_MVIDEO = 'mvideo.ru'
DOMAIN_MTS = 'mts.ru'
DOMAIN_ELDORADO = 'eldorado.ru'
DOMAIN_CITILINK = 'citilink.ru'


# ---------------- ПЕРЕМЕННЫЕ ДЛЯ РЕФЕРАЛЬНЫХ ССЫЛОК ----------------

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
        'price',
        'img_url',
        'url',
        'rating',
        'num_rating',
        'product_code',
    ),
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
        'price',
        'avg_actual_price',
        'hist_min_price',
        'hist_min_shop',
        'hist_min_date',
        'diff_cur_avg',
    ),
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
        'price',
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

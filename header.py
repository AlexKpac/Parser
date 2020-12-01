import collections
import logging
import re

logging.basicConfig(handlers=[logging.FileHandler(filename="log.txt", encoding='utf-8', mode='w')],
                    level=logging.INFO)
logger = logging.getLogger('header')


# Добавить запись в словарь
def add_entry_to_dictionary(path, entry):
    if not entry:
        return

    with open(path, 'a', encoding='UTF-8') as f:
        f.write(entry.lower() + '\n')


def update_color_dictionary():
    COLOR_DICTIONARY_LIST.clear()

    with open(COLORS_DICTIONARY_PATH, 'r', encoding='UTF-8') as f:
        lines = f.readlines()
        for line in lines:
            # удалим заключительный символ перехода строки
            current_place = line[:-1]
            # добавим элемент в конец списка
            COLOR_DICTIONARY_LIST.append(current_place)


# ЗАМОРОЖЕННАЯ Ф-ЦИЯ. Поиск цвета в названии модели, используя словарь цветов
def find_color_in_model_name(model_name):
    # Поиск цвета из словаря в строке названия модели
    res = []
    for item in COLOR_DICTIONARY_LIST:
        res += [(m.start(), m.group(), m.end()) for m in re.finditer(item, model_name)
                if m.end() == len(model_name) or not model_name[m.end()].isalpha()]

    # Совпадений не найдено
    if not res:
        logger.warning("Цвет не найден, ведется поиск вручную")
        return None

    # Найдено(ы) совпадение(ия), ищем элемент с максимальной длиной
    first_occur = min(res)
    first_occur_all = [item[1] for item in res if item[0] == first_occur[0]]
    color = max(first_occur_all, key=len)

    return color


# Поиск в строке названия фраз из списка исключения и их замена
def find_and_replace_except_model_name(model_name):
    model_name = model_name.lower()
    # Поиск: есть ли какой-нибудь элемент из списка исключений в строке названия
    res = re.findall(r'|'.join(EXCEPT_MODEL_NAMES_DICT.keys()), model_name)
    # Если есть - подменяем
    if res:
        res = res[0]
        model_name = model_name.replace(res, EXCEPT_MODEL_NAMES_DICT.get(res))

    return model_name


# ----------------------------- НАСТРОЙКИ -----------------------------

# Путь к webdriver
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
# Путь для файла с логами изменений цен
# PRICE_CHANGES_PATH = "/Users/Никита/Desktop/dif_price.csv"
PRICE_CHANGES_PATH = "cache/dif_price.csv"
# Путь для файла с результатами парсинга
# CSV_PATH = "/Users/Никита/Desktop/goods1.csv"
# CSV_PATH_RAW = "/Users/Никита/Desktop/"
CSV_PATH = "cache/goods.csv"
CSV_PATH_RAW = "cache/"
COLORS_DICTIONARY_PATH = "dictionaries/colors.dic"
EXCEPT_MODEL_NAMES_PATH = "dictionaries/except_model_names.dic"

# ----------------------------- КОЛЛЕКЦИЯ -----------------------------

# Словарь цветов
COLOR_DICTIONARY_LIST = []
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
        'price',
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

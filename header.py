import collections
import logging

# ----------------------------- НАСТРОЙКИ -----------------------------

# Путь к webdriver
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
# Путь для файла с логами изменений цен
PRICE_CHANGES_PATH = "/Users/Никита/Desktop/dif_price.csv"
# Путь для файла с результатами парсинга
CSV_PATH = "/Users/Никита/Desktop/goods.csv"


logging.basicConfig(level=logging.INFO)

# ----------------------------- КОЛЛЕКЦИЯ -----------------------------

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

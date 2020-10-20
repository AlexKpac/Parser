import collections
import logging

# ----------------------------- НАСТРОЙКИ -----------------------------

# Путь к webdriver
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
# На какую разницу цен необходимо реагировать
DIF_PRICE_UP_PERCENT = 3
DIF_PRICE_DOWN_PERCENT = 5
# Путь для файла с логами изменений цен
PRICE_CHANGES_PATH = "/Users/Никита/Desktop/dif_price.csv"
# Путь для файла с результатами парсинга
CSV_PATH = "/Users/Никита/Desktop/goods.csv"
# Текущий город для магазинов
CURRENT_CITY = 'Новосибирск'
# Время ожидания в сек между переключениями страниц в каталоге товаров
WAIT_BETWEEN_PAGES_SEC = 4

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
        'rating',
        'num_rating',
        'product_code',
        'date_time',
        'prev_price',
        'cur_price',
        'diff',
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
    'Рейтинг',
    'Кол-во отзывов',
    'Код продукта',
    'Дата и время',
    'Предыдущая цена',
    'Текущая цена',
    'Изменение',
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

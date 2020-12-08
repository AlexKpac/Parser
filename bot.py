import telebot
from telebot import types
import configparser
import header as h
import csv
import datetime
import requests
import time
from PIL import Image, ImageDraw
import re

logger = h.logging.getLogger('bot')
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}
STATS_PRODS_DICT = {}
STATS_SHOPS_DICT = {}


# Чтение словаря с подсчетом кол-ва моделей
def load_stats_prods_dictionary():
    # Словарь цветов
    with open(h.STATS_PRODS_DICTIONARY_PATH, 'r', encoding='UTF-8') as f:
        for line in f:
            res = re.findall(r"\[.+?]", line)
            # Отсечь кривые записи
            if len(res) != 2:
                continue
            # Добавить в словарь
            STATS_PRODS_DICT[res[0].replace('[', '').replace(']', '')] = \
                int(res[1].replace('[', '').replace(']', ''))


# Чтение словаря с подсчетом кол-ва моделей
def load_stats_shops_dictionary():
    # Словарь цветов
    with open(h.STATS_SHOPS_DICTIONARY_PATH, 'r', encoding='UTF-8') as f:
        for line in f:
            res = re.findall(r"\[.+?]", line)
            # Отсечь кривые записи
            if len(res) != 2:
                continue
            # Добавить в словарь
            STATS_SHOPS_DICT[res[0].replace('[', '').replace(']', '')] = \
                int(res[1].replace('[', '').replace(']', ''))


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


# Сохранить на диск измененный словарь статистики товаров
def save_stats_prods_dictionary():
    with open(h.STATS_PRODS_DICTIONARY_PATH, 'w', encoding='UTF-8') as f:
        for key, val in STATS_PRODS_DICT.items():
            f.write('[{}] -> [{}]\n'.format(key, val))


# Сохранить на диск измененный словарь статистики магазинов
def save_stats_shops_dictionary():
    with open(h.STATS_SHOPS_DICTIONARY_PATH, 'w', encoding='UTF-8') as f:
        for key, val in STATS_SHOPS_DICT.items():
            f.write('[{}] -> [{}]\n'.format(key, val))


# Поиск в строке названия фраз из списка исключения и их замена
def find_and_replace_except_model_name(model_name):
    # Поиск: есть ли какой-нибудь элемент из списка исключений в строке названия
    res = re.findall(r'|'.join(EXCEPT_MODEL_NAMES_TELEGRAM_DICT.keys()), model_name)
    # Если есть - подменяем
    if res:
        res = res[0]
        model_name = model_name.replace(res, EXCEPT_MODEL_NAMES_TELEGRAM_DICT.get(res))

    return model_name


# Увеличение полотна изображения и вставка в середину картинки для поста
def image_change(url):
    W, H = 640, 480

    # Проверка URL
    if not ("http" in url):
        logger.warning("Дефектный URL изображения: {}".format(url))
        return None

    # Загрузить изображение с url
    try:
        resp = requests.get(url, stream=True).raw
    except requests.exceptions.RequestException as e:
        logger.error("Can't get img from url :(, url={}\ne = {}".format(url, e))
        return None

    # Попытка открыть изображение средствами PIL
    try:
        img = Image.open(resp)
    except IOError:
        logger.error("Unable to open image")
        return None

    # Если высота не соответствует H - изменение размера изображения с учетом пропорций
    if img.height != H:
        width, height = img.size
        new_height = H
        new_width = int(new_height * width / height)
        img = img.resize((new_width, new_height), Image.ANTIALIAS)

    im = Image.new('RGB', (W, H), color='#FFFFFF')
    im.paste(img, (int((W - img.width) / 2), 0), 0)

    return im


# Получить данные с файла (для теста)
def get_data():
    result_list = []
    with open(h.PRICE_CHANGES_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            result_list.append(h.PriceChanges(
                shop=int(row['Магазин']),
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                date_time=row['Дата и время'],
                cur_price=int(row['Текущая цена']),
                avg_actual_price=float(row['Средняя цена']),
                hist_min_price=int(row['Историческая мин. цена']),
                hist_min_shop=int(row['Исторический мин. магазин']),
                hist_min_date=row['Исторический мин. дата'],
                diff_cur_avg=int(row['Разница цены от средней']),
            ))

    return result_list


class Bot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.chat_id = self.config['bot']['chat_id']
        self.ignore_brands = self.config['bot-ignore']['brands'].lower().split('\n')
        self.bot = telebot.TeleBot(self.config['bot']['token'])
        self.one_star_per = float(self.config['bot-stars']['one_star_per'])
        self.two_star_per = float(self.config['bot-stars']['two_star_per'])
        self.three_star_per = float(self.config['bot-stars']['three_star_per'])
        self.four_star_per = float(self.config['bot-stars']['four_star_per'])
        self.five_star_per = float(self.config['bot-stars']['five_star_per'])
        self.pc_product_list = []
        # Загрузка словаря исключений названий моделей для постов
        load_exceptions_model_names_telegram()
        load_stats_prods_dictionary()
        load_stats_shops_dictionary()

    # Подготовка текста для поста
    def __format_text(self, version_list):
        product = version_list[0]
        # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
        text = find_and_replace_except_model_name('<b>{} {} {}</b>\n'.format(
            product.category[0:-1].title(), product.brand_name.title(), product.model_name.title()))

        # КОМПЛЕКТАЦИЯ
        text += '<b>{}/{} GB</b>\n\n'.format(product.ram, product.rom) if product.ram \
            else '<b>{} GB</b>\n\n'.format(product.rom)

        # ОГОНЬКИ
        per = float(100 - product.cur_price / product.avg_actual_price * 100)
        star = 0
        if self.one_star_per <= per < self.two_star_per:
            star = 1
        if self.two_star_per <= per < self.three_star_per:
            star = 2
        if self.three_star_per <= per < self.four_star_per:
            star = 3
        if self.four_star_per <= per < self.five_star_per:
            star = 4
        if self.five_star_per < per:
            star = 5

        logger.info("{} ЗВЕЗД(Ы)".format(star))
        text += '🔥' * star
        text += '\n'

        # ЦЕНА
        # text += '⭐⭐⭐\n'
        # text += '🍪🍪🍪\n'
        # text += '👑👑👑\n'
        # text += '💎💎💎\n'
        # text += '💥💥💥\n'
        # text += '🌞🌞🌞\n'
        # text += '🔴🔴🔴\n'
        # text += '🚩🚩🚩\n'
        s_price = '{0:,}'.format(product.cur_price).replace(',', ' ')
        text += 'Выгодная цена: <b><i>{}</i></b> ₽\n'.format(s_price)
        s_price = '{0:,}'.format(int(product.avg_actual_price - product.cur_price))
        text += '<i>(Дешевле на {}</i> ₽<i> от средней)</i>\n\n'.format(s_price).replace(',', ' ')

        # ИСТОРИЧЕСКИЙ МИНИМУМ
        if product.cur_price <= product.hist_min_price:
            text += '<i>Данная цена является самой низкой за всё время</i>\n'
        else:
            date_time = datetime.datetime.strptime(str(product.hist_min_date), '%Y-%m-%d %H:%M:%S.%f').strftime(
                '%d.%m.%Y')
            s_price = '{0:,}'.format(product.hist_min_price).replace(',', ' ')
            text += '<i>Минимальная цена {}</i> ₽ <i>была {} в {}</i>\n'.format(
                s_price, h.TRUE_SHOP_NAMES[product.hist_min_shop - 1], date_time)

        # СПИСОК ССЫЛОК ДЛЯ ПОКУПКИ
        shops_set = list(set(item.shop for item in version_list))

        # Группировка позиций по магазину и создание списка ссылок на разные магазины с разными цветами
        hashtag_shops = ''
        links_shop_list = []
        for shop in shops_set:
            # Генерация тегов магазинов
            hashtag_shops += '#' + h.SHOPS_NAME_LIST[shop - 1][0] + ' '

            # Генерация ссылок
            urls = ''
            for product in version_list:
                if product.shop == shop:
                    urls += '<a href="{}">► {}</a>\n'.format(product.url, product.color.title())  # → ► ● ○ • ›
            links_shop_list.append(urls)

        # Генерация ссылок
        indx = 0
        for link_set in links_shop_list:
            text += '\nКупить в <b><u>{}</u></b>:\n'.format(h.TRUE_SHOP_NAMES[shops_set[indx] - 1])
            text += link_set
            indx += 1

        # ХЭШТЕГИ
        text += '\n' + '#' + product.brand_name + ' ' + hashtag_shops

        return text

    # Фильтрация входных данных - удаление дубликатов и применение игнор-листа
    def __filtering_data(self):
        # Удалить дубликаты, если имеются
        result = []
        for item in self.pc_product_list:
            if not result.count(item):
                result.append(item)
        self.pc_product_list = result

        # Удалить товары, если его бренд имеется в игнор-листе
        result = []
        for item in self.pc_product_list:
            if not self.ignore_brands.count(item.brand_name):
                result.append(item)
        self.pc_product_list = result

    # Разбор списка продуктов, группировка по цветам, отправка в телеграм
    def __prepare_posts_and_send(self):
        versions_list = []
        # Проход по всему списку, группировка элементов по версии и цвету, пост группы
        while self.pc_product_list:
            # Взятие группы комплектации с разными цветами
            item = self.pc_product_list[0]
            one_version_list = h.find_in_namedtuple_list(self.pc_product_list, brand_name=item.brand_name,
                                                         model_name=item.model_name, ram=item.ram, rom=item.rom,
                                                         cur_price=item.cur_price)
            # Составление списка комплектаций
            versions_list.append(one_version_list)
            # Удаление из основного списка взятой группы one_version_list
            for item in one_version_list:
                self.pc_product_list.remove(item)

        # Отправка постов в телеграм. Звук только у последних 2-ух
        for i in range(len(versions_list)):
            self.__send_post(versions_list[i], True if (i < (len(versions_list) - 2)) else False)

    # Отправка поста в телеграм
    def __send_post(self, version_list, dis_notify):
        item = version_list[0]
        text = self.__format_text(version_list)
        img = image_change(item.img_url)
        if not img:
            logger.error("No IMG in send post")
            return

        # Обновление словаря статистики товаров
        full_name = "{} {}".format(item.brand_name, item.model_name)
        if full_name in STATS_PRODS_DICT:
            STATS_PRODS_DICT[full_name] += 1
        else:
            STATS_PRODS_DICT[full_name] = 1

        shop_name = h.SHOPS_NAME_LIST[item.shop - 1][0]
        # Обновление словаря статистики магазинов
        if shop_name in STATS_SHOPS_DICT:
            STATS_SHOPS_DICT[shop_name] += 1
        else:
            STATS_SHOPS_DICT[shop_name] = 1

        # Отправка поста в обертке
        for i in range(3):
            try:
                self.bot.send_photo(chat_id=self.chat_id, photo=img, caption=text, parse_mode='Html',
                                    disable_notification=dis_notify)
                break
            except telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 30 сек, ({})".format(i + 1))
                time.sleep(30)

    # Запуск бота
    def run(self, pc_product_list):
        # pc_product_list = get_data()
        if not pc_product_list:
            logger.info("НЕТ ДАННЫХ ДЛЯ TELEGRAM")
            return
        self.pc_product_list = pc_product_list
        self.__filtering_data()
        self.__prepare_posts_and_send()
        save_stats_prods_dictionary()
        save_stats_shops_dictionary()

# bot = Bot()
# bot.run([])

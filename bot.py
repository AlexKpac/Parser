import re
import io
import time
import csv
import requests
import configparser
from datetime import datetime

import telebot
from telebot import types
from PIL import Image

import bd
import header as h
import sql_req as sr

logger = h.logging.getLogger('bot')
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}
STATS_PRODS_DICT = {}
STATS_SHOPS_DICT = {}


# Чтение словаря с подсчетом кол-ва моделей
def load_stats_prods_dictionary():
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
def image_change(url, stamp_irrelevant=False):
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

    # Поставить штамп "Не актуально"
    if stamp_irrelevant:
        # blackout = Image.open('img/blackout.png').convert("RGBA")
        stamp = Image.open('img/stamp.png').convert("RGBA")
        im.paste(stamp, (int((W - stamp.width) / 2), int((H - stamp.height) / 2)), stamp)
        # im.paste(blackout, (0, 0), blackout)

    return im.convert("RGB")


# Проверить все элементы на равенство по заданной позиции
def all_elem_equal_in_tuple_list(elements, indx):
    if not elements or len(elements) == 1:
        return True

    data = elements[0][indx]
    for item in elements:
        if item[indx] != data:
            return False

    return True


# Для неактуальных постов: вернет список с одним или несколькими магазинами и разными цветами,но с самыми низкими ценами
def irr_post_find_all_min_price_data(price_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    # Если в списке все цены равны (не важно сколько магазинов) или список пуст - возвращаем список без изменений
    if all_elem_equal_in_tuple_list(price_list, pos_price):
        return price_list

    # Если в списке цены разные, но магазин один или несколько - находим самые низкие цены не зависимо от магазина
    result = []
    min_price = min(price_list)[pos_price]
    for item in price_list:
        if item[pos_price] == min_price:
            result.append(item)

    return result


# Поиск в списке кортежей (результат с БД) значения по его url
def irr_post_find_price_data_by_url(price_data_list, url):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    if not price_data_list or not url:
        return []

    indx = [i for i, v in enumerate(price_data_list) if v[pos_url] == url]
    return price_data_list[indx[0]] if indx else []

# Для неактуальных постов: проверка других магазинов, отличных от магазинов поста, в которых цена тоже выгодная
def irr_post_check_price_in_other_shop(min_act_price_data_in_stock_list, item_shop_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    print("---In other shop:\nmin_act_price_data_in_stock_list - {}\nitem_shop_list - {}".format(min_act_price_data_in_stock_list, item_shop_list))

    # Если в минимальных актуальных цен есть цены из магазинов, отличных от магазинов в посте,
    # то пост автоматически становится ПОЛНОСТЬЮ НЕАКТУАЛЬНЫМ
    for min_price_data_item in min_act_price_data_in_stock_list:
        if not (min_price_data_item[pos_shop] in item_shop_list):
            print("---In other shop: if not {} in item_shop_list - TRUE".format(str(min_price_data_item[pos_shop])))
            # Если нашлась низкая цена в другом магазине - пост неактуальный - переход к другому посту
            return True

    return False


# Для неактуальных постов: поиск неактуальных ссылок
def irr_post_find_irr_url(act_price_data_in_stock_list, min_act_price_data_in_stock_list, item_urls_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    # Проверка неактуальных ссылок
    irrelevant_url_list = []
    for item_url in item_urls_list:
        # Если текущая ссылка отсутствует в списке всех актуальных цен в наличии (значит товара нет наличии) ИЛИ
        # текущая ссылка отсутствует в списке всех минимальных актуальных цен в наличии (цена изменилась)
        if not (item_url in (items_1[pos_url] for items_1 in act_price_data_in_stock_list)) or \
                not (item_url in (items_2[pos_url] for items_2 in min_act_price_data_in_stock_list)):
            irrelevant_url_list.append(item_url)

    return irrelevant_url_list


# Для неактуальных постов: поиск среди всех данных только тех, что в наличии
def irr_post_search_data_in_stock(act_price_data_list, pr_product_in_stock_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    act_price_data_in_stock_list = []
    for act_price_data_item in act_price_data_list:
        if h.find_in_namedtuple_list(pr_product_in_stock_list, url=act_price_data_item[pos_url],
                                     limit_one=True):
            act_price_data_in_stock_list.append(act_price_data_item)

    return act_price_data_in_stock_list


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
        self.irrelevant_url_text = self.config['bot']['irrelevant_url_text']
        self.pc_product_list = []
        self.actual_posts_in_telegram_list = []
        self.num_all_post = 0
        self.num_actual_post = 0
        self.db = bd.DataBase()
        # Загрузка словаря исключений названий моделей для постов
        load_exceptions_model_names_telegram()
        load_stats_prods_dictionary()
        load_stats_shops_dictionary()
        self.__load_num_posts()
        self.__load_msg_in_telegram_list()

    # Чтение кол-ва всех и актуальных постов
    def __load_num_posts(self):
        with open(h.NUM_POSTS_IN_TELEGRAM_PATH, 'r', encoding='UTF-8') as f:
            line1 = f.readline().replace('\n', '')
            self.num_all_post = int(line1) if line1 else 0
            line2 = f.readline().replace('\n', '')
            self.num_actual_post = int(line2) if line2 else 0

            logger.info("Num All Posts in Telegram = {}".format(self.num_all_post))
            logger.info("Num Actual Posts in Telegram = {}".format(self.num_actual_post))

    # Сохранить на диск кол-во всех и актуальных постов
    def __save_num_posts(self):
        with open(h.NUM_POSTS_IN_TELEGRAM_PATH, 'w', encoding='UTF-8') as f:
            f.write(str(self.num_all_post))
            f.write('\n')
            f.write(str(self.num_actual_post))

    # Сохранение всего результата в csv файл
    def __save_msg_in_telegram_list(self):
        with open(h.MESSAGES_IN_TELEGRAM_LIST_PATH, 'w', newline='', encoding='UTF-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_MSG_IN_TELEGRAM)
            for item in self.actual_posts_in_telegram_list:
                writer.writerow(item)

    # Загрузить данные с csv, чтобы не парсить сайт
    def __load_msg_in_telegram_list(self):
        with open(h.MESSAGES_IN_TELEGRAM_LIST_PATH, 'r', encoding='UTF-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_urls_list = row['URLs'].replace("'", "").replace('(', '').replace(')', '').replace(' ', '')
                row_shops_list = row['Магазины'].replace("'", "").replace('(', '').replace(')', '').replace(' ', '')

                self.actual_posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=int(row['Message ID']),
                    text=row['Текст'],
                    brand_name=row['Бренд'],
                    model_name=row['Модель'],
                    ram=int(row['RAM']),
                    rom=int(row['ROM']),
                    cur_price=int(row['Цена']),
                    shops_list=tuple(int(item) for item in row_shops_list.split(',') if item),
                    urls_list=tuple(item for item in row_urls_list.split(',') if item),
                    img_url=row['Img URL'],
                    datetime=datetime.strptime(str(row['Дата и Время']), '%Y-%m-%d %H:%M:%S.%f'),
                ))

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
            date_time = datetime.strptime(str(product.hist_min_date), '%Y-%m-%d %H:%M:%S.%f').strftime(
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

        # Проверка на наличие такого же поста в списке актуальных сообщений
        if h.find_in_namedtuple_list(self.actual_posts_in_telegram_list, brand_name=item.brand_name,
                                     model_name=item.model_name, cur_price=item.cur_price, ram=item.ram,
                                     rom=item.rom, limit_one=True):
            logger.info("Duplicate post, SKIP\n{}".format(item))
            return

        # Обновление счетчика постов
        self.num_all_post += 1
        self.num_actual_post += 1

        # Обновление словаря статистики товаров
        full_name = "{} {}".format(item.brand_name, item.model_name)
        if full_name in STATS_PRODS_DICT:
            STATS_PRODS_DICT[full_name] += 1
        else:
            STATS_PRODS_DICT[full_name] = 1

        # Обновление словаря статистики магазинов
        shop_name = h.SHOPS_NAME_LIST[item.shop - 1][0]
        if shop_name in STATS_SHOPS_DICT:
            STATS_SHOPS_DICT[shop_name] += 1
        else:
            STATS_SHOPS_DICT[shop_name] = 1

        # Генерация поста
        text = self.__format_text(version_list)
        img = image_change(item.img_url)
        if not img:
            logger.error("No IMG in send post")
            return

        # Отправка поста в обертке
        for i in range(3):
            try:
                resp = self.bot.send_photo(chat_id=self.chat_id, photo=img, caption=text, parse_mode='Html',
                                           disable_notification=dis_notify)
                print(resp.message_id)

                shops_list = tuple(set(item_shop.shop for item_shop in version_list))
                urls_list = tuple(set(item_url.url for item_url in version_list))

                # При успешной отправки добавляем данную позицию в список актуальных товаров
                self.actual_posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=resp.message_id,
                    text=text,
                    brand_name=item.brand_name,
                    model_name=item.model_name,
                    ram=item.ram,
                    rom=item.rom,
                    cur_price=item.cur_price,
                    shops_list=shops_list,
                    urls_list=urls_list,
                    img_url=item.img_url,
                    datetime=datetime.now(),
                ))

                break

            except telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 30 сек, ({})".format(i + 1))
                time.sleep(30)

    # Отредактировать пост как частично или полностью неактуальный. По-умолчанию полностью неактуальный
    def __edit_post_as_irrelevant(self, post, text=None, stamp=True):
        img = image_change(post.img_url, stamp)
        if not img:
            logger.error("No IMG in edit post")
            return False

        if not text:
            text = post.text

        # Редактирование поста
        try:
            self.bot.edit_message_media(
                media=types.InputMediaPhoto(media=img, caption=text, parse_mode='html'),
                chat_id=self.chat_id, message_id=post.message_id)

            # Декремент кол-ва актуальных постов
            self.num_actual_post -= 1
            return True

        except telebot.apihelper.ApiException as e:
            logger.error("Не удалось отредактировать пост: {}".format(e))
            return False

    # Проверка неактуальных постов
    def __checking_irrelevant_posts(self, pr_product_in_stock_list):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        from time import time
        time_start = time()

        # Проход по всем актуальным постам, их проверка на полную, частичную актуальность и неактуальность
        new_actual_posts_in_telegram_list = []
        for item in self.actual_posts_in_telegram_list:
            print(f"Время шага цикла: {time() - time_start} сек")
            time_start = time()
            time_start2 = time()
            # Получить список всех актуальных цен и данных на данную комплектацию:
            act_price_data_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                             (item.brand_name, item.model_name, item.ram, item.rom))
            print(f"  время 1: {time() - time_start2} сек")
            # Фильтрация списка актуальных цен с учетом наличия в магазинах
            act_price_data_in_stock_list = irr_post_search_data_in_stock(act_price_data_list, pr_product_in_stock_list)

            print(f"  время 1: {time() - time_start2} сек")
            # Список данных с минимальными актуальными ценами в наличии
            min_act_price_data_in_stock_list = irr_post_find_all_min_price_data(act_price_data_in_stock_list)

            print(f"  время 1: {time() - time_start2} сек")
            # Если минимальная цена отличается от цены в посте - ПОСТ ПОЛНОСТЬЮ НЕАКТУАЛЬНЫЙ
            if min_act_price_data_in_stock_list and min_act_price_data_in_stock_list[0][0] != item.cur_price:
                logger.info("Пост полностью неактуальный - есть более выгодное(ые) предложение(ия)")
                if not self.__edit_post_as_irrelevant(item):
                    new_actual_posts_in_telegram_list.append(item)
                continue

            print("item: {}".format(item))
            print("item.urls_list: {}".format(item.urls_list))
            print("item.shops_list: {}".format(item.shops_list))
            print("act_price_data_list: {}".format(act_price_data_list))
            print("act_price_data_in_stock_list: {}".format(act_price_data_in_stock_list))
            print("min_act_price_data_in_stock_list: {}".format(min_act_price_data_in_stock_list))

            print(f"  время 1: {time() - time_start2} сек")
            # Проверка других магазинов, в которых цена такая же выгодная. Если True - пост ПОЛНОСТЬЮ НЕАКТУАЛЬНЫЙ
            if irr_post_check_price_in_other_shop(min_act_price_data_in_stock_list, item.shops_list):
                logger.info("Пост полностью неактуальный - есть другие магазины с такой же ценой")
                if not self.__edit_post_as_irrelevant(item):
                    new_actual_posts_in_telegram_list.append(item)
                continue

            print(f"  время 2: {time() - time_start2} сек")
            # Получение неактуальных ссылок в посте
            irrelevant_url_list = irr_post_find_irr_url(act_price_data_in_stock_list, min_act_price_data_in_stock_list,
                                                        item.urls_list)

            print("irrelevant_url_list: {}".format(irrelevant_url_list))
            print("-" * 50)

            print(f"  время 3: {time() - time_start2} сек")
            # Если список пустой - пост ПОЛНОСТЬЮ АКТУАЛЬНЫЙ
            if not irrelevant_url_list:
                logger.info("Пост полностью актуальный:\n{}".format(item))
                new_actual_posts_in_telegram_list.append(item)
                continue

            print(f"  время 4: {time() - time_start2} сек")
            # Если кол-во неактуальных ссылок равно кол-ву ссылок в посте - пост ПОЛНОСТЬЮ НЕ АКТУАЛЬНЫЙ
            if len(irrelevant_url_list) == len(item.urls_list):
                logger.info("Пост полностью неактуальный - все ссылки неактуальны")
                if not self.__edit_post_as_irrelevant(item):
                    new_actual_posts_in_telegram_list.append(item)
                continue

            print(f"  время 5: {time() - time_start2} сек")
            logger.info("Пост частично актуальный")
            new_actual_posts_in_telegram_list.append(item)

            # Поиск неактуальных ссылок в тексте поста для пометки "неактуально"
            new_post_text = ""
            text_from_post = io.StringIO(item.text)
            for line in text_from_post:
                # Есть ли неактуальная ссылка (из списка) в текущей строке:
                if re.findall(r'|'.join(irrelevant_url_list), line):
                    new_post_text += "{} {}\n".format(line[:-1], self.irrelevant_url_text)
                else:
                    new_post_text += line

            print(f"  время 6: {time() - time_start2} сек")
            self.__edit_post_as_irrelevant(item, new_post_text, False)
            print(f"  время 7: {time() - time_start2} сек")

        self.actual_posts_in_telegram_list = new_actual_posts_in_telegram_list
        self.db.disconnect()

    # Запуск отправки новых постов
    def send_posts(self, pc_product_list):
        # pc_product_list = get_data()
        if not pc_product_list:
            logger.info("НЕТ ДАННЫХ ДЛЯ TELEGRAM")
            return

        self.pc_product_list = pc_product_list
        self.__filtering_data()
        self.__prepare_posts_and_send()
        save_stats_prods_dictionary()
        save_stats_shops_dictionary()
        self.__save_msg_in_telegram_list()
        self.__save_num_posts()

    # Запуск проверки на неактуальность постов
    def checking_irrelevant_posts(self, pr_product_in_stock_list):
        if not pr_product_in_stock_list:
            logger.error("НЕТ ДАННЫХ ДЛЯ НЕАКТУАЛЬНЫХ ПОСТОВ")
            return

        self.__checking_irrelevant_posts(pr_product_in_stock_list)
        self.__save_msg_in_telegram_list()
        self.__save_num_posts()


listtu = [(1111, 3, datetime(2020, 12, 16, 15, 31, 59, 687886), 'белый', 'https://www.dns-shop.ru/product/854dc0c06e3b1b80/65-smartfon-realme-6i-128-gb-belyj/'),
          (2222, 5, datetime(2020, 12, 16, 15, 31, 59, 690103), 'white', 'https://www.shop.mts.ru/product/smartfon-realme-6i-4-128gb-white'),
          (3333, 3, datetime(2020, 12, 16, 15, 32, 45, 739955), 'зеленый', 'https://www.dns-shop.ru/product/b5cb85606e3b1b80/65-smartfon-realme-6i-128-gb-zelenyj/'),
          (4444, 3, datetime(2020, 12, 16, 15, 31, 59, 691840), 'серый', 'https://www.dns-shop.ru/product/bf256b6f79643332/652-smartfon-realme-c3-64-gb-seryj/'),
          (5555, 1, datetime(2020, 12, 16, 15, 31, 59, 694720), 'volcano grey', 'https://www.mvideo.ru/products/smartfon-realme-c3-364gb-nfc-volcano-grey-rmx2020-30049951'),
          (6666, 1, datetime(2020, 12, 16, 15, 31, 59, 695397), 'blazing red', 'https://www.mvideo.ru/products/smartfon-realme-c3-364gb-nfc-blazing-red-rmx2020-30048602'),
          (7777, 3, datetime(2020, 12, 16, 15, 32, 45, 746571), 'красный', 'https://www.dns-shop.ru/product/96e2c63b5d003332/652-smartfon-realme-c3-64-gb-krasnyj/'),
          (8888, 3, datetime(2020, 12, 16, 15, 32, 45, 747695), 'синий', 'https://www.dns-shop.ru/product/848e429c5d003332/652-smartfon-realme-c3-64-gb-sinij/'),
          (9999, 5, datetime(2020, 12, 16, 15, 32, 45, 748380), 'grey', 'https://www.shop.mts.ru/product/smartfon-realme-c3-3-64gb-grey'),
          (1010, 1, datetime(2020, 12, 16, 15, 32, 45, 749052), 'frozen blue', 'https://www.mvideo.ru/products/smartfon-realme-c3-364gb-nfc-frozen-blue-rmx2020-30048601')]

url = 'https://www.dns-shop.ru/product/b5cb85606e3b1b80/65-smartfon-realme-6i-128-gb-zelenyj/'

# print(irr_post_find_price_data_by_url(listtu, url))
# bot = Bot()

# bot.db.connect_or_create("parser2", "postgres", "1990", "127.0.0.1", "5432")
# act_price_data_list = bot.db.execute_read_query(sr.search_actual_prices_by_version_query,
#                                                              ('samsung', 'galaxy s20', 8, 128))
# bot.db.disconnect()
#
# for item in act_price_data_list:
#     print(item)
#     print(item[1])


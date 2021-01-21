import re
import io
import time
import csv
import requests
import configparser
from datetime import datetime
import hashlib

import ast
import telebot
from telebot import types
from PIL import Image
from PIL import ImageEnhance

import bd
import header as h
import sql_req as sr
from post_image import PostImage

logger = h.logging.getLogger('bot')
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}
STATS_PRODS_DICT = {}
STATS_SHOPS_DICT = {}


# -------------------------- СЛОВАРИ -------------------------- #

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


# Сохранить на диск измененный словарь статистики товаров
def save_stats_prods_dictionary():
    with open(h.STATS_PRODS_DICTIONARY_PATH, 'w', encoding='UTF-8') as f:
        for key, val in STATS_PRODS_DICT.items():
            f.write('[{}] -> [{}]\n'.format(key, val))


# Чтение словаря с подсчетом кол-ва магазинов
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


# Сохранить на диск измененный словарь статистики магазинов
def save_stats_shops_dictionary():
    with open(h.STATS_SHOPS_DICTIONARY_PATH, 'w', encoding='UTF-8') as f:
        for key, val in STATS_SHOPS_DICT.items():
            f.write('[{}] -> [{}]\n'.format(key, val))


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


# -------------------------- ПОИСК -------------------------- #

# Поиск в строке названия фраз из списка исключения и их замена
def find_and_replace_except_model_name(model_name):
    # Поиск: есть ли какой-нибудь элемент из списка исключений в строке названия
    res = re.findall(r'|'.join(EXCEPT_MODEL_NAMES_TELEGRAM_DICT.keys()), model_name)
    # Если есть - подменяем
    if res:
        res = res[0]
        model_name = model_name.replace(res, EXCEPT_MODEL_NAMES_TELEGRAM_DICT.get(res))

    return model_name


# Проверить все элементы на равенство по заданной позиции
def all_elem_equal_in_tuple_list(elements, indx):
    if not elements or len(elements) == 1:
        return True

    data = elements[0][indx]
    for item in elements:
        if item[indx] != data:
            return False

    return True


# ----- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ АЛГОРИТМА НЕАКТУАЛЬНЫХ ПОСТОВ ----- #

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


# Для неактуальных постов: поиск среди всех данных только тех, что в наличии
def irr_post_search_data_in_stock(act_price_data_list, pr_product_in_stock_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    act_price_data_in_stock_list = []
    for act_price_data_item in act_price_data_list:
        if h.find_in_namedtuple_list(pr_product_in_stock_list, url=act_price_data_item[pos_url],
                                     limit_one=True):
            act_price_data_in_stock_list.append(act_price_data_item)

    return act_price_data_in_stock_list


# Для неактуальных постов: добавить элемент в список сообщений телеграм
def irr_post_add_item_in_msg_in_telegram_list(msg_telegram_list, max_element, item, new_hash, is_actual):
    new_item = h.MessagesInTelegram(message_id=item.message_id, category=item.category, brand_name=item.brand_name,
                                    model_name=item.model_name, ram=item.ram, rom=item.rom,
                                    cur_price=item.cur_price, avg_actual_price=item.avg_actual_price,
                                    img_url=item.img_url, where_buy_list=item.where_buy_list,
                                    hist_min_price=item.hist_min_price, hist_min_shop=item.hist_min_shop,
                                    hist_min_date=item.hist_min_date, post_datetime=item.post_datetime,
                                    text_hash=new_hash, is_actual=is_actual)

    # Проверка на переполнение списка
    if len(msg_telegram_list) >= max_element:
        logger.info("Список постов в телеграм полный, пробую удалить неактуальный")
        # Поиск индекса первого неактуального поста
        indx = 0
        for msg_item in msg_telegram_list:
            if not msg_item.is_actual:
                break
            indx += 1

        # Удаление старого неактуального
        if indx < len(msg_telegram_list):
            logger.info("Удаляю {}-й элемент".format(indx))
            msg_telegram_list.pop(indx)
        else:
            logger.warning("Не могу удалить, нет неактуальных")

    msg_telegram_list.append(new_item)


class Bot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.chat_id = self.config['bot']['chat_id']
        self.ignore_brands = self.config['bot-ignore']['brands'].lower().split('\n')
        self.bot = telebot.TeleBot(self.config['bot']['token'])
        self.one_star_per = float(self.config['bot-stars']['one_star_per'])
        self.two_star_per = float(self.config['bot-stars']['two_star_per'])
        self.three_star_per = float(self.config['bot-stars']['three_star_per'])
        self.four_star_per = float(self.config['bot-stars']['four_star_per'])
        self.five_star_per = float(self.config['bot-stars']['five_star_per'])
        self.irrelevant_url_text = self.config['bot']['irrelevant_url_text']
        self.hash_tag_actual = '#' + self.config['bot']['hash_tag_actual']
        self.max_num_act_post_telegram = int(self.config['bot']['max_num_act_post_telegram'])
        self.pc_product_list = []
        self.posts_in_telegram_list = []
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
            for item in self.posts_in_telegram_list:
                writer.writerow(item)

    # Загрузить данные с csv, чтобы не парсить сайт
    def __load_msg_in_telegram_list(self):
        with open(h.MESSAGES_IN_TELEGRAM_LIST_PATH, 'r', encoding='UTF-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=int(row['Message_ID']),
                    category=row['Category'],
                    brand_name=row['Brand'],
                    model_name=row['Model'],
                    ram=int(row['RAM']),
                    rom=int(row['ROM']),
                    cur_price=int(row['Cur_Price']),
                    avg_actual_price=float(row['Avg_Price']),
                    img_url=row['Img_URL'],
                    where_buy_list=ast.literal_eval(row['Where_Buy_List']),
                    hist_min_price=int(row['Hist_Min_Price']),
                    hist_min_shop=int(row['Hist_Min_Shop']),
                    hist_min_date=datetime.strptime(str(row['Hist_Min_Date']), '%Y-%m-%d %H:%M:%S.%f'),
                    post_datetime=datetime.strptime(str(row['Post_Datetime']), '%Y-%m-%d %H:%M:%S.%f'),
                    text_hash=row['Text_Hash'],
                    is_actual=(row['Actual'] == 'True'),
                ))

    # Подготовка текста для поста
    def __format_text(self, version_list, is_actual):
        product = version_list[0]
        # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
        text = find_and_replace_except_model_name('<b>{} {} {}</b>\n'.format(
            product.category[0:-1].title(), product.brand_name.title(), product.model_name.title()))

        # КОМПЛЕКТАЦИЯ
        text += '<b>{}/{} GB</b>\n\n'.format(product.ram, product.rom) \
            if (product.ram and product.brand_name != 'apple') \
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
            text += '<i>Минимальная цена {}</i> ₽ <i>была в {} {}</i>\n'.format(
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
        if is_actual:
            text += self.hash_tag_actual

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
        if h.find_in_namedtuple_list(self.posts_in_telegram_list, brand_name=item.brand_name,
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
        text = self.__format_text(version_list, True)
        img = PostImage(item.img_url).get_img()
        if not img:
            logger.error("No IMG in send post")
            return

        # Отправка поста в обертке
        for i in range(3):
            try:
                resp = self.bot.send_photo(chat_id=self.chat_id, photo=img, caption=text, parse_mode='Html',
                                           disable_notification=dis_notify)
                print(resp.message_id)
                logger.info(
                    "Создан новый пост, id={}, item={} {} {}/{} price={}".format(resp.message_id, item.brand_name,
                                                                                 item.model_name, item.ram,
                                                                                 item.rom, item.cur_price))

                # При успешной отправки добавляем данную позицию в список актуальных товаров
                self.posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=resp.message_id,
                    category=item.category,
                    brand_name=item.brand_name,
                    model_name=item.model_name,
                    ram=item.ram,
                    rom=item.rom,
                    cur_price=item.cur_price,
                    avg_actual_price=item.avg_actual_price,
                    img_url=item.img_url,
                    where_buy_list=[(item.shop, item.color, item.url) for item in version_list],
                    post_datetime=datetime.now(),
                    hist_min_price=item.hist_min_price,
                    hist_min_shop=item.hist_min_shop,
                    hist_min_date=item.hist_min_date,
                    text_hash=hashlib.sha256(text.encode()).hexdigest(),
                    is_actual=True,
                ))
                break

            except telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 30 сек, ({})".format(i + 1))
                time.sleep(30)

    # Отредактировать пост как частично или полностью неактуальный
    def __edit_post_as_irrelevant(self, post, text, current_actual):

        # Если пост был неактуальный и до сих пор неактуальный - выходим, менять нечего
        if not post.is_actual and not current_actual:
            logger.info("Пост был и остается неактуальным, не меняем")
            return True

        # Если есть изменения состояния, то обновляем пост вместе с картинкой, иначе только описание
        if post.is_actual != current_actual:
            logger.info("Изменение актуальности {} -> {}".format(post.is_actual, current_actual))

            # Генерация новой картинки
            img = PostImage(post.img_url)
            if not img.check():
                logger.error("No IMG in edit post")
                return False

            # Установка штампа
            if not current_actual:
                img.draw_stamp().change_bytes_img()

            # 5 попыток изменить пост (из-за бага телеграм)
            for i in range(5):
                if current_actual:
                    img.lighten()

                try:
                    self.bot.edit_message_media(
                        media=types.InputMediaPhoto(media=img.get_img(), caption=text, parse_mode='html'),
                        chat_id=self.chat_id, message_id=post.message_id)
                    logger.info("edit_message_media УСПЕШНО")

                    # Декремент кол-ва актуальных постов
                    self.num_actual_post += 1 if current_actual else (-1)
                    time.sleep(3)
                    return True

                except telebot.apihelper.ApiException as e:
                    logger.error("Не удалось отредактировать пост ({}) - edit_message_media: {}".format(i + 1, e))
                    img.save("cache/", "{}.jpg".format(post.message_id))
            else:
                logger.error("Не удалось отредактировать пост после 5 попыток")
                return False

        # Если пост не менял актуальность (true=true) и хэш сообщения изменился - обновляем описание поста
        if hashlib.sha256(text.encode()).hexdigest() != post.text_hash:
            try:
                self.bot.edit_message_caption(caption=text, parse_mode='html',
                                              chat_id=self.chat_id, message_id=post.message_id)
                logger.info("edit_message_caption УСПЕШНО")
                time.sleep(3)

            except telebot.apihelper.ApiException as e:
                logger.error("Не удалось отредактировать пост - edit_message_caption: {}".format(e))
                return False

        logger.info("В посте ничего не изменилось")
        return True

    # Проверка неактуальных постов
    def __checking_irrelevant_posts(self, pr_product_in_stock_list):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        # Проход по всем актуальным постам, их проверка на полную, частичную актуальность и неактуальность
        new_posts_in_telegram_list = []
        for item in self.posts_in_telegram_list:

            # Получить список всех актуальных цен и данных на данную комплектацию:
            act_price_data_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                             (item.brand_name, item.model_name, item.ram, item.rom))
            # Фильтрация списка актуальных цен с учетом наличия в магазинах
            act_price_data_in_stock_list = irr_post_search_data_in_stock(act_price_data_list, pr_product_in_stock_list)
            # Список данных с минимальными актуальными ценами в наличии
            min_act_price_data_in_stock_list = irr_post_find_all_min_price_data(act_price_data_in_stock_list)

            logger.info("-" * 50)
            logger.info("item: {}".format(item))
            logger.info("item actual: {}".format(item.is_actual))
            logger.info("act_price_data_list: {}".format(act_price_data_list))
            logger.info("act_price_data_in_stock_list: {}".format(act_price_data_in_stock_list))
            logger.info("min_act_price_data_in_stock_list: {}".format(min_act_price_data_in_stock_list))

            # Если минимальная цена отличается от цены в посте - ПОСТ ПОЛНОСТЬЮ НЕАКТУАЛЬНЫЙ
            is_actual = True
            if (min_act_price_data_in_stock_list and min_act_price_data_in_stock_list[0][0] != item.cur_price) or \
                    not min_act_price_data_in_stock_list:
                logger.info("Пост полностью неактуальный - есть более выгодное(ые) предложение(ия) или акция прошла")
                is_actual = False

            # Индексы структуры с данными о ссылках
            pos_shop, pos_color, pos_url = (1, 3, 4) if is_actual else (0, 1, 2)
            data_list = min_act_price_data_in_stock_list if is_actual else item.where_buy_list

            # Упаковка данных в структуру для генерации поста
            versions_list = []
            for data_item in data_list:
                versions_list.append(h.PriceChanges(shop=data_item[pos_shop],
                                                    category=item.category,
                                                    brand_name=item.brand_name,
                                                    model_name=item.model_name,
                                                    color=data_item[pos_color],
                                                    ram=item.ram,
                                                    rom=item.rom,
                                                    img_url=item.img_url,
                                                    url=data_item[pos_url],
                                                    date_time=None,
                                                    cur_price=item.cur_price,
                                                    avg_actual_price=item.avg_actual_price,
                                                    hist_min_price=item.hist_min_price,
                                                    hist_min_shop=item.hist_min_shop,
                                                    hist_min_date=item.hist_min_date,
                                                    diff_cur_avg=item.avg_actual_price - item.cur_price))

            if not versions_list:
                logger.error("Неизвестная ошибка с пустым versions_list, пропуск")
                continue

            new_text = self.__format_text(versions_list, is_actual)
            if not self.__edit_post_as_irrelevant(item, new_text, is_actual):
                logger.error("Не удалось отредактировать пост!")
                is_actual = True

            # Сохраняем пост в список постов
            irr_post_add_item_in_msg_in_telegram_list(new_posts_in_telegram_list,
                                                      self.max_num_act_post_telegram, item,
                                                      hashlib.sha256(new_text.encode()).hexdigest(), is_actual)

        self.posts_in_telegram_list = new_posts_in_telegram_list
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


# from admitad import api, items
#
# client_id = "O4soVKt8QcnbWsdqGzIYEJX1ZkXORC"
# client_secret = "lFJIDCMvSDpe34DnMgO2BvKHcCy4sT"
# scope = ' '.join(set([items.Me.SCOPE]))
#
# client = api.get_oauth_client_client(
#     client_id,
#     client_secret,
#     scope
# )
#
# print(client.Me.get())
#
# # res = client.DeeplinksManage.create(1649831, 21659, ulp=['https://www.mvideo.ru/products/smartfon-huawei-p40-lite-midnight-black-jny-lx1-30048480s',], subid='a20koellat')
# res = client.DeeplinksManage.create(1649831, 21659, ulp='https://shop.huawei.com/ru/product/huawei-p40-pro/', subid='a20kt')
#
#
# print(res)

from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler


# app = Client("my_account")
# if res[0].outgoing == False:
#     print("Сообщение от бота")


# def hui():
#     with Client("my_account") as app:
#         # @app.on_message(filters.user("@admitad_bot"))
#         # async def echo(client, msg):
#         #     print(msg.text)
#         #     await app.disconnect()
#
# # res = app.get_history("@admitad_bot", limit=2) # print(res) # print(res[0].outgoing) res = app.get_messages(
# "@admitad_bot", 189) print(res.text) print(res.outgoing) # app.send_message("@admitad_bot", #
# text="https://www.mvideo.ru/products/smartfon-apple-iphone-7-32gb-silver-mn8y2ru-a-30026136")
#
# hui()

# list_url = ['https://www.mvideo.ru/products/smartfon-apple-iphone-7-plus-32gb-black-mnqm2ru-a-30026229',
#             'https://www.mvideo.ru/products/smartfon-apple-iphone-6s-32gb-gold-mn112ru-a-30026284',
#             'https://www.mvideo.ru/products/smartfon-apple-iphone-8-plus-256gb-space-gray-mq8p2ru-a-30030160']
#
#
# async def get_deeplink(app, url_list):
#     urls = ', '.join(url_list)
#
#     # Отправка ссылок боту и получение id сообщения-ответа
#     res = await app.send_message("@admitad_bot", text=urls)
#     message_id = res.message_id + 1
#
#     # Ждем ответа от бота
#     while True:
#         res = await app.get_messages("@admitad_bot", message_id)
#         if not res.empty:
#             return res.text
#
#         time.sleep(0.5)
#
#
# app = Client("my_account")
# app.start()
# text = app.loop.run_until_complete(get_deeplink(app, list_url))
# print("text = {}".format(text))
# app.stop()
# for message in app.iter_history("@admitad_bot"):
#     print(message.text)


# app.start()
# res = app.send_message("@admitad_bot",
#                            text="https://www.mvideo.ru/products/smartfon-apple-iphone-12-128gb-black-mgja3ru-a-30052890")


# with Client("my_account") as app:
#     res = app.send_message("@admitad_bot",
#                            text="https://www.mvideo.ru/products/smartfon-apple-iphone-12-128gb-black-mgja3ru-a-30052890")


# app.run()

# app.run()

# app.run()
# with Client("my_account") as app:
#     app.send_message("me", "И еще привет!")


# from PIL import Image, ImageDraw
# from time import time
#
#
# def steganography_encrypt(text):
#     img = Image.open('cache/enc_img.png')
#     draw = ImageDraw.Draw(img)
#     pix = img.load()
#
#     indx = 0
#     for elem in ([ord(elem) for elem in text]):
#         for x in '{:08b}'.format(elem):
#             r, g, b = pix[indx, 0]
#             if not int(x):
#                 draw.point((indx, 0), (r, g, (b & 254)))
#             else:
#                 draw.point((indx, 0), (r, g, (b | 1)))
#             indx += 1
#
#     img.save("cache/newimage.png", "PNG")
#     return img
#
#
# def change_bytes_img():
#     img = Image.open('cache/enc_img.png')
#     draw = ImageDraw.Draw(img)
#     width, height = img.size
#     pix = img.load()
#
#     for i in range(width):
#         for j in range(height):
#             cur_pix = pix[i, j]
#             if cur_pix[0] > 240 and cur_pix[1] > 240 and cur_pix[2] > 240:
#                 draw.point((i, j), (cur_pix[0] ^ 0x07, cur_pix[1] ^ 0x07, cur_pix[2] ^ 0x07))
#             else:
#                 draw.point((i, j), (cur_pix[0] ^ 0x03, cur_pix[1] ^ 0x01, cur_pix[2] ^ 0x07))
#
#     return img
#
#
# def steganography_decrypt(len_text):
#     pix = Image.open('cache/newimage.png').load()  # создаём объект изображения
#     cipher_text = ""
#
#     for i in range(len_text):
#         one_char = 0
#         for j in range(8):
#             cur_bit = pix[(i * 8) + j, 0][2] & 1
#             one_char += cur_bit << (7 - j)
#         cipher_text += chr(one_char)
#
#     return cipher_text

# def check_div_two_img():
#     img1 = Image.open('cache/img_orig.png')
#     pix1 = img1.load()
#     pix2 = Image.open('cache/img_stamp.png').load()
#     width, height = img1.size
#
#     dif_pix = 0
#     all_pix = 0
#     for i in range(width):
#         for j in range(height):
#             all_pix += 1
#             cur_pix1 = pix1[i, j]
#             cur_pix2 = pix2[i, j]
#
#             if cur_pix1[0] != cur_pix2[0] or cur_pix1[1] != cur_pix2[1] or cur_pix1[2] != cur_pix2[2]:
#                 dif_pix += 1
#
#     print('dif_pix = {}, all_pix = {}'.format(dif_pix, all_pix))
#     print('per = {}%'.format(float(dif_pix/all_pix) * 100.0))


# check_div_two_img()

# indx1 = 0
# for item in list_url:
#     print(item)
#     img = PostImage(item)
#     img.change_bytes_img()
#     img.save('cache/dif/', str(indx1))
#     indx1 += 1
# from post_image import PostImage
#
# img = PostImage('https://mtscdn.ru/upload/iblock/f8d/smartfon_samsung_a415_galaxy_a41_4_64gb_white_1.jpg')
# img.get_img().show()
# img.change_bytes_img()
# img.get_img().show()
#

# # img123.save('cache/', 'img_orig')
# img123.draw_stamp()
# img123.darken()
# img123.save('cache/', 'img_stamp')


# output = [int(x) for x in '{:08b}'.format(num)]
# print(output)


# time_start = time()
# steganography_encrypt("Prodavach: https://t.me/prodavach_nsk")
# print("you message: '{}'".format(steganography_decrypt(37)))
# print(f"Время выполнения: {time() - time_start} сек")

import re
import time
import csv
import configparser
from datetime import datetime
import hashlib

import ast
import telebot

from modules.common import db_wrapper, sql_req as sr
import modules.common.helper as h
from modules.common.image_creator import ImageCreator
from pyrogram import Client
from pyrogram.types import InputMediaPhoto
import pyrogram.errors.exceptions as ex

from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('bot')
EXCEPT_MODEL_NAMES_TELEGRAM_DICT = {}
STATS_PRODS_DICT = {}
STATS_SHOPS_DICT = {}


# -------------------------- РЕФЕРАЛЬНЫЕ ССЫЛКИ -------------------------- #

def convert_url_for_ref_link(url):
    return url.replace(':', '%3A').replace('/', '%2F').strip()


# -------------------------- СЛОВАРИ -------------------------- #

def load_stats_prods_dictionary():
    """
    Чтение словаря с подсчетом кол-ва моделей
    """
    global STATS_PRODS_DICT
    STATS_PRODS_DICT = FileWorker.dict_data_str_int.load(h.STATS_PRODS_DICTIONARY_PATH)


def save_stats_prods_dictionary():
    """
    Сохранить на диск измененный словарь статистики товаров
    """
    FileWorker.dict_data.save(h.STATS_PRODS_DICTIONARY_PATH, data=STATS_PRODS_DICT)


def load_stats_shops_dictionary():
    """
    Чтение словаря с подсчетом кол-ва магазинов
    """
    global STATS_SHOPS_DICT
    STATS_SHOPS_DICT = FileWorker.dict_data_str_int.load(h.STATS_SHOPS_DICTIONARY_PATH)


def save_stats_shops_dictionary():
    """
    Сохранить на диск измененный словарь статистики магазинов
    """
    FileWorker.dict_data.save(h.STATS_SHOPS_DICTIONARY_PATH, data=STATS_SHOPS_DICT)


def load_exceptions_model_names_telegram():
    """
    Чтение словаря исключений названий моделей
    """
    global EXCEPT_MODEL_NAMES_TELEGRAM_DICT
    EXCEPT_MODEL_NAMES_TELEGRAM_DICT = FileWorker.dict_data.load(h.EXCEPT_MODEL_NAMES_TELEGRAM_PATH)


# ----- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ АЛГОРИТМА НЕАКТУАЛЬНЫХ ПОСТОВ ----- #

def irr_post_search_data_in_stock(act_price_data_list, pr_product_in_stock_list):
    """
    Для неактуальных постов: поиск среди всех данных только тех, что в наличии
    """
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    act_price_data_in_stock_list = []
    for act_price_data_item in act_price_data_list:
        if h.find_in_namedtuple_list(pr_product_in_stock_list, url=act_price_data_item[pos_url],
                                     limit_one=True):
            act_price_data_in_stock_list.append(act_price_data_item)

    return act_price_data_in_stock_list


def irr_post_add_item_in_msg_in_telegram_list(msg_telegram_list, max_element, item, new_hash, is_actual):
    """
    Для неактуальных постов: добавить элемент в список сообщений телеграм
    """
    new_item = h.MessagesInTelegram(message_id=item.message_id, category=item.category, brand_name=item.brand_name,
                                    model_name=item.model_name, ram=item.ram, rom=item.rom,
                                    price=item.price, avg_actual_price=item.avg_actual_price,
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
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataSender
    Класс, реализующий юзербота в телеграме, который выполняет сразу несколько функций:
        - Делает новые посты в канал (с генерацией текста и картинки)
        - Перепроверяет старые посты на актуальность и, в случае неактуальности обновляет
            данные или ставит штамп
    """

    def __init__(self):
        self.app = None
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.chat_id = int(self.config['bot']['chat_id'])
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
        # Рефералки
        self.domain_mts = self.config['admitad']['domain_mts']
        self.domain_mvideo = self.config['admitad']['domain_mvideo']
        self.domain_citilink = self.config['admitad']['domain_citilink']
        self.domain_eldorado = self.config['admitad']['domain_eldorado']
        self.ref_link_mts = self.config['admitad']['ref_link_mts']
        self.ref_link_mvideo = self.config['admitad']['ref_link_mvideo']
        self.ref_link_citilink = self.config['admitad']['ref_link_citilink']
        self.ref_link_eldorado = self.config['admitad']['ref_link_eldorado']

        self.pc_product_list = []
        self.posts_in_telegram_list = []
        self.num_all_post = 0
        self.num_actual_post = 0
        self.db = db_wrapper.DataBase()
        # Загрузка словаря исключений названий моделей для постов
        load_exceptions_model_names_telegram()
        load_stats_prods_dictionary()
        load_stats_shops_dictionary()
        self.__load_num_posts()
        self.__load_msg_in_telegram_list()

    def __enter__(self):
        logger.info("Запуск бота")
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Остановка бота")
        self.stop()

    def start(self):
        """
        Запуск бота
        """
        self.app = Client(h.BOT_ACCOUNT_PATH)
        self.app.start()

    def stop(self):
        """
        Остановка бота
        """
        self.app.stop()
        self.app = None

    def __load_num_posts(self):
        """
        Чтение кол-ва всех и актуальных постов
        """
        with open(h.NUM_POSTS_IN_TELEGRAM_PATH, 'r', encoding='UTF-8') as f:
            line1 = f.readline().replace('\n', '')
            self.num_all_post = int(line1) if line1 else 0
            line2 = f.readline().replace('\n', '')
            self.num_actual_post = int(line2) if line2 else 0

            logger.info("Num All Posts in Telegram = {}".format(self.num_all_post))
            logger.info("Num Actual Posts in Telegram = {}".format(self.num_actual_post))

    def __save_num_posts(self):
        """
        Сохранить на диск кол-во всех и актуальных постов
        """
        with open(h.NUM_POSTS_IN_TELEGRAM_PATH, 'w', encoding='UTF-8') as f:
            f.write(str(self.num_all_post))
            f.write('\n')
            f.write(str(self.num_actual_post))

    def __save_msg_in_telegram_list(self):
        """
        Сохранение всего результата в csv файл
        """
        with open(h.MESSAGES_IN_TELEGRAM_LIST_PATH, 'w', newline='', encoding='UTF-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_MSG_IN_TELEGRAM)
            for item in self.posts_in_telegram_list:
                writer.writerow(item)

    def __load_msg_in_telegram_list(self):
        """
        Загрузить данные о сообщениях в канале телеграм
        """
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
                    price=int(row['Price']),
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

    def __format_text(self, version_list, is_actual):
        """
        Подготовка текста для поста
        """
        product = version_list[0]
        # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
        text = h.find_allowed_model_names(EXCEPT_MODEL_NAMES_TELEGRAM_DICT, '<b>{} {} {}</b>\n'.format(
            product.category[0:-1].title(), product.brand_name.title(), product.model_name.title()))

        # КОМПЛЕКТАЦИЯ
        text += '<b>{}/{} GB</b>\n\n'.format(product.ram, product.rom) \
            if (product.ram and product.brand_name != 'apple') \
            else '<b>{} GB</b>\n\n'.format(product.rom)

        # ОГОНЬКИ
        per = float(100 - product.price / product.avg_actual_price * 100)
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
        s_price = '{0:,}'.format(product.price).replace(',', ' ')
        text += 'Выгодная цена: <b><i>{}</i></b> ₽\n'.format(s_price)
        s_price = '{0:,}'.format(int(product.avg_actual_price - product.price))
        text += '<i>(Дешевле на {}</i> ₽<i> от средней)</i>\n\n'.format(s_price).replace(',', ' ')

        # ИСТОРИЧЕСКИЙ МИНИМУМ
        if product.price <= product.hist_min_price:
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

            # Генерация ссылок → ► ● ○ • ›
            urls = ''
            for product in version_list:
                if product.shop == shop:
                    urls += '<a href="{}">► {}</a>\n'.format(self.get_ref_link(product.url), product.color.title())
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

    def __filtering_data(self):
        """
        Фильтрация входных данных - удаление дубликатов и применение игнор-листа
        """
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

    def __prepare_posts_and_send(self):
        """
        Разбор списка продуктов, группировка по цветам, отправка в телеграм
        """
        versions_list = []
        # Проход по всему списку, группировка элементов по версии и цвету, пост группы
        while self.pc_product_list:
            # Взятие группы комплектации с разными цветами
            item = self.pc_product_list[0]
            one_version_list = h.find_in_namedtuple_list(self.pc_product_list, brand_name=item.brand_name,
                                                         model_name=item.model_name, ram=item.ram, rom=item.rom,
                                                         price=item.price)
            # Составление списка комплектаций
            versions_list.append(one_version_list)
            # Удаление из основного списка взятой группы one_version_list
            for item in one_version_list:
                self.pc_product_list.remove(item)

        # Отправка постов в телеграм. Звук только у последних 2-ух
        for i in range(len(versions_list)):
            self.app.loop.run_until_complete(self.__send_post(versions_list[i], True if (i < (len(versions_list) - 2)) else False))
            # self.__send_post(versions_list[i], True if (i < (len(versions_list) - 2)) else False)

    async def __send_post(self, version_list, dis_notify):
        """
        Отправка поста в телеграм
        """
        item = version_list[0]

        # Проверка на наличие такого же поста в списке актуальных сообщений
        if h.find_in_namedtuple_list(self.posts_in_telegram_list, brand_name=item.brand_name,
                                     model_name=item.model_name, price=item.price, ram=item.ram,
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
        shops_set = list(set(item.shop for item in version_list))
        for shop_item in shops_set:
            shop_name = h.SHOPS_NAME_LIST[shop_item - 1][0]
            if shop_name in STATS_SHOPS_DICT:
                STATS_SHOPS_DICT[shop_name] += 1
            else:
                STATS_SHOPS_DICT[shop_name] = 1

        # Генерация поста
        text = self.__format_text(version_list, True)
        img = ImageCreator(item.img_url)
        if not img.check():
            logger.error("No IMG in send post")
            return

        img.lighten()

        img_name = 'img_{}'.format(datetime.now().timestamp())
        img.save_as_jpg('cache/for_send', img_name)
        time.sleep(1)

        # Отправка поста в обертке
        for i in range(3):
            try:
                resp = await self.app.send_photo(self.chat_id, 'cache/for_send/{}.jpg'.format(img_name), text, 'html', disable_notification=dis_notify)
                # resp = self.bot.send_photo(chat_id=self.chat_id, photo=img.get_img(), caption=text, parse_mode='Html',
                #                            disable_notification=dis_notify)
                print(resp.message_id)

                logger.info(
                    "Создан новый пост, id={}, item={} {} {}/{} price={}".format(resp.message_id, item.brand_name,
                                                                                 item.model_name, item.ram,
                                                                                 item.rom, item.price))

                # При успешной отправки добавляем данную позицию в список актуальных товаров
                self.posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=resp.message_id,
                    category=item.category,
                    brand_name=item.brand_name,
                    model_name=item.model_name,
                    ram=item.ram,
                    rom=item.rom,
                    price=item.price,
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

            except ex.bad_request_400.MessageNotModified: # telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 30 сек, ({})".format(i + 1))
                time.sleep(30)

    async def __edit_post_as_irrelevant(self, post, text, current_actual):
        """
        Отредактировать пост как частично или полностью неактуальный
        """
        # Если пост был неактуальный и до сих пор неактуальный - выходим, менять нечего
        if not post.is_actual and not current_actual:
            logger.info("Пост был и остается неактуальным, не меняем")
            return True

        # Если есть изменения состояния, то обновляем пост вместе с картинкой, иначе только описание
        if post.is_actual != current_actual:
            logger.info("Изменение актуальности {} -> {}".format(post.is_actual, current_actual))

            # Генерация новой картинки
            img = ImageCreator(post.img_url)
            if not img.check():
                logger.error("No IMG in edit post")
                return False

            # Установка штампа
            if not current_actual:
                img.change_bytes_img().draw_stamp().darken()
            else:
                img.lighten()

            img_name = 'img_{}'.format(datetime.now().timestamp())
            img.save_as_jpg('cache/for_send', img_name)
            time.sleep(1)
            # new_img = PostImage()
            # new_img.open('cache/for_send/{}.jpg'.format(img_name))

            # 5 попыток изменить пост (из-за бага телеграм)
            for i in range(3):

                try:
                    await self.app.edit_message_media(self.chat_id, post.message_id, InputMediaPhoto('cache/for_send/{}.jpg'.format(img_name), text, 'html'))
                    # self.bot.edit_message_media(
                    #     media=types.InputMediaPhoto(media=img.get_img(), caption=text, parse_mode='html'),
                    #     chat_id=self.chat_id, message_id=post.message_id)
                    logger.info("edit_message_media УСПЕШНО")

                    # Декремент кол-ва актуальных постов
                    self.num_actual_post += 1 if current_actual else (-1)
                    time.sleep(3)
                    return True

                except ex.bad_request_400.MessageNotModified as e: # telebot.apihelper.ApiException as e:
                    logger.error("Не удалось отредактировать пост ({}) - edit_message_media: {}".format(i + 1, e))
                    img.save_as_jpg("cache/", "{}.jpg".format(post.message_id))
                    img.lighten() if current_actual else img.darken()
            else:
                logger.error("Не удалось отредактировать пост после 5 попыток")
                return False

        # Если пост не менял актуальность (true=true) и хэш сообщения изменился - обновляем описание поста
        if hashlib.sha256(text.encode()).hexdigest() != post.text_hash:
            try:
                # self.bot.edit_message_caption(caption=text, parse_mode='html',
                #                               chat_id=self.chat_id, message_id=post.message_id)
                await self.app.edit_message_caption(self.chat_id, post.message_id, text, 'html')
                logger.info("edit_message_caption УСПЕШНО")
                time.sleep(3)

            except ex.bad_request_400.MessageNotModified as e: # telebot.apihelper.ApiException as e:
                logger.error("Не удалось отредактировать пост - edit_message_caption: {}".format(e))
                return False

        logger.info("В посте ничего не изменилось")
        return True

    def __checking_irrelevant_posts(self, pr_product_in_stock_list):
        """
        Проверка неактуальных постов
        """
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
            min_act_price_data_in_stock_list = h.find_min_price_in_prices_list(act_price_data_in_stock_list)

            logger.info("-" * 50)
            logger.info("item: {}".format(item))
            logger.info("item actual: {}".format(item.is_actual))
            logger.info("act_price_data_list: {}".format(act_price_data_list))
            logger.info("act_price_data_in_stock_list: {}".format(act_price_data_in_stock_list))
            logger.info("min_act_price_data_in_stock_list: {}".format(min_act_price_data_in_stock_list))

            # Если минимальная цена отличается от цены в посте - ПОСТ ПОЛНОСТЬЮ НЕАКТУАЛЬНЫЙ
            is_actual = True
            if (min_act_price_data_in_stock_list and min_act_price_data_in_stock_list[0][0] != item.price) or \
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
                                                    price=item.price,
                                                    avg_actual_price=item.avg_actual_price,
                                                    hist_min_price=item.hist_min_price,
                                                    hist_min_shop=item.hist_min_shop,
                                                    hist_min_date=item.hist_min_date,
                                                    diff_cur_avg=item.avg_actual_price - item.price))

            if not versions_list:
                logger.error("Неизвестная ошибка с пустым versions_list, пропуск")
                continue

            new_text = self.__format_text(versions_list, is_actual)

            ####
            if not self.app.loop.run_until_complete(self.__edit_post_as_irrelevant(item, new_text, is_actual)):
                logger.error("Не удалось отредактировать пост!")
                is_actual = True
            # if not self.__edit_post_as_irrelevant(item, new_text, is_actual):
            #     logger.error("Не удалось отредактировать пост!")
            #     is_actual = True

            # Сохраняем пост в список постов
            irr_post_add_item_in_msg_in_telegram_list(new_posts_in_telegram_list,
                                                      self.max_num_act_post_telegram, item,
                                                      hashlib.sha256(new_text.encode()).hexdigest(), is_actual)

        self.posts_in_telegram_list = new_posts_in_telegram_list
        self.db.disconnect()

    def send_posts(self, pc_product_list):
        """
        Запуск отправки новых постов
        """
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

    def checking_irrelevant_posts(self, pr_product_in_stock_list):
        """
        Запуск проверки на неактуальность постов
        """
        if not pr_product_in_stock_list:
            logger.error("НЕТ ДАННЫХ ДЛЯ НЕАКТУАЛЬНЫХ ПОСТОВ")
            return

        self.__checking_irrelevant_posts(pr_product_in_stock_list)
        self.__save_msg_in_telegram_list()
        self.__save_num_posts()

    def get_ref_link(self, url):
        """
        Получить реферальную ссылку
        """
        # Мвидео
        if self.domain_mvideo in url:
            return self.ref_link_mvideo + convert_url_for_ref_link(url)

        # МТС
        if self.domain_mts in url:
            return self.ref_link_mts + convert_url_for_ref_link(url)

        # Ситилинк
        if self.domain_citilink in url:
            return self.ref_link_citilink + convert_url_for_ref_link(url)

        # Эльдорадо
        if self.domain_eldorado in url:
            return self.ref_link_eldorado + convert_url_for_ref_link(url)

        return url

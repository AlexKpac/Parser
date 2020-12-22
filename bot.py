import re
import io
import time
import csv
import requests
import configparser
from datetime import datetime

import ast
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
        img = img.resize((new_width, new_height), Image.LANCZOS)

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
def irr_post_add_item_in_msg_in_telegram_list(msg_telegram_list, max_element, item, is_actual):
    new_item = h.MessagesInTelegram(message_id=item.message_id, category=item.category, brand_name=item.brand_name,
                                    model_name=item.model_name, ram=item.ram, rom=item.rom,
                                    cur_price=item.cur_price, avg_actual_price=item.avg_actual_price,
                                    img_url=item.img_url, where_buy_list=item.where_buy_list,
                                    hist_min_price=item.hist_min_price, hist_min_shop=item.hist_min_shop,
                                    hist_min_date=item.hist_min_date, post_datetime=item.post_datetime,
                                    is_actual=is_actual)

    # Проверка на переполнение списка
    if len(msg_telegram_list) >= max_element:
        logger.info("Список постов в телеграм полный, пробую удалить неактуальный")
        # Поиск индекса первого неактуального поста
        indx = 0
        for msg_item in msg_telegram_list:
            if not msg_item[1]:
                break
            indx += 1

        # Удаление старого неактуального
        if indx < len(msg_telegram_list):
            logger.info("Удаляю {}-й элемент".format(indx))
            msg_telegram_list.pop(indx)
        else:
            logger.warning("Не могу удалить, нет неактуальных")

    msg_telegram_list.append(new_item)


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
                    is_actual=True,
                ))
                break

            except telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 30 сек, ({})".format(i + 1))
                time.sleep(30)

    # Отредактировать пост как частично или полностью неактуальный. По-умолчанию полностью неактуальный
    def __edit_post_as_irrelevant(self, post, text, is_actual):

        # Если пост был неактуальный и до сих пор неактуальный - выходим, менять нечего
        if not post.is_actual and not is_actual:
            logger.info("Пост был и остается неактуальным, не меняем")
            return True

        change_actual = post.is_actual != is_actual

        # Если пост был неактуальный, а стал актуальный - создаем новое изображение
        img = None
        if change_actual:
            img = image_change(post.img_url, not is_actual)
            if not img:
                logger.error("No IMG in edit post")
                return False

        # Редактирование поста
        try:
            if change_actual:
                self.bot.edit_message_media(
                    media=types.InputMediaPhoto(media=img, caption=text, parse_mode='html'),
                    chat_id=self.chat_id, message_id=post.message_id)
            else:
                self.bot.edit_message_caption(caption=text, parse_mode='html',
                                              chat_id=self.chat_id, message_id=post.message_id)

            # Декремент кол-ва актуальных постов
            if change_actual:
                self.num_actual_post += 1 if is_actual else (-1)
            return True

        except telebot.apihelper.ApiException as e:
            logger.error("Не удалось отредактировать пост: {}".format(e))
            img.save("cache/{}.jpg".format(post.message_id), "jpeg")
            return False

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
            data_list = (min_act_price_data_in_stock_list if is_actual else item.where_buy_list)

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
                                                    diff_cur_avg=item.avg_actual_price-item.cur_price))

            if not versions_list:
                logger.error("Неизвестная ошибка с пустым versions_list, пропуск")
                continue

            new_text = self.__format_text(versions_list, is_actual)
            if not self.__edit_post_as_irrelevant(item, new_text, is_actual):
                logger.error("Не удалось отредактировать пост!")

            # Сохраняем пост в список постов
            irr_post_add_item_in_msg_in_telegram_list(new_posts_in_telegram_list,
                                                      self.max_num_act_post_telegram, item, is_actual)

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

#
# def dela(msg_telegram_list, max_element, item):
#
#     # Проверка на переполнение списка
#     if len(msg_telegram_list) >= max_element:
#         print("Список полный")
#         # Поиск индекса первого неактуального поста
#         indx = 0
#         for item1 in msg_telegram_list:
#             if not item1[1]:
#                 break
#             indx += 1
#
#         # Удаление старого неактуального
#         if indx < len(msg_telegram_list):
#             print('Пытаюсь удалить, indx = {}'.format(indx))
#             msg_telegram_list.pop(indx)
#         else:
#             print("Не могу удалить, нет неактуальных")
#
#     print("item = {}".format(item))
#     msg_telegram_list.append(item)
#
#
# from random import randint
#
# lista = []
# for i in range(13):
#     dela(lista, 5, (i, randint(0, 1)))
#     print(lista)
#     print()
#     print('-' * 50)
#     print()

# bot = Bot()
# bot.checking_irrelevant_posts([1,2])



# bot.send_posts([])
# bot = Bot()
#
# bot.db.connect_or_create("parser2", "postgres", "1990", "127.0.0.1", "5432")
# act_price_data_list = bot.db.execute_read_query(sr.search_actual_prices_by_version_query,
#                                                              ('samsung', 'galaxy s20', 8, 128))
# bot.db.disconnect()
#
# for item in act_price_data_list:
#     print(item)
#     print(type(item[0]))

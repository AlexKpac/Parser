import ast
import csv
import time
from datetime import datetime

import modules.common.helper as h
from modules.common.file_worker import FileWorker
from modules.common.image_creator import ImageCreator

logger = h.logging.getLogger('Bot')


# -------------------------- СТАТИСТИКА  -------------------------- #

def inc_stats_products(dictionary: dict, brand_name, model_name):
    """
    Обновление словаря статистики товаров
    """
    full_name = "{} {}".format(brand_name, model_name)
    if full_name in dictionary:
        dictionary[full_name] += 1
    else:
        dictionary[full_name] = 1


def inc_stats_shops(dictionary: dict, shop_list):
    """
    Обновление словаря статистики магазинов
    """
    for shop_item in shop_list:
        shop_name = h.SHOPS_NAME_LIST[shop_item - 1][0]
        if shop_name in dictionary:
            dictionary[shop_name] += 1
        else:
            dictionary[shop_name] = 1


# -------------------------- РЕФЕРАЛЬНЫЕ ССЫЛКИ -------------------------- #

def convert_url_for_ref_link(url):
    """
    Конвертирование url в специальный вид для реферальных ссылок
    """
    return url.replace(':', '%3A').replace('/', '%2F').strip()


def get_ref_link(url):
    """
    Получить реферальную ссылку
    """
    # Мвидео
    if h.DOMAIN_MVIDEO in url:
        return h.REF_LINK_MVIDEO + convert_url_for_ref_link(url)

    # МТС
    if h.DOMAIN_MTS in url:
        return h.REF_LINK_MTS + convert_url_for_ref_link(url)

    # Ситилинк
    if h.DOMAIN_CITILINK in url:
        return h.REF_LINK_CITILINK + convert_url_for_ref_link(url)

    # Эльдорадо
    if h.DOMAIN_ELDORADO in url:
        return h.REF_LINK_ELDORADO + convert_url_for_ref_link(url)

    return url


# -------------------------- СЛОВАРИ -------------------------- #

def load_num_posts():
    """
    Чтение кол-ва всех и актуальных постов
    """
    data_num_post = FileWorker.list_data_int.load(h.NUM_POSTS_IN_TELEGRAM_PATH)
    num_all_post, num_actual_post = data_num_post \
        if data_num_post and len(data_num_post) == 2 else (0, 0)

    return num_all_post, num_actual_post


def load_msg_in_telegram_list():
    """
    Загрузить данные о сообщениях в канале телеграм. FileWorker не подходит для этой задачи
    из-за обработки прочитанных данных
    """
    posts_in_telegram_list = []

    # Message Id,Category,Brand Name,Model Name,Ram,Rom,Price,Avg Actual Price,Img Url,Where Buy List,Hist Min Price,Hist Min Shop,Hist Min Date,Post Datetime,Text Hash,Is Actual
    with open(h.MESSAGES_IN_TELEGRAM_LIST_PATH, 'r', encoding='UTF-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts_in_telegram_list.append(h.MessagesInTelegram(
                message_id=int(row['Message ID']),
                category=row['Category'],
                brand_name=row['Brand Name'],
                model_name=row['Model Name'],
                ram=int(row['Ram']),
                rom=int(row['Rom']),
                price=int(row['Price']),
                avg_actual_price=float(row['Avg Actual Price']),
                img_url=row['Img Url'],
                where_buy_list=ast.literal_eval(row['Where Buy List']),
                hist_min_price=int(row['Hist Min Price']),
                hist_min_shop=int(row['Hist Min Shop']),
                hist_min_date=datetime.strptime(str(row['Hist Min Date']), '%Y-%m-%d %H:%M:%S.%f'),
                post_datetime=datetime.strptime(str(row['Post Datetime']), '%Y-%m-%d %H:%M:%S.%f'),
                text_hash=row['Text Hash'],
                is_actual=(row['Is Actual'] == 'True'),
            ))

    return posts_in_telegram_list


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
            msg_telegram_list.pop(indx)
            logger.info("Удаляю {}-й элемент".format(indx))
        else:
            logger.warning("Не могу удалить, нет неактуальных")

    msg_telegram_list.append(new_item)


# -------------------- ИЗОБРАЖЕНИЕ -------------------- #

def create_and_save_img_for_edit_post(img_url, is_actual):
    """
    Генерация изображения и сохранения его на диск.
    Возвращает полный путь к сохраненному изображению
    """
    img = ImageCreator(img_url)
    if not img.check():
        logger.error("No IMG in edit post")
        return None

    # Установка штампа
    if not is_actual:
        img.draw_stamp().darken()
    else:
        img.lighten()

    img_name = 'img_{}.jpg'.format(datetime.now().timestamp())
    img.save_as_jpg(h.IMAGE_FOR_SEND_IN_TELEGRAM_PATH, img_name)
    time.sleep(1)

    return h.IMAGE_FOR_SEND_IN_TELEGRAM_PATH + img_name

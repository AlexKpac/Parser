import re
import csv
import configparser
from time import time, sleep
import os
import socket

from data_source.parsers.dns_parse import DNSParse
from data_source.parsers.mvideo_parse import MVideoParse
from data_source.parsers.mts_parse import MTSParse
from data_source.parsers.eldorado_parse import EldoradoParse
from data_source.parsers.citilink_parse import CitilinkParse
from core.checker import Checker
from output.telegram.bot import Bot
import common.general_helper as h

logger = h.logging.getLogger('main')


# Проверка наличия подключения к сети
def check_internet():
    for timeout in [1, 5, 10, 15]:
        try:
            socket.setdefaulttimeout(timeout)
            host = socket.gethostbyname("www.google.com")
            s = socket.create_connection((host, 80), 2)
            s.close()
            return True

        except Exception:
            print("Нет интернета")
            sleep(5)
    return False


# Чтение словаря исключений названий моделей
def load_exceptions_model_names():
    with open(h.EXCEPT_MODEL_NAMES_PATH, 'r', encoding='UTF-8') as f:
        for line in f:
            res = re.findall(r"\[.+?]", line)
            # Отсечь кривые записи
            if len(res) != 2:
                continue
            # Добавить в словарь
            h.EXCEPT_MODEL_NAMES_DICT[res[0].replace('[', '').replace(']', '')] = \
                res[1].replace('[', '').replace(']', '')


# Чтение списка разрешенных названий моделей для добавления в БД
def load_allowed_model_names_list_for_base():
    with open(h.PATH_LIST_MODEL_NAMES_BASE, 'r', encoding='UTF-8') as f:
        h.ALLOWED_MODEL_NAMES_LIST_FOR_BASE = f.read().splitlines()


# Загрузить данные с csv, чтобы не парсить сайт
def load_result_from_csv(name):
    pr_result_list = []
    with open(h.CSV_PATH_RAW + name, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_result_list.append(h.ParseResult(
                shop=row['Магазин'],
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                cur_price=int(row['Цена']),
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                rating=float(row['Рейтинг']),
                num_rating=int(row['Кол-во отзывов']),
                product_code=row['Код продукта'],
            ))

    return pr_result_list


# Сохранение всего результата в csv файл
def save_result_list(elements):
    with open(h.CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(h.HEADERS)
        for item in elements:
            writer.writerow(item)


# Чтение данных
def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding="utf-8")
    h.REBUILT_IPHONE_NAME = ' ' + config.defaults()['rebuilt_iphone_name']
    h.IGNORE_WORDS_FOR_COLOR = config['parser']['color_ignore'].lower().split('\n')


# Удалить лок-файл
def del_lock_file():
    if os.path.isfile(h.PATH_UNDEFINED_MODEL_NAME_LIST_LOCK):
        os.remove(h.PATH_UNDEFINED_MODEL_NAME_LIST_LOCK)


# Создать лок файл, запрещающий сервисному боту читать файл с исключениями
def create_lock_file():
    del_lock_file()
    with open(h.PATH_UNDEFINED_MODEL_NAME_LIST_LOCK, 'w') as f:
        pass


def worker1():
    parser1 = MVideoParse()
    parser1.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")


def worker2():
    parser2 = DNSParse()
    parser2.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")


def worker3():
    parser3 = MTSParse()
    parser3.run_catalog("https://shop.mts.ru/catalog/smartfony/")


def worker4():
    parser4 = EldoradoParse()
    parser4.run_catalog("https://www.eldorado.ru/c/smartfony/")


if __name__ == '__main__':

    # Проверка наличия интернета перед выполнением программы
    # if not check_internet():
    #     raise SystemExit(2)
    # import multiprocessing
    #
    # time_start = time()
    # load_allowed_model_names_list_for_base()
    # load_exceptions_model_names()
    # read_config()
    #
    # for item in h.ALLOWED_MODEL_NAMES_LIST_FOR_BASE:
    #     print(item)
    #
    # time_start = time()
    # p1 = multiprocessing.Process(target=worker1)
    # p2 = multiprocessing.Process(target=worker2)
    # p3 = multiprocessing.Process(target=worker3)
    # p4 = multiprocessing.Process(target=worker4)
    # p1.start()
    # p2.start()
    # p3.start()
    # p4.start()
    # print("КОНЕЦ СТАРТОВ")
    # p1.join()
    # p2.join()
    # p3.join()
    # p4.join()
    # print("КОНЕЦ ДЖОИНОВ")
    # logger.info(f"Время выполнения: {time() - time_start} сек")

    # https://docs-python.ru/standart-library/paket-multiprocessing-python/

    time_start = time()
    h.del_old_logs()
    result_list = []

    load_allowed_model_names_list_for_base()
    load_exceptions_model_names()
    read_config()
    create_lock_file()
    #
    parser = MVideoParse()
    result = parser.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
    # result = load_result_from_csv("mvideo.csv")
    if not result:
        raise SystemExit(5)
    result_list.extend(result)
    #
    # parser = MTSParse()
    # result = parser.run_catalog("https://shop.mts.ru/catalog/smartfony/")
    # # result = load_result_from_csv("mts.csv")
    # if not result:
    #     raise SystemExit(5)
    # result_list.extend(result)
    #
    # parser = DNSParse()
    # result = parser.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
    # # result = load_result_from_csv("dns.csv")
    # if not result:
    #     raise SystemExit(5)
    # result_list.extend(result)
    #
    # parser = CitilinkParse()
    # result = parser.run_catalog("https://www.citilink.ru/catalog/mobile/smartfony/")
    # # result = load_result_from_csv("citilink.csv")
    # if not result:
    #     raise SystemExit(5)
    # result_list.extend(result)
    #
    # parser = EldoradoParse()
    # result = parser.run_catalog("https://www.eldorado.ru/c/smartfony/")
    # # result = load_result_from_csv("eldorado.csv")
    # if not result:
    #     raise SystemExit(5)
    # result_list.extend(result)
    #
    del_lock_file()
    save_result_list(result_list)

    # result_list = load_result_from_csv("goods2.csv")
    # check = Checker(result_list)
    # benefit_price_list = check.run()
    #
    # bot = Bot()
    # bot.checking_irrelevant_posts(result_list)
    # bot.send_posts(benefit_price_list)
    # bot.stop()

    logger.info(f"Время выполнения: {time() - time_start} сек")

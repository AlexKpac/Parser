import time
import re
import csv
import datetime
import configparser

import sql_req as sr
import bd
import header as h

logger = h.logging.getLogger('checker')


# Функция, которая вернет true, если хоть у одного поля поврежденные данные
def check_item_on_errors(item):
    e = "error"
    if item.category == e or \
            item.shop == e or \
            item.brand_name == e or \
            item.model_name == e or \
            item.color == e or \
            item.img_url == e or \
            item.product_code == e or \
            item.rom == 0 or \
            item.price == 0:
        return False
    else:
        return True


# Проверить все элементы на равенство
def all_elem_equal(elements):
    return len(elements) < 1 or len(elements) == elements.count(elements[0])


class Checker:
    def __init__(self, product_list):
        self.db = bd.DataBase()
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.min_diff_price_per = int(self.config.defaults()['min_diff_price_per'])
        self.product_list = product_list
        self.result = []

    def __check_price_in_db(self, cur_price, brand_name, model_name, ram, rom):
        # Получить список всех актуальных цен на данную комплектацию
        prices_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                 (brand_name, model_name, ram, rom))
        # Поиск средней цены
        avg_price = sum(item[0] for item in prices_list) / len(prices_list)
        # Поиск исторического минимума цены
        hist_min_price = self.db.execute_read_query(sr.search_min_historical_price_by_version_query,
                                                    (brand_name, model_name, ram, rom))

        print("check_price: len = {}, prices_list = {}".format(len(prices_list), prices_list))
        print("avg_price = {}".format(avg_price))
        print("hist_min_price = {}".format(hist_min_price))

        # Составление списка товаров, у которых цена ниже средней на self.min_diff_price_per%
        result_list = []
        for price in prices_list:
            if price[0] < avg_price:
                diff_per = 100 - (cur_price / avg_price * 100)
                if diff_per >= self.min_diff_price_per:
                    result_list.append(price)

        return (result_list if all_elem_equal(result_list) else [min(result_list)]), avg_price, *hist_min_price

    def __save_result(self):
        if not self.result:
            logger.info("НЕТ ЗАПИСЕЙ С ИЗМЕНЕНИЕМ ЦЕН")
            return

        with open(h.PRICE_CHANGES_PATH, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_PRICE_CHANGES)
            for item in self.result:
                writer.writerow(item)

    def run(self):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        for item in self.product_list:
            if not check_item_on_errors(item):
                logger.warning("Продукт {} {} с артиклом {} в магазине {} содержит 'error', SKIP".format(
                    item.brand_name, item.model_name, item.product_code, item.shop))
                continue

            # Сохранение данных в базу. Если цена изменилась - вернет предыдущую
            self.db.add_product_to_bd(
                category_name=item.category,
                shop_name=item.shop,
                brand_name=item.brand_name,
                model_name=item.model_name,
                var_color=item.color,
                var_ram=item.ram,
                var_rom=item.rom,
                price=item.price,
                img_url=item.img_url,
                url=item.url,
                product_code=item.product_code,
                local_rating=item.rating,
                num_rating=item.num_rating)

            result_list, avg_price, hist_min_price = 0

            # Если выявлено изменение цены - записать в список
            if result_list and avg_price and hist_min_price:
                for item_result in result_list:
                    self.price_changes.append(h.PriceChanges(
                        shop=item_result[1],
                        category=item.category,
                        brand_name=item.brand_name,
                        model_name=item.model_name,
                        color=item_result[2],
                        ram=item.ram,
                        rom=item.rom,
                        img_url=item.img_url,
                        url=item_result[3],
                        date_time=datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                        cur_price=item_result[0],
                        avg_actual_price=int(avg_price),
                        hist_min_price=hist_min_price[0],
                        hist_min_shop=hist_min_price[1],
                        hist_min_date=hist_min_price[2],
                        diff_cur_avg=int(avg_price - item_result[0]),
                    ))

        self.db.disconnect()

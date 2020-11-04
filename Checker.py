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

        # Добавление продукта в таблицу products_table

    def __insert_product_in_products_table(self, id_category_name, brand_name, model_name, total_rating):
        id_product = self.execute_read_query(sr.insert_into_products_table_query,
                                             [(id_category_name, brand_name, model_name, total_rating), ])

        return id_product[0][0] if id_product else None

        # Добавление комплектации в таблицу versions_phones_table

    def __insert_version_in_versions_phones_table(self, id_product, ram, rom, img_url):
        id_ver_phone = self.execute_read_query(sr.insert_into_versions_phones_table_query,
                                               [(id_product, ram, rom, img_url), ])

        return id_ver_phone[0][0] if id_ver_phone else None

        # Добавление магазина для покупки комплектации в shops_phones_table

    def __insert_shop_in_shops_phones_table(self, id_shop_name, id_product, id_ver_phone, url, product_code, var_color,
                                            local_rating, num_local_rating, bonus_rubles=0):
        id_shop_phone = self.execute_read_query(sr.insert_into_shops_phones_table_query,
                                                [(id_shop_name, id_product, id_ver_phone, url, product_code, var_color,
                                                  local_rating, num_local_rating, bonus_rubles), ])

        return id_shop_phone[0][0] if id_shop_phone else None

        # Добавление цены определенного магазина определенной комплектации в prices_phones_table

    def __insert_price_in_prices_phones_table(self, id_shop_name, id_product, id_shop_phone, price, datetime='now()'):
        self.execute_query(sr.insert_into_prices_phones_table_query,
                           [(id_shop_name, id_product, id_shop_phone, price, datetime), ])

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

    # Добавление спарсенного товара в БД
    def add_product_to_bd(self, category_name, shop_name, brand_name, model_name, var_rom, var_ram, var_color, img_url,
                          url, product_code, local_rating, num_rating, price, bonus_rubles=0):

        if not self.connection:
            logger.warning("Can't execute query - no connection")
            return False

        try:
            id_category_name = h.CATEGORIES_NAME_LIST.index((category_name,)) + 1
            id_shop_name = h.SHOPS_NAME_LIST.index((shop_name,)) + 1
        except ValueError as e:
            logger.error("ERROR get category_name or shop_name = {}".format(e))
            return False

        id_product = self.execute_read_query(sr.select_id_product_query, (brand_name, model_name))
        # + Продукт присутствует в #products_table
        if id_product:
            id_product = id_product[0][0]
            id_ver_phone = self.execute_read_query(sr.select_id_ver_phone_query,
                                                   (id_product, var_ram, var_rom))
            # ++ Комплектация присутствует в #version_phones_table
            if id_ver_phone:
                id_ver_phone = id_ver_phone[0][0]
                id_shop_phone = self.execute_read_query(sr.select_id_shop_phone_query,
                                                        (id_ver_phone, id_shop_name, product_code))

                # +++ Данную комплектацию можно купить в #shop_phones_table
                if id_shop_phone:
                    id_shop_phone = id_shop_phone[0][0]
                    price_phone = self.execute_read_query(sr.select_price_in_price_phone_query, (id_shop_phone,))

                    if not price_phone:
                        logger.error("Нет цены, id_prod = {}, "
                                     "id_ver = {}, id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                        return False

                    # ++++ Цена данной комплектации в данном магазине не изменилась - ничего не делаем
                    if price_phone[-1][0] == price:
                        print("NO CHANGE, IGNORE; "
                              "id_prod = {}, id_ver = {}, id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))

                    # ---- Цена данной комплектации в данном магазине изменилась - добавляем в список цен
                    else:
                        print("Новая цена на эту комплектацию в этом магазине, добавляю цену")
                        self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)

                        # Проверка изменения цены-если изменилась на нужный процент-вернет исторический минимум, иначе 0
                        if price < price_phone[-1][0]:
                            self.check_price_list.append(h.CheckPrice(
                                cur_price=price,
                                brand_name=brand_name,
                                model_name=model_name,
                                var_ram=var_ram,
                                var_rom=var_rom,
                            ))
                            # return self.check_price(price, brand_name, model_name, var_ram, var_rom)

                # --- Данную комплектацию нельзя купить, отсутствует в #shop_phones_table
                else:
                    print("Такой комплектации нет в данном магазине, добавляю магазин и цену")
                    id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                             url, product_code, var_color, local_rating,
                                                                             num_rating, bonus_rubles)
                    self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                    print("id_prod = {}, id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))

            # -- Комплектация отсутствует в #version_phones_table
            else:
                print("Данная комплектация отсутствует в списке комплектаций, добавляю комплектацию, магазин, цену")
                id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_ram, var_rom, img_url)
                id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                         url, product_code, var_color, local_rating,
                                                                         num_rating, bonus_rubles)
                self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                print("id_prod = {}, new id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))

        # - Продукт отсутствует в #products_table
        else:
            print("Данный продукт отсутствует в products_table, добавляю продукт, комплектацию, магазин, цену")
            id_product = self.__insert_product_in_products_table(id_category_name, brand_name, model_name, 0)
            id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_ram, var_rom, img_url)
            id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone, url,
                                                                     product_code, var_color, local_rating, num_rating,
                                                                     bonus_rubles)
            self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
            print("new id_prod = {}, new id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))

        return True

    # Запуск проверки товаров с измененной ценой на поиск выгоды
    def run_check_price(self):
        for item in self.check_price_list:
            self.check_price(item.price, item.brand_name, item.model_name, item.ram, item.rom)

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

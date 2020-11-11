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
def all_elem_equal_in_tuple_list(elements, indx):
    if not elements or len(elements) == 1:
        return True

    price = elements[0][indx]
    for item in elements:
        if item[indx] != price:
            return False

    return True


# Поиск элемента по заданным параметрам в nametuple ParseResult
def find_in_pr_price_change_list(nametuple, brand_name, model_name, ram, rom, price):
    if not nametuple:
        return False

    for item in nametuple:
        if item.brand_name == brand_name and \
                item.model_name == model_name and \
                item.ram == ram and \
                item.rom == rom and \
                item.price == price:
            return True

    return False


# Поиск элемента по заданным параметрам в nametuple PriceChanges
def find_in_pc_result_list(namedtuple, brand_name, model_name, ram, rom, price, shop, color):
    print('--nametuple={}'.format(namedtuple))
    print('--brand={}, model={}, ram={}, rom={}, price={}, shop={}, color={}'.format(brand_name, model_name, ram, rom, price, shop, color))
    if not namedtuple:
        return False

    for item in namedtuple:
        if item.brand_name == brand_name and \
                item.model_name == model_name and \
                item.ram == ram and \
                item.rom == rom and \
                item.cur_price == price and \
                item.shop == shop and \
                item.color == color:
            print('--TRUE')
            return True

    print('--FALSE')
    return False


# Вернет список с одним или несколькими магазинами и разными цветами, но с самыми низкими ценами
def find_min_price_in_prices_list(price_list):
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


class Checker:

    def __init__(self, parse_result_list):
        self.db = bd.DataBase()
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.min_diff_price_per = int(self.config.defaults()['min_diff_price_per'])
        self.pr_product_list = parse_result_list
        self.pr_price_change_list = []
        self.pc_result_list = []

    # Добавление продукта в таблицу products_table
    def __insert_product_in_products_table(self, id_category_name, brand_name, model_name, total_rating):
        id_product = self.db.execute_read_query(sr.insert_into_products_table_query,
                                                [(id_category_name, brand_name, model_name, total_rating), ])

        return id_product[0][0] if id_product else None

        # Добавление комплектации в таблицу versions_phones_table

    # Добавление комплектации в таблицу versions_phones_table
    def __insert_version_in_versions_phones_table(self, id_product, ram, rom, img_url):
        id_ver_phone = self.db.execute_read_query(sr.insert_into_versions_phones_table_query,
                                                  [(id_product, ram, rom, img_url), ])

        return id_ver_phone[0][0] if id_ver_phone else None

        # Добавление магазина для покупки комплектации в shops_phones_table

    # Добавление магазина, где продается комплектация в таблицу shops_phones_table
    def __insert_shop_in_shops_phones_table(self, id_shop_name, id_product, id_ver_phone, url, product_code, var_color,
                                            local_rating, num_local_rating, bonus_rubles=0):
        id_shop_phone = self.db.execute_read_query(sr.insert_into_shops_phones_table_query,
                                                   [(id_shop_name, id_product, id_ver_phone, url, product_code,
                                                     var_color,
                                                     local_rating, num_local_rating, bonus_rubles), ])

        return id_shop_phone[0][0] if id_shop_phone else None

        # Добавление цены определенного магазина определенной комплектации в prices_phones_table

    # Добавление цены в таблицу prices_phones_table
    def __insert_price_in_prices_phones_table(self, id_shop_name, id_product, id_shop_phone, price, date_time='now()'):
        self.db.execute_query(sr.insert_into_prices_phones_table_query,
                              [(id_shop_name, id_product, id_shop_phone, price, date_time), ])

    # Проверка списка товаров с измененной ценой на выгодное предложение
    def __check_price_for_benefit(self, cur_price, brand_name, model_name, ram, rom):
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

        null_result = (None, None, None)

        # Получить список всех актуальных цен на данную комплектацию
        prices_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                 (brand_name, model_name, ram, rom))
        if not prices_list:
            return null_result

        # Определить, данный товар продается только в одном магазине или нет
        is_one_shop = all_elem_equal_in_tuple_list(prices_list, pos_shop)
        # Поиск исторического минимума цены
        hist_min_price = self.db.execute_read_query(sr.search_all_prices_by_version_query,
                                                    (brand_name, model_name, ram, rom))
        if not hist_min_price:
            return null_result

        print('-' * 50)
        print("hist origin: {}".format(hist_min_price))

        # Если магазин один, то удалить последние добавленные актуальные цены
        indx = 0
        if is_one_shop:
            last_datetime = hist_min_price[0][pos_datetime]
            for item in hist_min_price:
                # if item[pos_price] == cur_price:
                if (last_datetime - item[pos_datetime]).total_seconds() < 1:
                    print('dif_time = {}'.format((last_datetime - item[pos_datetime]).total_seconds()))
                    indx += 1
                else:
                    break
            print('indx = {}, new hist: {}'.format(indx, hist_min_price[indx:]))
            hist_min_price = min(hist_min_price[indx:])
        else:
            hist_min_price = min(hist_min_price)

        print('hist_min = {}'.format(hist_min_price))
        # Поиск средней цены
        avg_price = ((cur_price + hist_min_price[pos_price]) / 2) if is_one_shop \
            else sum(item[pos_price] for item in prices_list) / len(prices_list)

        print('hist_min_price = {}'.format(hist_min_price[pos_price]))
        print('cur_price = {}, hist_min_price = {}'.format(cur_price, hist_min_price[0]))
        print('is_one_shop: {}'.format(is_one_shop))
        print("check_price: len = {}, prices_list = {}".format(len(prices_list), prices_list))
        print("avg_price = {}".format(avg_price))
        print("hist_min_price res = {}".format(hist_min_price))

        # Составление списка товаров, у которых цена ниже средней на self.min_diff_price_per%
        result_list = []
        for price in prices_list:
            if price[0] < avg_price and (datetime.datetime.now() - price[pos_datetime]).total_seconds() < 60:
                diff_per = 100 - (cur_price / avg_price * 100)
                if diff_per >= self.min_diff_price_per:
                    result_list.append(price)

        print('YES' if result_list else 'NO')

        return find_min_price_in_prices_list(result_list), avg_price, hist_min_price

    # Сохранение результата
    def __save_result(self):
        if not self.pc_result_list:
            logger.info("НЕТ ЗАПИСЕЙ С ИЗМЕНЕНИЕМ ЦЕН")
            return

        with open(h.PRICE_CHANGES_PATH, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_PRICE_CHANGES)
            for item in self.pc_result_list:
                writer.writerow(item)

    # Добавление спарсенного товара в БД
    def add_product_to_bd(self, category_name, shop_name, brand_name, model_name, var_rom, var_ram, var_color,
                          img_url, url, product_code, local_rating, num_rating, price, bonus_rubles=0):

        if not self.db.connection:
            logger.warning("Can't execute query - no connection")
            return 'error'

        try:
            id_category_name = h.CATEGORIES_NAME_LIST.index((category_name,)) + 1
            id_shop_name = h.SHOPS_NAME_LIST.index((shop_name,)) + 1
        except ValueError as e:
            logger.error("ERROR get category_name or shop_name = {}".format(e))
            return 'error'

        id_product = self.db.execute_read_query(sr.select_id_product_query, (brand_name, model_name))
        # + Продукт присутствует в #products_table
        if id_product:
            id_product = id_product[0][0]
            id_ver_phone = self.db.execute_read_query(sr.select_id_ver_phone_query,
                                                      (id_product, var_ram, var_rom))
            # ++ Комплектация присутствует в #version_phones_table
            if id_ver_phone:
                id_ver_phone = id_ver_phone[0][0]
                id_shop_phone = self.db.execute_read_query(sr.select_id_shop_phone_query,
                                                           (id_ver_phone, id_shop_name, product_code))

                # +++ Данную комплектацию можно купить в #shop_phones_table
                if id_shop_phone:
                    id_shop_phone = id_shop_phone[0][0]
                    price_phone = self.db.execute_read_query(sr.select_price_in_price_phone_query, (id_shop_phone,))

                    if not price_phone:
                        logger.error("Нет цены, id_prod = {}, "
                                     "id_ver = {}, id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                        return 'error'

                    # ++++ Цена данной комплектации в данном магазине не изменилась - ничего не делаем
                    if price_phone[-1][0] == price:
                        # Если ничего не изменилось - обновить дату у цены
                        self.db.execute_query(sr.update_datetime_in_price_phone_table_query, (id_product, id_ver_phone,
                                                                                              id_shop_phone, price))
                        print("NO CHANGE, IGNORE, UPDATE DATETIME; "
                              "id_prod = {}, id_ver = {}, id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))

                    # ---- Цена данной комплектации в данном магазине изменилась - добавляем в список цен
                    else:
                        print("Новая цена на эту комплектацию в этом магазине, добавляю цену")
                        self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                        return 'price'

                # --- Данную комплектацию нельзя купить, отсутствует в #shop_phones_table
                else:
                    print("Такой комплектации нет в данном магазине, добавляю магазин и цену")
                    id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                             url, product_code, var_color, local_rating,
                                                                             num_rating, bonus_rubles)
                    self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                    print("id_prod = {}, id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                    return 'version'

            # -- Комплектация отсутствует в #version_phones_table
            else:
                print("Данная комплектация отсутствует в списке комплектаций, добавляю комплектацию, магазин, цену")
                id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_ram, var_rom, img_url)
                id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                         url, product_code, var_color, local_rating,
                                                                         num_rating, bonus_rubles)
                self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                print("id_prod = {}, new id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                return 'shop'

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
            return 'product'

        return 'error'

    # Запуск проверки товаров с измененной ценой на поиск выгоды
    def check_prices(self, pr_price_change_list=None):
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

        if not pr_price_change_list:
            pr_price_change_list = self.pr_price_change_list

        for item in pr_price_change_list:
            print(item)

        for item in pr_price_change_list:
            result_list, avg_price, hist_min_price = self.__check_price_for_benefit(item.price,
                                                                                    item.brand_name,
                                                                                    item.model_name,
                                                                                    item.ram, item.rom)

            for item11 in result_list:
                print('==item11={}'.format(item11))

            # Если выявлено изменение цены - записать в список
            if result_list and avg_price and hist_min_price:
                for item_result in result_list:
                    # Для исключительных ситуаций: проверка, что такого элемента с такой ценой и цветом еще нет в списке
                    if not find_in_pc_result_list(self.pc_result_list, item.brand_name, item.model_name, item.ram,
                                                  item.rom, item_result[pos_price], item_result[pos_shop],
                                                  item_result[pos_color]):
                        self.pc_result_list.append(h.PriceChanges(
                            shop=item_result[pos_shop],
                            category=item.category,
                            brand_name=item.brand_name,
                            model_name=item.model_name,
                            color=item_result[pos_color],
                            ram=item.ram,
                            rom=item.rom,
                            img_url=item.img_url,
                            url=item_result[pos_url],
                            date_time=datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                            cur_price=item_result[pos_price],
                            avg_actual_price=int(avg_price),
                            hist_min_price=hist_min_price[pos_price],
                            hist_min_shop=hist_min_price[pos_shop],
                            hist_min_date=hist_min_price[pos_datetime],
                            diff_cur_avg=int(avg_price - item_result[pos_price]),
                        ))

    # Добавление всех товаров в базу
    def adding_all_products_to_db(self, pr_product_list=None):

        if not pr_product_list:
            pr_product_list = self.pr_product_list

        if not pr_product_list:
            logger.warning('pr_product_list is empty')
            return

        for item in pr_product_list:
            # Проверка элемента на некорректные поля
            if not check_item_on_errors(item):
                logger.warning("Продукт {} {} с артиклом {} в магазине {} содержит 'error', SKIP".format(
                    item.brand_name, item.model_name, item.product_code, item.shop))
                continue

            # Сохранение данных в базу. Если цена изменилась - вернет предыдущую
            resp = self.add_product_to_bd(
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

            # Если при добавлении товара в базу была изменена только цена -
            # добавляем в очередь на проверку выгоды
            if resp == 'price' and not find_in_pr_price_change_list(self.pr_price_change_list, item.brand_name,
                                                                    item.model_name,
                                                                    item.ram, item.rom, item.price):
                print(item)
                self.pr_price_change_list.append(item)

    # Запуск
    def run(self):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
        self.adding_all_products_to_db()
        if not len(self.pr_price_change_list):
            logger.info('СПИСОК ПРОДУКТОВ НА ПРОВЕРКУ ВЫГОДЫ ПУСТ')
        self.check_prices()
        self.db.disconnect()
        self.__save_result()

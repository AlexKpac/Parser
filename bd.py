import psycopg2
from psycopg2 import OperationalError
from psycopg2 import extras
import sql_req as sr
import header as h
import configparser
import collections

logger = h.logging.getLogger('bd')


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


class DataBase:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_name_basic = "postgres"
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.min_diff_price_per = int(self.config.defaults()['min_diff_price_per'])
        self.check_price_list = []

    # Создание таблиц, если они отсутствуют и заполнение вспомогательных данными
    def __create_tables_and_views(self):
        self.execute_query(sr.create_categories_name_table_query)
        self.execute_query(sr.create_shops_name_table_query)
        self.execute_query(sr.create_products_table_query)
        self.execute_query(sr.create_versions_phones_table_query)
        self.execute_query(sr.create_shops_phones_table_query)
        self.execute_query(sr.create_prices_phone_table_query)

        self.execute_query(sr.create_view_general_table_query)

        self.__insert_shops_name_table()
        self.__insert_category_name()

    # Заполнить таблицу shops_name_table данными
    def __insert_shops_name_table(self):
        if not self.connection:
            print("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, "INSERT INTO shops_name_table (Shop_Name) VALUES %s",
                                  h.SHOPS_NAME_LIST)
        except OperationalError as e:
            print("The error '{}' occurred".format(e))

    # Заполнить таблицу categories_name_table данными
    def __insert_category_name(self):
        if not self.connection:
            print("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, "INSERT INTO categories_name_table (Category_Name) VALUES %s",
                                  h.CATEGORIES_NAME_LIST)
        except OperationalError as e:
            print("The error '{}' occurred".format(e))

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

    # Соединение с базой данных
    def connect(self, db_name, db_user, db_password, db_host, db_port):
        if not self.connection:
            self.disconnect()
            self.connection = None

        try:
            self.connection = psycopg2.connect(
                database=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
            )

            print("Connection to PostgreSQL DB '{}' successful".format(db_name))
            self.connection.autocommit = True
            self.cursor = self.connection.cursor()
        except OperationalError as e:
            print("The error '{}' occurred".format(e))
            return False

        return True

    # Создание базы данных
    def create_database(self, db_name):
        if not self.connection:
            print("Can't create database - no connection")
            return False

        create_database_query = "CREATE DATABASE " + db_name
        try:
            self.cursor.execute(create_database_query)
        except OperationalError as e:
            print("The error '{}' occurred".format(e))
            return False

        return True

    # Попытка подключиться к запрашиваемой БД, если не получилось - создание этой БД
    def connect_or_create(self, db_name, db_user, db_password, db_host, db_port):
        # Попытка подключится к запрашиваемой базе данных
        if not self.connect(db_name, db_user, db_password, db_host, db_port):

            # Если такой базы не существует, подключаемся к основной и создаем новую
            print("Data base '{}' not found".format(db_name))
            if self.connect(self.db_name_basic, db_user, db_password, db_host, db_port):

                # Если подключились к основной - создаем свою
                if self.create_database(db_name):

                    # Если получилось создать новую базу данных - соединяемся с ней
                    print("Data base '{}' created".format(db_name))
                    if not self.connect(db_name, db_user, db_password, db_host, db_port):
                        return False
                    self.__create_tables_and_views()
        return True

    # Отправка sql запроса в БД
    def execute_query(self, query, variables=None):
        if not self.connection:
            print("Can't execute query - no connection")
            return False

        try:
            self.cursor.execute(query, variables)
        except OperationalError as e:
            print("The error '{}' occurred".format(e))
            return False

        return True

    # Чтение данных с таблицы
    def execute_read_query(self, query, variables=None):
        if not self.connection:
            print("Can't execute read query - no connection")
            return None

        result = None
        try:
            if variables:
                self.cursor.execute(query, variables)
            else:
                self.cursor.execute(query)

            result = self.cursor.fetchall()
            return result

        except OperationalError as e:
            print("The error '{}' occurred".format(e))
            return None

    # Отсоединение от БД
    def disconnect(self):
        if self.cursor:
            self.cursor.close()

        if self.connection:
            self.connection.close()

    # Проверка текущего товара на самую выгодную цену
    def check_price(self, cur_price, brand_name, model_name, ram, rom):
        # Получить список всех актуальных цен на данную комплектацию
        prices_list = self.execute_read_query(sr.search_actual_prices_by_version_query,
                                              (brand_name, model_name, ram, rom))
        # Поиск средней цены
        avg_price = sum(item[0] for item in prices_list) / len(prices_list)
        # Поиск исторического минимума цены
        hist_min_price = self.execute_read_query(sr.search_min_historical_price_by_version_query,
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

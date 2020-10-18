import psycopg2
from psycopg2 import OperationalError
from psycopg2 import extras
import sql_req as sr

# Список названий магазинов
SHOPS_NAME_LIST = [
    ('мвидео',),
    ('эльдорадо',),
    ('dns',),
    ('технопоинт',),
    ('мтс',),
    ('ситилинк',),
    ('rbt',),
    ('онлайнтрейд',),
    ('связной',),
    ('техносити',),
    ('билайн',),
    ('мегафон',),
    ('e2e4',),
    ('ноу-хау',),
]

# Список категорий
CATEGORIES_NAME_LIST = [
    ('смартфоны',),
    ('ноутбуки',),
]


class DataBase:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_name_basic = "postgres"

    # Создание таблиц, если они отсутствуют и заполнение вспомогательных данными
    def __create_table(self):
        self.execute_query(sr.create_categories_name_table_query)
        self.execute_query(sr.create_shops_name_table_query)
        self.execute_query(sr.create_products_table_query)
        self.execute_query(sr.create_versions_phones_table_query)
        self.execute_query(sr.create_shops_phones_table_query)
        self.execute_query(sr.create_prices_phone_table_query)

        self.__insert_shops_name_table()
        self.__insert_category_name()

    # Заполнить таблицу shops_name_table данными
    def __insert_shops_name_table(self):
        if not self.connection:
            print("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, "INSERT INTO shops_name_table (Shop_Name) VALUES %s",
                                  SHOPS_NAME_LIST)
        except OperationalError as e:
            print(f"The error '{e}' occurred")

    # Заполнить таблицу categories_name_table данными
    def __insert_category_name(self):
        if not self.connection:
            print("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, "INSERT INTO categories_name_table (Category_Name) VALUES %s",
                                  CATEGORIES_NAME_LIST)
        except OperationalError as e:
            print(f"The error '{e}' occurred")

    # Добавление продукта в таблицу products_table
    def __insert_product_in_products_table(self, id_category_name, brand_name, model_name, total_rating):
        id_product = self.execute_read_query(sr.insert_into_products_table_query,
                                             [(id_category_name, brand_name, model_name, total_rating), ])

        return id_product[0][0] if id_product else None

    # Добавление комплектации в таблицу versions_phones_table
    def __insert_version_in_versions_phones_table(self, id_product, color, ram, rom, img_url):
        id_ver_phone = self.execute_read_query(sr.insert_into_versions_phones_table_query,
                                               [(id_product, color, ram, rom, img_url), ])

        return id_ver_phone[0][0] if id_ver_phone else None

    # Добавление магазина для покупки комплектации в shops_phones_table
    def __insert_shop_in_shops_phones_table(self, id_shop_name, id_product, id_ver_phone, url, product_code,
                                            local_rating, num_local_rating):
        id_shop_phone = self.execute_read_query(sr.insert_into_shops_phones_table_query,
                                                [(id_shop_name, id_product, id_ver_phone, url, product_code,
                                                  local_rating, num_local_rating), ])

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

            print(f"Connection to PostgreSQL DB '{db_name}' successful")
            self.connection.autocommit = True
            self.cursor = self.connection.cursor()
        except OperationalError as e:
            print(f"The error '{e}' occurred")
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
            print(f"The error '{e}' occurred")
            return False

        return True

    # Попытка подключиться к запрашиваемой БД, если не получилось - создание этой БД
    def connect_or_create(self, db_name, db_user, db_password, db_host, db_port):
        # Попытка подключится к запрашиваемой базе данных
        if not self.connect(db_name, db_user, db_password, db_host, db_port):

            # Если такой базы не существует, подключаемся к основной и создаем новую
            print(f"Data base '{db_name}' not found")
            if self.connect(self.db_name_basic, db_user, db_password, db_host, db_port):

                # Если подключились к основной - создаем свою
                if self.create_database(db_name):

                    # Если получилось создать новую базу данных - соединяемся с ней
                    print(f"Data base '{db_name}' created")
                    if not self.connect(db_name, db_user, db_password, db_host, db_port):
                        return False
                    self.__create_table()
        return True

    # Отправка sql запроса в БД
    def execute_query(self, query, variables=None):
        if not self.connection:
            print("Can't execute query - no connection")
            return False

        try:
            self.cursor.execute(query, variables)
        except OperationalError as e:
            print(f"The error '{e}' occurred")
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
            print(f"The error '{e}' occurred")
            return None

    # Отсоединение от БД
    def disconnect(self):
        if self.cursor:
            self.cursor.close()

        if self.connection:
            self.connection.close()

    # Добавление спарсенного товара в БД
    def add_product_to_bd(self, category_name, shop_name, brand_name, model_name, var_rom, var_ram, var_color, img_url,
                          url, product_code, local_rating, num_rating, price):

        if not self.connection:
            print("Can't execute query - no connection")
            return

        try:
            id_category_name = CATEGORIES_NAME_LIST.index((category_name,)) + 1
            id_shop_name = SHOPS_NAME_LIST.index((shop_name,)) + 1
        except ValueError as e:
            print("ERROR get category_name or shop_name = {}".format(e))
            return

        id_product = self.execute_read_query(sr.select_id_product_query, (brand_name, model_name))
        # + Продукт присутствует в #products_table
        if id_product:
            id_product = id_product[0][0]; print("id_product = {}".format(id_product))
            id_ver_phone = self.execute_read_query(sr.select_id_ver_phone_query,
                                                   (id_product, var_color, var_ram, var_rom))
            # ++ Комплектация присутствует в #version_phones_table
            if id_ver_phone:
                id_ver_phone = id_ver_phone[0][0]; print("id_ver_phone = {}".format(id_ver_phone))
                id_shop_phone = self.execute_read_query(sr.select_id_shop_phone_query,
                                                        (id_ver_phone, id_shop_name))

                # +++ Данную комплектацию можно купить в #shop_phones_table
                if id_shop_phone:
                    id_shop_phone = id_shop_phone[0][0]; print("id_shop_phone = {}".format(id_shop_phone))
                    price_phone = self.execute_read_query(sr.select_price_in_price_phone_query, (id_shop_phone,))

                    # ++++ Цена данной комплектации в данном магазине не изменилась - ничего не делаем
                    if price_phone[-1][0] == price:
                        print("add_product_to_bd: NO CHANGE, IGNORE")

                    # ---- Цена данной комплектации в данном магазине изменилась - добавляем в список цен
                    else:
                        print("Новая цена на эту комплектацию в этом магазине, добавляю цену")
                        self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)

                # --- Данную комплектацию нельзя купить, отсутствует в #shop_phones_table
                else:
                    print("Такой комплектации нет в данном магазине, добавляю магазин и цену")
                    id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone, url, product_code, local_rating, num_rating)
                    self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)

            # -- Комплектация отсутствует в #version_phones_table
            else:
                print("Данная комплектация отсутствует в списке комплектаций, добавляю комплектацию, магазин, цену")
                id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_color, var_ram, var_rom, img_url)
                id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone, url, product_code, local_rating, num_rating)
                self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)

        # - Продукт отсутствует в #products_table
        else:
            print("Данный продукт отсутствует в products_table, добавляю продукт, комплектацию, магазин, цену")
            id_product = self.__insert_product_in_products_table(id_category_name, brand_name, model_name, 0)
            id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_color, var_ram, var_rom, img_url)
            id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone, url, product_code, local_rating, num_rating)
            self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)


# db = DataBase()
# db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
#
# db.add_product_to_bd(category_name="смартфоны",
#                      shop_name="dns",
#                      brand_name="Samsung",
#                      model_name="S10",
#                      var_color="белый",
#                      var_ram=6,
#                      var_rom=128,
#                      price=48990,
#                      img_url="http://url_img",
#                      url="http://url_shop",
#                      product_code="1212",
#                      local_rating=4.5,
#                      num_rating=130)
#
# db.disconnect()

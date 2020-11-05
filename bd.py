import psycopg2
from psycopg2 import OperationalError
from psycopg2 import extras
import sql_req as sr
import header as h
import configparser
import sys

logger = h.logging.getLogger('bd')


class DataBase:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_name_basic = "postgres"

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
            logger.error("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, sr.insert_into_shops_name_table_query, h.SHOPS_NAME_LIST)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))

    # Заполнить таблицу categories_name_table данными
    def __insert_category_name(self):
        if not self.connection:
            logger.error("Can't execute read query - no connection")
            return

        try:
            extras.execute_values(self.cursor, sr.insert_into_categories_name_table_query, h.CATEGORIES_NAME_LIST)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))

    # Создание базы данных
    def create_database(self, db_name):
        if not self.connection:
            logger.error("Can't create database - no connection")
            return False

        try:
            self.cursor.execute(sr.create_database_query + db_name)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))
            return False

        return True

    # Соединение с базой данных
    def connect(self, db_name, db_user, db_password, db_host, db_port):
        if self.connection:
            self.disconnect()

        try:
            self.connection = psycopg2.connect(
                database=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
            )

            logger.info("Connection to PostgreSQL DB '{}' successful".format(db_name))
            self.connection.autocommit = True
            self.cursor = self.connection.cursor()
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))
            return False

        return True

    # Попытка подключиться к запрашиваемой БД, если не получилось - создание этой БД
    def connect_or_create(self, db_name, db_user, db_password, db_host, db_port):
        # Попытка подключится к запрашиваемой базе данных
        if not self.connect(db_name, db_user, db_password, db_host, db_port):

            # Если такой базы не существует, подключаемся к основной и создаем новую
            logger.info("Data base '{}' not found, create '{}'".format(db_name, db_name))
            if self.connect(self.db_name_basic, db_user, db_password, db_host, db_port):

                # Если подключились к основной - создаем свою
                if self.create_database(db_name):

                    # Если получилось создать новую базу данных - соединяемся с ней
                    logger.error("Data base '{}' created".format(db_name))
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
            logger.error("Can't execute read query - no connection")
            return None

        try:
            if variables:
                self.cursor.execute(query, variables)
            else:
                self.cursor.execute(query)

            result = self.cursor.fetchall()
            return result

        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))
            return None

    # Отсоединение от БД
    def disconnect(self):
        if self.cursor:
            self.cursor.close()

        if self.connection:
            self.connection.close()

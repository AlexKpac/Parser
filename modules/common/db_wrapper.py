import psycopg2
from psycopg2 import OperationalError
from modules.common import sql_req as sr, helper as h

logger = h.logging.getLogger('DBWrapper')


class DataBase:
    """
    ВСПОМОГАТЕЛЬНЫЙ КЛАСС
    Класс, реализующий взаимодейтсвие с БД PostgreSQL.

    :method connect: Подключение к БД
    :method create_database: Создание базы данных
    :method connect_or_create: Попытка подключиться к запрашиваемой БД, если не получилось - создание этой БД
    :method execute_query: Отправка sql запроса в БД
    :method execute_read_query: Отправка sql запроса в БД с получением ответа
    :method disconnect: Отключение от БД
    :method __create_tables_and_views: Создание таблиц, если они отсутствуют и заполнение вспомогательных данными.
        Необходимо реализовать отдельные методы по созданию и заполнению таблиц и вызывать их здесь.
    """
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_name_basic = "postgres"

    def __create_tables_and_views(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Создание таблиц, если они отсутствуют и заполнение вспомогательных данными
        """
        self.execute_query(sr.create_categories_name_table_query)
        self.execute_query(sr.create_shops_name_table_query)

        self.__insert_shops_name_table()
        self.__insert_category_name()

        self.execute_query(sr.create_products_table_query)
        self.execute_query(sr.create_versions_phones_table_query)
        self.execute_query(sr.create_shops_phones_table_query)
        self.execute_query(sr.create_prices_phone_table_query)

        self.execute_query(sr.create_view_general_table_query)

    def __insert_shops_name_table(self):
        """
        Заполнить таблицу shops_name_table данными
        """
        if not self.connection:
            logger.error("Can't execute read query - no connection")
            return

        try:
            psycopg2.extras.execute_values(self.cursor, sr.insert_into_shops_name_table_query, h.SHOPS_NAME_LIST)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))

    def __insert_category_name(self):
        """
        Заполнить таблицу categories_name_table данными
        """
        if not self.connection:
            logger.error("Can't execute read query - no connection")
            return

        try:
            psycopg2.extras.execute_values(self.cursor, sr.insert_into_categories_name_table_query, h.CATEGORIES_NAME_LIST)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))

    def create_database(self, db_name):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Создание базы данных
        """
        if not self.connection:
            logger.error("Can't create database - no connection")
            return False

        try:
            self.cursor.execute(sr.create_database_query + db_name)
        except OperationalError as e:
            logger.error("The error '{}' occurred".format(e))
            return False

        return True

    def connect(self, db_name, db_user, db_password, db_host, db_port):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Соединение с базой данных
        """
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

    def connect_or_create(self, db_name, db_user, db_password, db_host, db_port):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Попытка подключиться к запрашиваемой БД, если не получилось - создание этой БД
        """
        # Попытка подключится к запрашиваемой базе данных
        if self.connect(db_name, db_user, db_password, db_host, db_port):
            logger.info("Connected to Database {}".format(db_name))
            return True

        # Если такой базы не существует, подключаемся к основной и создаем новую
        logger.info("Database '{}' not found, create '{}'".format(db_name, db_name))
        if not self.connect(self.db_name_basic, db_user, db_password, db_host, db_port):
            logger.error("Basic Database '{}' not found!".format(self.db_name_basic))
            return False

        # Если подключились к основной - создаем свою
        if not self.create_database(db_name):
            logger.error("Can't create new Database '{}'".format(db_name))
            return False

        # Если получилось создать новую базу данных - соединяемся с ней
        logger.info("Data base '{}' created".format(db_name))
        if not self.connect(db_name, db_user, db_password, db_host, db_port):
            return False

        self.__create_tables_and_views()
        return True

    def execute_query(self, query, variables=None):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Отправка sql запроса в БД
        """
        if not self.connection:
            logger.info("Can't execute query - no connection")
            return False

        try:
            self.cursor.execute(query, variables)
        except OperationalError as e:
            logger.info("The error '{}' occurred".format(e))
            return False

        return True

    def execute_read_query(self, query, variables=None):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Чтение данных с таблицы
        """
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

    def disconnect(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Отсоединение от БД
        """
        if self.cursor:
            self.cursor.close()

        if self.connection:
            self.connection.close()

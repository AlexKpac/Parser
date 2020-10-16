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
        self.execute_query(sr.create_shop_buy_table_query)
        self.execute_query(sr.create_version_phones_table_query)
        self.execute_query(sr.create_prices_table_query)

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
    def connect_else_create(self, db_name, db_user, db_password, db_host, db_port):
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
            if variables:
                self.cursor.execute(query, variables)
            else:
                self.cursor.execute(query)

            print("Query executed successfully")
        except OperationalError as e:
            print(f"The error '{e}' occurred")
            return False

        return True

    # Чтение данных с таблицы
    def execute_read_query(self, query):
        if not self.connection:
            print("Can't execute read query - no connection")
            return None

        result = None
        try:
            self.cursor.execute(query)
            result = self.cursor.fetchall()
            return result

        except OperationalError as e:
            print(f"The error '{e}' occurred")
            return None

    # Отсоединение от БД
    def disconnect(self):
        if self.cursor:
            del self.cursor

        if self.connection:
            del self.connection


db = DataBase()
db.connect_else_create("parser", "postgres", "1990", "127.0.0.1", "5432")

# # Заполнение данными
# users = [
#     ("James", 25, "male", "USA"),
#     ("Leila", 32, "female", "France"),
#     ("Brigitte", 35, "female", "England"),
#     ("Mike", 40, "male", "Denmark"),
#     ("Elizabeth", 21, "female", "Canada"),
# ]
# posts = [
#     ("Happy", "I am feeling very happy today", 1),
#     ("Hot Weather", "The weather is very hot today", 2),
#     ("Help", "I need some help with my work", 2),
#     ("Great News", "I am getting married", 1),
#     ("Interesting Game", "It was a fantastic game of tennis", 5),
#     ("Party", "Anyone up for a late-night party today?", 3),
# ]
#
# user_records = ", ".join(["%s"] * len(users))
# post_records = ", ".join(["%s"] * len(posts))
#
# insert_query = f"INSERT INTO users (name, age, gender, nationality) VALUES {user_records}"
# db.execute_query(insert_query, users)
#
# insert_query = f"INSERT INTO posts (title, description, user_id) VALUES {post_records}"
# db.execute_query(insert_query, posts)

# Чтение данных
# users = db.execute_read_query(select_users)

# for user in users:
#     print(user)

db.disconnect()

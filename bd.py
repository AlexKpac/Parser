import psycopg2
from psycopg2 import OperationalError

# Таблица Категории - categories_name_table
create_categories_name_table_query = """
CREATE TABLE IF NOT EXISTS categories_name_table (
  "ID_Category"        SERIAL PRIMARY KEY,
  "Category_Name"      VARCHAR(50) NOT NULL
);
"""

# Таблица: Магазины - shops_name_table
create_shops_name_table_query = """
CREATE TABLE IF NOT EXISTS shops_name_table (
  "ID_Shop_Name"     SERIAL PRIMARY KEY,
  "Shop_Name"        VARCHAR(20) NOT NULL
);
"""

# Таблица: Продукты - products_table
create_products_table_query = """
CREATE TABLE IF NOT EXISTS products_table (
  "ID_Product"       SERIAL PRIMARY KEY,
  "ID_Category"      INTEGER REFERENCES categories_name_table("ID_Category"),
  "Brand_Name"       VARCHAR(20) NOT NULL,
  "Model_Name"       VARCHAR(100) NOT NULL,
  "Total_Rating"     REAL
);
"""

# Таблица: В каком магазине купить продукт - shop_buy_table
create_shop_buy_table_query = """
CREATE TABLE IF NOT EXISTS shop_buy_table (
  "ID_Shop_Buy"      SERIAL PRIMARY KEY,
  "ID_Shop_Name"     INTEGER REFERENCES shops_name_table("ID_Shop_Name"),
  "ID_Category"      INTEGER REFERENCES categories_name_table("ID_Category"),
  "ID_Product"       INTEGER REFERENCES products_table("ID_Product"),
  "URL_Product"      VARCHAR(100) NOT NULL,
  "Product_Code"     VARCHAR(20) NOT NULL,
  "Local_Rating"     REAL,
  "Num_Local_Rating" INTEGER
);
"""

# Таблица: Комплектации телефонов - version_phones_table
create_version_phones_table_query = """
CREATE TABLE IF NOT EXISTS version_phones_table (
  "ID"               SERIAL PRIMARY KEY,
  "ID_Product"       INTEGER REFERENCES products_table("ID_Product"),
  "ID_Shop_Buy"      INTEGER REFERENCES shop_buy_table("ID_Shop_Buy"),
  "Color"            VARCHAR(50) NOT NULL,
  "RAM"              INTEGER NOT NULL,
  "ROM"              INTEGER NOT NULL,
  "Img_URL"          VARCHAR(100) NOT NULL
);
"""

# Таблица: Цены всех товаров - prices_table
create_prices_table_query = """
CREATE TABLE IF NOT EXISTS prices_table (
  "ID"               SERIAL PRIMARY KEY,
  "ID_Shop_Buy"      INTEGER REFERENCES shop_buy_table("ID_Shop_Buy"),
  "ID_Shop_Name"     INTEGER REFERENCES shops_name_table("ID_Shop_Name"),
  "ID_Product"       INTEGER REFERENCES products_table("ID_Product"),
  "ID_Category"      INTEGER REFERENCES categories_name_table("ID_Category"),
  "Price"            INTEGER NOT NULL,
  "Datetime"         TIMESTAMP NOT NULL
);
"""


class DataBase:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_name_basic = "postgres"

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

    def create_database(self, db_name):
        if not self.connection:
            print("Can't create database - no connection")
            return False

        create_database_query = "CREATE DATABASE " + str.lower(db_name)
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
                    self.create_table()
        return True

    def create_table(self):
        self.execute_query(create_categories_name_table_query)
        self.execute_query(create_shops_name_table_query)
        self.execute_query(create_products_table_query)
        self.execute_query(create_shop_buy_table_query)
        self.execute_query(create_version_phones_table_query)
        self.execute_query(create_prices_table_query)

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

    def disconnect(self):
        if self.cursor:
            self.cursor.close()

        if self.connection:
            self.connection.close()


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

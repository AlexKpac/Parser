import psycopg2
from psycopg2 import OperationalError

# Создание таблицы ...
create_users_table = """
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL, 
  age INTEGER,
  gender TEXT,
  nationality TEXT
)
"""
# Создание таблицы ...
create_posts_table = """
CREATE TABLE IF NOT EXISTS posts (
  id SERIAL PRIMARY KEY, 
  title TEXT NOT NULL, 
  description TEXT NOT NULL, 
  user_id INTEGER REFERENCES users(id)
)
"""
# Поиск юзеров
select_users = "SELECT * FROM users"


class BD:
    def __init__(self):
        self.connection = None
        self.cursor = None

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
            print("Connection to PostgreSQL DB successful")
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

        # self.cursor = connection.cursor()
        try:
            self.cursor.execute(create_database_query)
            print("Query executed successfully")
        except OperationalError as e:
            print(f"The error '{e}' occurred")
            return False

        return True

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


bd = BD()

# Подключение к общей БД
bd.connect("postgres", "postgres", "1990", "127.0.0.1", "5432")
#
# Создание своей БД
bd.create_database("parser")

# Подключение к своей БД
bd.connect("parser", "postgres", "1990", "127.0.0.1", "5432")

print(bd.connection)

# Создание таблицы
bd.execute_query(create_users_table)

# Создание таблицы
bd.execute_query(create_posts_table)

# Заполнение данными
users = [
    ("James", 25, "male", "USA"),
    ("Leila", 32, "female", "France"),
    ("Brigitte", 35, "female", "England"),
    ("Mike", 40, "male", "Denmark"),
    ("Elizabeth", 21, "female", "Canada"),
]
posts = [
    ("Happy", "I am feeling very happy today", 1),
    ("Hot Weather", "The weather is very hot today", 2),
    ("Help", "I need some help with my work", 2),
    ("Great News", "I am getting married", 1),
    ("Interesting Game", "It was a fantastic game of tennis", 5),
    ("Party", "Anyone up for a late-night party today?", 3),
]

user_records = ", ".join(["%s"] * len(users))
post_records = ", ".join(["%s"] * len(posts))

insert_query = (
    f"INSERT INTO users (name, age, gender, nationality) VALUES {user_records}"
)

bd.execute_query(insert_query, users)

insert_query = (
    f"INSERT INTO posts (title, description, user_id) VALUES {post_records}"
)

bd.execute_query(insert_query, posts)

# Чтение данных
users = bd.execute_read_query(select_users)

for user in users:
    print(user)

bd.disconnect()

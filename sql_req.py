# Таблица Категории - categories_name_table
create_categories_name_table_query = """
CREATE TABLE IF NOT EXISTS categories_name_table (
  ID_Category      SERIAL PRIMARY KEY,
  Category_Name    VARCHAR(50) NOT NULL
);
"""

# Таблица: Магазины - shops_name_table
create_shops_name_table_query = """
CREATE TABLE IF NOT EXISTS shops_name_table (
  ID_Shop_Name     SERIAL PRIMARY KEY,
  Shop_Name        VARCHAR(20) NOT NULL
);
"""

# Таблица: Продукты - products_table
create_products_table_query = """
CREATE TABLE IF NOT EXISTS products_table (
  ID_Product       SERIAL PRIMARY KEY,
  ID_Category      INTEGER REFERENCES categories_name_table(ID_Category),
  Brand_Name       VARCHAR(20) NOT NULL,
  Model_Name       VARCHAR(100) NOT NULL,
  Total_Rating     REAL
);
"""

# Таблица: В каком магазине купить продукт - shop_buy_table
create_shop_buy_table_query = """
CREATE TABLE IF NOT EXISTS shop_buy_table (
  ID_Shop_Buy      SERIAL PRIMARY KEY,
  ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name),
  ID_Category      INTEGER REFERENCES categories_name_table(ID_Category),
  ID_Product       INTEGER REFERENCES products_table(ID_Product),
  URL_Product      VARCHAR(100) NOT NULL,
  Product_Code     VARCHAR(20) NOT NULL,
  Local_Rating     REAL,
  Num_Local_Rating INTEGER
);
"""

# Таблица: Комплектации телефонов - version_phones_table
create_version_phones_table_query = """
CREATE TABLE IF NOT EXISTS version_phones_table (
  ID               SERIAL PRIMARY KEY,
  ID_Product       INTEGER REFERENCES products_table(ID_Product),
  ID_Shop_Buy      INTEGER REFERENCES shop_buy_table(ID_Shop_Buy),
  Color            VARCHAR(50) NOT NULL,
  RAM              INTEGER NOT NULL,
  ROM              INTEGER NOT NULL,
  Img_URL          VARCHAR(100) NOT NULL
);
"""

# Таблица: Цены всех товаров - prices_table
create_prices_table_query = """
CREATE TABLE IF NOT EXISTS prices_table (
  ID               SERIAL PRIMARY KEY,
  ID_Shop_Buy      INTEGER REFERENCES shop_buy_table(ID_Shop_Buy),
  ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name),
  ID_Product       INTEGER REFERENCES products_table(ID_Product),
  ID_Category      INTEGER REFERENCES categories_name_table(ID_Category),
  Price            INTEGER NOT NULL,
  Datetime         TIMESTAMP NOT NULL
);
"""
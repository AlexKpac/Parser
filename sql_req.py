# --------------------- СОЗДАНИЕ ТАБЛИЦ ------------------------------

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

# Таблица: Комплектации телефонов - versions_phones_table
create_versions_phones_table_query = """
    CREATE TABLE IF NOT EXISTS versions_phones_table (
        ID_Ver_Phone     SERIAL PRIMARY KEY,
        ID_Product       INTEGER REFERENCES products_table(ID_Product),
        Color            VARCHAR(50) NOT NULL,
        RAM              INTEGER NOT NULL,
        ROM              INTEGER NOT NULL,
        Img_URL          VARCHAR(100) NOT NULL
    );
"""

# Таблица: В каком магазине купить продукт - shop_buy_table
create_shops_phones_table_query = """
    CREATE TABLE IF NOT EXISTS shops_phones_table (
        ID_Shop_Phone    SERIAL PRIMARY KEY,
        ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name),
        ID_Product       INTEGER REFERENCES products_table(ID_Product),
        ID_Ver_Phone     INTEGER REFERENCES versions_phones_table(ID_Ver_Phone),
        URL_Product      VARCHAR(100) NOT NULL,
        Product_Code     VARCHAR(20) NOT NULL,
        Local_Rating     REAL,
        Num_Local_Rating INTEGER
    );
"""

# Таблица: Цены всех товаров - prices_phones_table
create_prices_phone_table_query = """
    CREATE TABLE IF NOT EXISTS prices_phones_table (
        ID               SERIAL PRIMARY KEY,
        ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name),
        ID_Product       INTEGER REFERENCES products_table(ID_Product),
        ID_Shop_Phone    INTEGER REFERENCES shops_phones_table(ID_Shop_Phone),
        Price            INTEGER NOT NULL,
        Datetime         TIMESTAMP NOT NULL
    );
"""

# --------------------------- ЗАПРОСЫ К БД -----------------------------

# Поиск товара в таблице products_table
select_id_product_query = """
    SELECT id_product FROM products_table 
    WHERE 
        brand_name = %s AND 
        model_name = %s
"""

# Поиск комплектации в таблице versions_phones_table
select_id_ver_phone_query = """
    SELECT id_ver_phone FROM versions_phones_table 
    WHERE 
        id_product = %s AND 
        color = %s      AND
        ram = %s        AND
        rom = %s
"""

# Поиск наличия в магазине данной комплектации в таблице shops_phones_table
select_id_shop_phone_query = """
    SELECT id_shop_phone FROM shops_phones_table 
    WHERE 
        id_ver_phone = %s AND 
        id_shop_name = %s
"""

# Поиск наличия цены у данного магазина данной комплектации в таблице price_phones_table
select_price_in_price_phone_query = """
    SELECT price FROM prices_phones_table 
    WHERE 
        id_shop_phone = %s
"""

# --------------------------- ЗАПИСЬ В БД ----------------------------

# Добавление цены в prices_phone
insert_into_prices_phones_table_query = """
    INSERT INTO prices_phones_table (id_shop_name, id_product, id_shop_phone, price, datetime) 
    VALUES %s
"""

insert_into_shops_phones_table_query = """
    INSERT INTO shops_phones_table (id_shop_name, id_product, id_ver_phone, url_product, product_code,
                                   local_rating, num_local_rating)
    VALUES %s
    RETURNING id_shop_phone
"""

insert_into_versions_phones_table_query = """
    INSERT INTO versions_phones_table (id_product, color, ram, rom, img_url)
    VALUES %s
    RETURNING id_ver_phone
"""

insert_into_products_table_query = """
    INSERT INTO products_table (id_category, brand_name, model_name, total_rating)
    VALUES %s
    RETURNING id_product
"""
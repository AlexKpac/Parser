# --
# Создание БД
create_database_query = "CREATE DATABASE "

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
        ID_Category      INTEGER REFERENCES categories_name_table(ID_Category) NOT NULL,
        Brand_Name       VARCHAR(20) NOT NULL,
        Model_Name       VARCHAR(100) NOT NULL,
        Total_Rating     REAL
    );
"""

# Таблица: Комплектации телефонов - versions_phones_table
create_versions_phones_table_query = """
    CREATE TABLE IF NOT EXISTS versions_phones_table (
        ID_Ver_Phone     SERIAL PRIMARY KEY,
        ID_Product       INTEGER NOT NULL,
        RAM              INTEGER NOT NULL,
        ROM              INTEGER NOT NULL,
        Img_URL          VARCHAR(200) NOT NULL,
        
        FOREIGN KEY (ID_Product)
            REFERENCES products_table(ID_Product) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE CASCADE
            NOT VALID
    );
"""

# Таблица: В каком магазине купить продукт - shop_buy_table
create_shops_phones_table_query = """
    CREATE TABLE IF NOT EXISTS shops_phones_table (
        ID_Shop_Phone    SERIAL PRIMARY KEY,
        ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name) NOT NULL,
        ID_Product       INTEGER NOT NULL,
        ID_Ver_Phone     INTEGER NOT NULL,
        URL_Product      VARCHAR(200) NOT NULL,
        Product_Code     VARCHAR(20) NOT NULL,
        Color            VARCHAR(50) NOT NULL,
        Local_Rating     REAL,
        Num_Local_Rating INTEGER,
        Bonus_Rubles     INTEGER,
        
        FOREIGN KEY (ID_Ver_Phone)
            REFERENCES versions_phones_table(ID_Ver_Phone) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE CASCADE
            NOT VALID
    );
"""

# Таблица: Цены всех товаров - prices_phones_table
create_prices_phone_table_query = """
    CREATE TABLE IF NOT EXISTS prices_phones_table (
        ID               SERIAL PRIMARY KEY,
        ID_Shop_Name     INTEGER REFERENCES shops_name_table(ID_Shop_Name) NOT NULL,
        ID_Product       INTEGER NOT NULL,
        ID_Shop_Phone    INTEGER NOT NULL,
        Price            INTEGER NOT NULL,
        Datetime         TIMESTAMP NOT NULL,
        
        FOREIGN KEY (ID_Shop_Phone)
            REFERENCES shops_phones_table(ID_Shop_Phone) MATCH SIMPLE
            ON UPDATE NO ACTION
            ON DELETE CASCADE
            NOT VALID
    );
"""

# ----------------------- СОЗДАНИЕ ПРЕДСТАВЛЕНИЙ --------------------------

# Создать представление общей таблицы, где все таблицы соеденены в одну
create_view_general_table_query = """
    CREATE VIEW general_table AS
        SELECT products_table.id_product, products_table.id_category, brand_name, model_name, total_rating,
        versions_phones_table.id_ver_phone, ram, rom, img_url, 
        shops_phones_table.id_shop_phone, shops_phones_table.id_shop_name, url_product, product_code, color, 
            local_rating, num_local_rating, bonus_rubles,
        id, price, datetime
        FROM products_table
            JOIN versions_phones_table USING (id_product)
            JOIN shops_phones_table USING (id_ver_phone)
            JOIN prices_phones_table USING (id_shop_phone)
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
        id_product = %s       AND 
        (ram = %s or ram = 0) AND
        rom = %s
"""

# Поиск наличия в магазине данной комплектации в таблице shops_phones_table
select_id_shop_phone_query = """
    SELECT id_shop_phone 
    FROM shops_phones_table 
    WHERE 
        id_ver_phone = %s AND 
        id_shop_name = %s AND
        url_product = %s
"""

# Поиск наличия цены у данного магазина данной комплектации в таблице price_phones_table
select_price_in_price_phone_query = """
    SELECT price 
    FROM prices_phones_table 
    WHERE 
        id_shop_phone = %s
"""

select_img_url_query = """
    SELECT img_url 
    FROM general_table
    WHERE 
        id_shop_name=%s AND 
        brand_name=%s   AND 
        model_name=%s   AND 
        ram=%s          AND 
        rom=%s 
    LIMIT 1
"""

# --------------------------- ЗАПИСЬ В БД ----------------------------

# Заполнить таблицу названий магазинов
insert_into_shops_name_table_query = "INSERT INTO shops_name_table (Shop_Name) VALUES %s"

# Заполнить таблицу названий категорий
insert_into_categories_name_table_query = "INSERT INTO categories_name_table (Category_Name) VALUES %s"

# Добавление цены в prices_phone
insert_into_prices_phones_table_query = """
    INSERT INTO prices_phones_table (id_shop_name, id_product, id_shop_phone, price, datetime) 
    VALUES %s
"""

insert_into_shops_phones_table_query = """
    INSERT INTO shops_phones_table (id_shop_name, id_product, id_ver_phone, url_product, product_code, color,
                                   local_rating, num_local_rating, bonus_rubles)
    VALUES %s
    RETURNING id_shop_phone
"""

insert_into_versions_phones_table_query = """
    INSERT INTO versions_phones_table (id_product, ram, rom, img_url)
    VALUES %s
    RETURNING id_ver_phone
"""

insert_into_products_table_query = """
    INSERT INTO products_table (id_category, brand_name, model_name, total_rating)
    VALUES %s
    RETURNING id_product
"""

# --------------------------- ПОИСК ----------------------------

# Поиск всех цен (исторических) по названию бренда, модели, ROM и RAM и сортировка по убыванию
search_all_prices_by_version_query = """
    SELECT price, id_shop_name, datetime
    FROM general_table
    WHERE brand_name = %s       AND 
          model_name = %s       AND 
          (ram = %s or ram = 0) AND 
          rom = %s
    ORDER BY datetime DESC
"""

# Поиск минимальной цены (исторической) по названию бренда, модели, ROM и RAM
search_min_historical_price_by_version_query = """
    SELECT price, id_shop_name, datetime::DATE
    FROM general_table
    WHERE brand_name = %s       AND 
          model_name = %s       AND 
          (ram = %s or ram = 0) AND 
          rom = %s
    ORDER BY price ASC LIMIT 1
"""

# Поиск только актуальных (с самой свежей датой) цен всех магазинов и цветов
# SELECT price, id_shop_name, datetime, color, general_table.url_product
search_actual_prices_by_version_query = """
    SELECT price, id_shop_name, datetime, color, general_table.url_product
    FROM general_table
    JOIN (
        SELECT url_product, MAX(datetime) as MaxDate 
        FROM general_table
        WHERE brand_name = %s       AND 
              model_name = %s       AND 
              (ram = %s OR ram = 0) AND 
              rom = %s
        GROUP BY url_product
    ) AS group_table
    ON general_table.datetime = group_table.MaxDate AND 
       general_table.url_product = group_table.url_product
"""

# Поиск только актуальных (с самой свежей датой) цен всех магазинов и цветов
search_actual_prices_by_version_and_shop_query = """
    SELECT price, id_shop_name, general_table.url_product
    FROM general_table
    JOIN (
        SELECT url_product, MAX(datetime) as MaxDate 
        FROM general_table
        WHERE brand_name = %s       AND 
              model_name = %s       AND 
              (ram = %s OR ram = 0) AND 
              rom = %s              AND
              id_shop_name = %s
        GROUP BY url_product
    ) AS group_table
    ON general_table.datetime = group_table.MaxDate AND 
       general_table.url_product = group_table.url_product
"""

# ----------------------- ОБНОВЛЕНИЕ ДАННЫХ ---------------------------

# Обновление даты у цены
update_datetime_in_price_phone_table_query = """
    UPDATE prices_phones_table 
    SET datetime = now() 
    WHERE id =
        (SELECT id 
        FROM general_table 
        WHERE id_product = %s AND
             id_ver_phone = %s AND
             id_shop_phone = %s AND
             price = %s
        )
"""

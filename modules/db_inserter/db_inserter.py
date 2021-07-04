import configparser

from modules.common.db_wrapper import DataBase
from modules.common import sql_req as sr, helper as h

logger = h.logging.getLogger('AddingToDB')


# Функция, которая вернет true, если хоть у одного поля поврежденные данные
def check_item_on_errors(item):
    if not item.category or \
            not item.shop or \
            not item.brand_name or \
            not item.model_name or \
            not item.color or \
            not item.img_url or \
            not item.product_code or \
            item.rom == 0 or \
            item.price == 0:
        return False
    else:
        return True


class DbInserter:
    """
    Класс, отвечающий за распределение данных с парсеров - добавляет в базу, находит выгодные цены,
    подготавливает список выгодных товаров для отправки в телеграм бот
    """

    def __init__(self, parse_result_list=None):
        self.db = DataBase()
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.best_shop_for_img_url = (self.config.defaults()['best_shops_for_img_url']).lower().split(', ')
        self.pr_parse_result_list = parse_result_list
        # Базовая переменная, в которую необходимо помещать те позиции, которые были добавлены в базу и подходят для
        # следующего этапа - проверки перед публикацией
        self.pr_price_change_list = []

    def __insert_product_in_products_table(self, id_category_name, brand_name, model_name, total_rating):
        """
        Добавление продукта в таблицу products_table
        """
        id_product = self.db.execute_read_query(sr.insert_into_products_table_query,
                                                [(id_category_name, brand_name, model_name, total_rating), ])

        return id_product[0][0] if id_product else None

    def __insert_version_in_versions_phones_table(self, id_product, ram, rom, img_url):
        """
        Добавление комплектации в таблицу versions_phones_table
        """
        id_ver_phone = self.db.execute_read_query(sr.insert_into_versions_phones_table_query,
                                                  [(id_product, ram, rom, img_url), ])

        return id_ver_phone[0][0] if id_ver_phone else None

    def __insert_shop_in_shops_phones_table(self, id_shop_name, id_product, id_ver_phone, url, product_code, var_color,
                                            local_rating, num_local_rating, bonus_rubles=0):
        """
        Добавление магазина, где продается комплектация в таблицу shops_phones_table
        """
        id_shop_phone = self.db.execute_read_query(sr.insert_into_shops_phones_table_query,
                                                   [(id_shop_name, id_product, id_ver_phone, url, product_code,
                                                     var_color,
                                                     local_rating, num_local_rating, bonus_rubles), ])

        return id_shop_phone[0][0] if id_shop_phone else None

    def __insert_price_in_prices_phones_table(self, id_shop_name, id_product, id_shop_phone, price, date_time='now()'):
        """
        Добавление цены в таблицу prices_phones_table
        """
        self.db.execute_query(sr.insert_into_prices_phones_table_query,
                              [(id_shop_name, id_product, id_shop_phone, price, date_time), ])

    def __add_product_to_bd(self, category_name, shop_name, brand_name, model_name, var_rom, var_ram, var_color,
                            img_url, url, product_code, local_rating, num_rating, price, bonus_rubles=0):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Добавление спарсенного товара в БД
        """
        logger.info('-' * 50)
        logger.info(
            "-- {} {} {} {} {} {} {} {}".format(shop_name, brand_name, model_name, var_rom, var_ram, var_color, url,
                                                price))

        if not self.db.connection:
            logger.warning("Can't execute query - no connection")
            return 'error'

        try:
            id_category_name = h.CATEGORIES_NAME_LIST.index((category_name,)) + 1
            id_shop_name = h.SHOPS_NAME_LIST.index((shop_name,)) + 1
        except ValueError as e:
            logger.error("ERROR get category_name or shop_name = {}".format(e))
            return 'error'

        id_product = self.db.execute_read_query(sr.select_id_product_query, (brand_name, model_name))
        # + Продукт присутствует в #products_table
        if id_product:

            logger.info("---id_prod = {}".format(id_product))
            id_product = id_product[0][0]
            id_ver_phone = self.db.execute_read_query(sr.select_id_ver_phone_query,
                                                      (id_product, var_ram, var_rom))
            # ++ Комплектация присутствует в #version_phones_table
            if id_ver_phone:
                logger.info("---id_ver_phone = {}".format(id_ver_phone))
                id_ver_phone = id_ver_phone[0][0]
                id_shop_phone = self.db.execute_read_query(sr.select_id_shop_phone_query,
                                                           (id_ver_phone, id_shop_name, url))

                # +++ Данную комплектацию можно купить в этом магазине в #shop_phones_table
                if id_shop_phone:
                    logger.info("---id_shop_phone = {}".format(id_shop_phone))
                    id_shop_phone = id_shop_phone[0][0]
                    price_phone = self.db.execute_read_query(sr.select_price_in_price_phone_query, (id_shop_phone,))

                    if not price_phone:
                        logger.error("Нет цены, id_prod = {}, "
                                     "id_ver = {}, id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                        return 'error'

                    # ++++ Цена данной комплектации в данном магазине не изменилась - ничего не делаем
                    if price_phone[-1][0] == price:
                        logger.info("---price_phone = {}".format(price_phone))
                        # Если ничего не изменилось - обновить дату у цены
                        logger.info("NO CHANGE, IGNORE; "
                                    "id_prod = {}, id_ver = {}, id_shop = {}, price = {}".format(id_product,
                                                                                                 id_ver_phone,
                                                                                                 id_shop_phone,
                                                                                                 price_phone[-1][0]))

                    # ---- Цена данной комплектации в данном магазине изменилась - добавляем в список цен
                    else:
                        logger.info("Новая цена на эту комплектацию в этом магазине, добавляю цену")
                        self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                        return 'price'

                # --- Данную комплектацию нельзя купить в этом магазине, магазин отсутствует в #shop_phones_table
                else:
                    logger.info("Такой комплектации нет в данном магазине, добавляю магазин и цену")
                    id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                             url, product_code, var_color, local_rating,
                                                                             num_rating, bonus_rubles)
                    self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                    logger.info(
                        "id_prod = {}, id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                    return 'version'

            # -- Комплектация отсутствует в #version_phones_table
            else:
                logger.info(
                    "Данная комплектация отсутствует в списке комплектаций, добавляю комплектацию, магазин, цену")
                id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_ram, var_rom, img_url)
                id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone,
                                                                         url, product_code, var_color, local_rating,
                                                                         num_rating, bonus_rubles)
                self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
                logger.info(
                    "id_prod = {}, new id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
                return 'shop'

        # - Продукт отсутствует в #products_table
        else:
            logger.info("Данный продукт отсутствует в products_table, добавляю продукт, комплектацию, магазин, цену")
            id_product = self.__insert_product_in_products_table(id_category_name, brand_name, model_name, 0)
            id_ver_phone = self.__insert_version_in_versions_phones_table(id_product, var_ram, var_rom, img_url)
            id_shop_phone = self.__insert_shop_in_shops_phones_table(id_shop_name, id_product, id_ver_phone, url,
                                                                     product_code, var_color, local_rating, num_rating,
                                                                     bonus_rubles)
            self.__insert_price_in_prices_phones_table(id_shop_name, id_product, id_shop_phone, price)
            logger.info(
                "new id_prod = {}, new id_ver = {}, new id_shop = {}".format(id_product, id_ver_phone, id_shop_phone))
            return 'product'

        return 'error'

    def __add_input_list_to_db(self, pr_product_list=None):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Добавление всех товаров в базу
        """
        if not pr_product_list or not self.pr_parse_result_list:
            logger.warning('pr_product_list is empty')
            return

        pr_product_list = pr_product_list or self.pr_parse_result_list
        for item in pr_product_list:

            # Проверка элемента на некорректные поля
            if not check_item_on_errors(item):
                logger.warning("Продукт {} {} с артиклом {} в магазине {} содержит 'None', SKIP".format(
                    item.brand_name, item.model_name, item.product_code, item.shop))
                continue

            # Сохранение данных в базу. Если цена изменилась - вернет предыдущую
            resp = self.__add_product_to_bd(
                category_name=item.category,
                shop_name=item.shop,
                brand_name=item.brand_name,
                model_name=item.model_name,
                var_color=item.color,
                var_ram=item.ram,
                var_rom=item.rom,
                price=item.price,
                img_url=item.img_url,
                url=item.url,
                product_code=item.product_code,
                local_rating=item.rating,
                num_rating=item.num_rating)

            # Если при добавлении товара в базу была изменена только цена -
            # добавляем в очередь на проверку выгоды
            if resp == 'price' and not h.find_in_namedtuple_list(self.pr_price_change_list, brand_name=item.brand_name,
                                                                 model_name=item.model_name, ram=item.ram, rom=item.rom,
                                                                 price=item.price, limit_one=True):
                logger.info(item)
                self.pr_price_change_list.append(item)

    def run(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Запуск
        """
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
        self.__add_input_list_to_db()
        self.db.disconnect()
        return self.pr_price_change_list


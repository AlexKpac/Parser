import csv
import datetime
import configparser

import bd
import header as h
import sql_req as sr


logger = h.logging.getLogger('checker')


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
            item.cur_price == 0:
        return False
    else:
        return True


# Проверить все элементы на равенство по заданной позиции
def all_elem_equal_in_tuple_list(elements, indx):
    if not elements or len(elements) == 1:
        return True

    data = elements[0][indx]
    for item in elements:
        if item[indx] != data:
            return False

    return True


# Вернет список с одним или несколькими магазинами и разными цветами, но с самыми низкими ценами
def find_min_price_in_prices_list(price_list):
    pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

    # Если в списке все цены равны (не важно сколько магазинов) или список пуст - возвращаем список без изменений
    if all_elem_equal_in_tuple_list(price_list, pos_price):
        return price_list

    # Если в списке цены разные, но магазин один или несколько - находим самые низкие цены не зависимо от магазина
    result = []
    min_price = min(price_list)[pos_price]
    for item in price_list:
        if item[pos_price] == min_price:
            result.append(item)

    return result


# Класс, отвечающий за распределение данных с парсеров - добавляет в базу, находит выгодные цены, подготавливает список
# выгодных товаров для отправки в телеграм бот
class Checker:

    def __init__(self, parse_result_list):
        self.db = bd.DataBase()
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.min_diff_price_per = float(self.config.defaults()['min_diff_price_per'])
        self.best_shop_for_img_url = (self.config.defaults()['best_shops_for_img_url']).lower().split(', ')
        self.pr_product_list = parse_result_list
        self.pr_price_change_list = []
        self.pc_result_list = []

    # Добавление продукта в таблицу products_table
    def __insert_product_in_products_table(self, id_category_name, brand_name, model_name, total_rating):
        id_product = self.db.execute_read_query(sr.insert_into_products_table_query,
                                                [(id_category_name, brand_name, model_name, total_rating), ])

        return id_product[0][0] if id_product else None

        # Добавление комплектации в таблицу versions_phones_table

    # Добавление комплектации в таблицу versions_phones_table
    def __insert_version_in_versions_phones_table(self, id_product, ram, rom, img_url):
        id_ver_phone = self.db.execute_read_query(sr.insert_into_versions_phones_table_query,
                                                  [(id_product, ram, rom, img_url), ])

        return id_ver_phone[0][0] if id_ver_phone else None

        # Добавление магазина для покупки комплектации в shops_phones_table

    # Добавление магазина, где продается комплектация в таблицу shops_phones_table
    def __insert_shop_in_shops_phones_table(self, id_shop_name, id_product, id_ver_phone, url, product_code, var_color,
                                            local_rating, num_local_rating, bonus_rubles=0):
        id_shop_phone = self.db.execute_read_query(sr.insert_into_shops_phones_table_query,
                                                   [(id_shop_name, id_product, id_ver_phone, url, product_code,
                                                     var_color,
                                                     local_rating, num_local_rating, bonus_rubles), ])

        return id_shop_phone[0][0] if id_shop_phone else None

        # Добавление цены определенного магазина определенной комплектации в prices_phones_table

    # Добавление цены в таблицу prices_phones_table
    def __insert_price_in_prices_phones_table(self, id_shop_name, id_product, id_shop_phone, price, date_time='now()'):
        self.db.execute_query(sr.insert_into_prices_phones_table_query,
                              [(id_shop_name, id_product, id_shop_phone, price, date_time), ])

    # Проверка списка товаров с измененной ценой на выгодное предложение
    def __check_price_for_benefit(self, cur_price, brand_name, model_name, ram, rom):
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4
        null_result = (None, None, None)

        # Получить список всех актуальных цен на данную комплектацию: price, id_shop_name, datetime, color, url_product
        act_price_data_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                         (brand_name, model_name, ram, rom))
        if not act_price_data_list:
            return null_result

        # Определить, данный товар продается только в одном магазине или нет
        is_one_shop = all_elem_equal_in_tuple_list(act_price_data_list, pos_shop)
        # Поиск исторического минимума цены
        all_price_data_list = self.db.execute_read_query(sr.search_all_prices_by_version_query,
                                                         (brand_name, model_name, ram, rom))
        if not all_price_data_list:
            return null_result

        logger.info(("-" * 50) + "\n" + "hist origin: {}".format(all_price_data_list))

        # Если магазин один, то удалить последние добавленные актуальные цены для нормального расчета средней цены
        indx = 0
        if is_one_shop:
            last_datetime = all_price_data_list[0][pos_datetime]
            for item in all_price_data_list:
                if (last_datetime - item[pos_datetime]).total_seconds() < 1:
                    indx += 1
                else:
                    break
            logger.info('One shop: indx = {}, new hist: {}'.format(indx, all_price_data_list[indx:]))
            hist_min_price = min(all_price_data_list[indx:])
        else:
            hist_min_price = min(all_price_data_list)

        # Поиск средней цены для одного магазина или нескольких
        avg_price = ((cur_price + hist_min_price[pos_price]) / 2) if is_one_shop \
            else sum(item[pos_price] for item in act_price_data_list) / len(act_price_data_list)

        logger.info('cur_price = {}, hist_min_price = {}'.format(cur_price, hist_min_price[pos_price]))
        logger.info('is_one_shop: {}'.format(is_one_shop))
        logger.info("check_price: len = {}, prices_list = {}".format(len(act_price_data_list), act_price_data_list))
        logger.info("avg_price = {}".format(avg_price))
        logger.info("hist_min_price res = {}".format(hist_min_price))

        # Оставить в списке только товары в наличии (которые есть в списке с результатами всех парсеров)
        act_price_in_stock_data_list = []
        for item in act_price_data_list:
            if h.find_in_namedtuple_list(self.pr_product_list, url=item[pos_url], limit_one=True):
                act_price_in_stock_data_list.append(item)

        # Оставить только самые минимальные цены из товаров в наличии
        min_act_price_in_stock_data_list = find_min_price_in_prices_list(act_price_in_stock_data_list)

        # Сравнение минимальной цены (любой, они равны) со средней. Если цена не выгодная - очистить список
        if h.per_num_of_num(min_act_price_in_stock_data_list[0][pos_price], avg_price) < self.min_diff_price_per:
            min_act_price_in_stock_data_list.clear()

        logger.info('YES' if min_act_price_in_stock_data_list else 'NO')
        return min_act_price_in_stock_data_list, avg_price, hist_min_price

    # Сохранение результата
    def __save_result(self):
        if not self.pc_result_list:
            return

        with open(h.PRICE_CHANGES_PATH, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_PRICE_CHANGES)
            for item in self.pc_result_list:
                writer.writerow(item)

    # Добавление спарсенного товара в БД
    def add_product_to_bd(self, category_name, shop_name, brand_name, model_name, var_rom, var_ram, var_color,
                          img_url, url, product_code, local_rating, num_rating, price, bonus_rubles=0):

        logger.info('-' * 50)
        logger.info("-- {} {} {} {} {} {} {} {}".format(shop_name, brand_name, model_name, var_rom, var_ram, var_color, url, price))

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
                                    "id_prod = {}, id_ver = {}, id_shop = {}, price = {}".format(id_product, id_ver_phone,
                                                                                     id_shop_phone, price_phone[-1][0]))

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

    # Запуск проверки товаров с измененной ценой на поиск выгоды
    def check_prices(self, pr_price_change_list=None):
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

        if not pr_price_change_list:
            pr_price_change_list = self.pr_price_change_list

        for item in pr_price_change_list:
            result_list, avg_price, hist_min_price = self.__check_price_for_benefit(item.cur_price,
                                                                                    item.brand_name,
                                                                                    item.model_name,
                                                                                    item.ram, item.rom)
            for item11 in result_list:
                logger.info('==item11={}'.format(item11))

            # Если выявлено изменение цены - записать в список
            if result_list and avg_price and hist_min_price:
                for item_result in result_list:
                    # Для исключительных ситуаций: проверка, что такого элемента с такой ценой и цветом еще нет в списке
                    if not h.find_in_namedtuple_list(self.pc_result_list, url=item_result[pos_url], limit_one=True):

                        # Ссылу на изображение необходимо вытянуть из предпочтительных магазинов
                        img_url = None
                        for best_shop_item in self.best_shop_for_img_url:
                            img_url = h.find_in_namedtuple_list(self.pr_product_list, brand_name=item.brand_name,
                                                                model_name=item.model_name, shop=best_shop_item,
                                                                limit_one=True)
                            if img_url and ("http" in img_url[0].img_url):
                                img_url = img_url[0].img_url
                                break
                            else:
                                img_url = None

                        self.pc_result_list.append(h.PriceChanges(
                            shop=item_result[pos_shop],
                            category=item.category,
                            brand_name=item.brand_name,
                            model_name=item.model_name,
                            color=item_result[pos_color],
                            ram=item.ram,
                            rom=item.rom,
                            img_url=img_url if img_url else item.img_url,
                            url=item_result[pos_url],
                            date_time=datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                            cur_price=item_result[pos_price],
                            avg_actual_price=int(avg_price),
                            hist_min_price=hist_min_price[pos_price],
                            hist_min_shop=hist_min_price[pos_shop],
                            hist_min_date=hist_min_price[pos_datetime],
                            diff_cur_avg=int(avg_price - item_result[pos_price]),
                        ))

    # Добавление всех товаров в базу
    def adding_all_products_to_db(self, pr_product_list=None):

        if not pr_product_list:
            pr_product_list = self.pr_product_list

        if not pr_product_list:
            logger.warning('pr_product_list is empty')
            return

        for item in pr_product_list:
            # Проверка элемента на некорректные поля
            if not check_item_on_errors(item):
                logger.warning("Продукт {} {} с артиклом {} в магазине {} содержит 'None', SKIP".format(
                    item.brand_name, item.model_name, item.product_code, item.shop))
                continue

            # Сохранение данных в базу. Если цена изменилась - вернет предыдущую
            resp = self.add_product_to_bd(
                category_name=item.category,
                shop_name=item.shop,
                brand_name=item.brand_name,
                model_name=item.model_name,
                var_color=item.color,
                var_ram=item.ram,
                var_rom=item.rom,
                price=item.cur_price,
                img_url=item.img_url,
                url=item.url,
                product_code=item.product_code,
                local_rating=item.rating,
                num_rating=item.num_rating)

            # Если при добавлении товара в базу была изменена только цена -
            # добавляем в очередь на проверку выгоды
            if resp == 'price' and not h.find_in_namedtuple_list(self.pr_price_change_list, brand_name=item.brand_name,
                                                                 model_name=item.model_name, ram=item.ram, rom=item.rom,
                                                                 cur_price=item.cur_price, limit_one=True):
                logger.info(item)
                self.pr_price_change_list.append(item)

    # Запуск
    def run(self):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
        self.adding_all_products_to_db()
        if not len(self.pr_price_change_list):
            logger.info('СПИСОК ПРОДУКТОВ НА ПРОВЕРКУ ВЫГОДЫ ПУСТ')
        self.check_prices()
        self.db.disconnect()
        self.__save_result()
        return self.pc_result_list


# Загрузить данные с csv, чтобы не парсить сайт
def load_result_from_csv(name):
    pr_result_list = []
    with open(h.CSV_PATH_RAW + name, 'r', encoding='UTF-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_result_list.append(h.ParseResult(
                shop=row['Магазин'],
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                cur_price=int(row['Цена']),
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                rating=float(row['Рейтинг']),
                num_rating=int(row['Кол-во отзывов']),
                product_code=row['Код продукта'],
            ))

    return pr_result_list


def get_data():
    pc_product_list = []
    with open(h.PRICE_CHANGES_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pc_product_list.append(h.PriceChanges(
                shop=int(row['Магазин']),
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                date_time=row['Дата и время'],
                cur_price=int(row['Текущая цена']),
                avg_actual_price=float(row['Средняя цена']),
                hist_min_price=int(row['Историческая мин. цена']),
                hist_min_shop=int(row['Исторический мин. магазин']),
                hist_min_date=row['Исторический мин. дата'],
                diff_cur_avg=int(row['Разница цены от средней']),
            ))

    return pc_product_list

# ch = Checker([])
# res = get_data()  # load_result_from_csv("dif_price.csv")
# res12 = h.find_in_namedtuple_list(res, brand_name='honor', model_name='', date_time='', hist_min_price=13519,
#                                 cur_price=13519, color='белый')
# for item1 in res12:
#     print(item1)
import datetime
import configparser

from modules.common.db_wrapper import DataBase
from modules.common.file_worker import FileWorker
import modules.common.sql_req as sr
import modules.common.helper as h

logger = h.logging.getLogger('DataChecker')


class DataChecker:
    """
    Класс, реализующий проверку данных, которую отфильтровал предыдущий модуль добавления в БД @AddingToDB. Из
    этих данных этот класс оставляет только те данные, которые необходимо отправить дальше, на вывод.
    """

    def __init__(self, pr_data_after_bd_list, pr_parse_result_list):
        """
        :param pr_data_after_bd_list: список данных, которые отфильтровал DBInserter в процессе добавления данных в БД
        :param pr_parse_result_list: список данных, которые пришли после DataValidator (до БД)
        """
        self.pc_self_result_list = []
        self.pr_price_change_list = pr_data_after_bd_list
        self.pr_parse_result_list = pr_parse_result_list

        self.db = DataBase()
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.min_diff_price_per = float(self.config.defaults()['min_diff_price_per'])
        self.best_shop_for_img_url = (self.config.defaults()['best_shops_for_img_url']).lower().split(', ')

    def __check_price_for_benefit(self, price, brand_name, model_name, ram, rom):
        """
        Проверка списка товаров с измененной ценой на выгодное предложение
        """
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4
        null_result = (None, None, None)

        # Получить список всех актуальных цен на данную комплектацию: price, id_shop_name, datetime, color, url_product
        act_price_data_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                         (brand_name, model_name, ram, rom))
        if not act_price_data_list:
            return null_result

        # Определить, данный товар продается только в одном магазине или нет
        is_one_shop = h.is_all_elem_equal_in_tuple_list(act_price_data_list, pos_shop)
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
        avg_price = ((price + hist_min_price[pos_price]) / 2) if is_one_shop \
            else sum(item[pos_price] for item in act_price_data_list) / len(act_price_data_list)

        logger.info('price = {}, hist_min_price = {}'.format(price, hist_min_price[pos_price]))
        logger.info('is_one_shop: {}'.format(is_one_shop))
        logger.info("check_price: len = {}, prices_list = {}".format(len(act_price_data_list), act_price_data_list))
        logger.info("avg_price = {}".format(avg_price))
        logger.info("hist_min_price res = {}".format(hist_min_price))

        # Оставить в списке только товары в наличии (которые есть в списке с результатами всех парсеров)
        act_price_in_stock_data_list = []
        for item in act_price_data_list:
            if h.find_in_namedtuple_list(self.pr_parse_result_list, url=item[pos_url], limit_one=True):
                act_price_in_stock_data_list.append(item)

        # Оставить только самые минимальные цены из товаров в наличии
        min_act_price_in_stock_data_list = h.find_min_price_in_prices_list(act_price_in_stock_data_list)

        # Сравнение минимальной цены (любой, они равны) со средней. Если цена не выгодная - очистить список
        if h.per_num_of_num(min_act_price_in_stock_data_list[0][pos_price], avg_price) < self.min_diff_price_per or \
                avg_price - min_act_price_in_stock_data_list[0][pos_price] < 1500:
            min_act_price_in_stock_data_list.clear()

        logger.info('YES' if min_act_price_in_stock_data_list else 'NO')
        return min_act_price_in_stock_data_list, avg_price, hist_min_price

    def __check_prices(self, pr_price_change_list=None):
        """
        Запуск проверки товаров с измененной ценой на поиск выгоды
        """
        pos_price, pos_shop, pos_datetime, pos_color, pos_url = 0, 1, 2, 3, 4

        if not pr_price_change_list:
            pr_price_change_list = self.pr_price_change_list

        for item in pr_price_change_list:
            result_list, avg_price, hist_min_price = \
                self.__check_price_for_benefit(item.price, item.brand_name, item.model_name, item.ram, item.rom)

            if not result_list or not avg_price or not hist_min_price:
                continue

            for item_result in result_list:
                # Для исключительных ситуаций: проверка, что такого элемента с такой ценой и цветом еще нет в списке
                if h.find_in_namedtuple_list(self.pc_self_result_list, url=item_result[pos_url], limit_one=True):
                    continue

                # Ссылу на изображение необходимо вытянуть из предпочтительных магазинов
                img_url = None
                for best_shop_item in self.best_shop_for_img_url:
                    img_url = h.find_in_namedtuple_list(
                        self.pr_parse_result_list,
                        brand_name=item.brand_name, model_name=item.model_name, shop=best_shop_item, limit_one=True)
                    if img_url and ("http" in img_url[0].img_url):
                        img_url = img_url[0].img_url
                        break
                    else:
                        img_url = None

                self.pc_self_result_list.append(h.PriceChanges(
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
                    price=item_result[pos_price],
                    avg_actual_price=int(avg_price),
                    hist_min_price=hist_min_price[pos_price],
                    hist_min_shop=hist_min_price[pos_shop],
                    hist_min_date=hist_min_price[pos_datetime],
                    diff_cur_avg=int(avg_price - item_result[pos_price]),
                ))

    def run(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Запуск проверки данных
        """
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")
        self.__check_prices()
        self.db.disconnect()

        # Сохранение результата
        FileWorker.csv_data.save(h.PRICE_CHANGES_PATH, data=self.pc_self_result_list,
                                 namedtuple_type=h.PriceChanges)

        return self.pc_self_result_list

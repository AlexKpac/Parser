import time
import hashlib
from datetime import datetime

import modules.common.helper as h
import modules.data_sender.telegram.bot_helper as bh
from modules.common import sql_req as sr
from modules.common.db_wrapper import DataBase
from modules.common.file_worker import FileWorker
from modules.data_sender.telegram.telegram_sender import TelegramSender

logger = h.logging.getLogger('Bot')


class Bot(TelegramSender):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataSender
    Класс, реализующий юзербота в телеграме, который выполняет сразу несколько функций:
        - Делает новые посты в канал (с генерацией текста и картинки)
        - Перепроверяет старые посты на актуальность и, в случае неактуальности обновляет
            данные или ставит штамп
    """

    def __init__(self):
        super().__init__()
        self.ignore_brands = self.config['bot-ignore']['brands'].lower().split('\n')
        self.one_star_per = float(self.config['bot-stars']['one_star_per'])
        self.two_star_per = float(self.config['bot-stars']['two_star_per'])
        self.three_star_per = float(self.config['bot-stars']['three_star_per'])
        self.four_star_per = float(self.config['bot-stars']['four_star_per'])
        self.five_star_per = float(self.config['bot-stars']['five_star_per'])
        self.irrelevant_url_text = self.config['bot']['irrelevant_url_text']
        self.hash_tag_actual = '#' + self.config['bot']['hash_tag_actual']
        self.max_num_act_post_telegram = int(self.config['bot']['max_num_act_post_telegram'])

        self.pc_product_list = []
        self.posts_in_telegram_list = []
        self.db = DataBase()

        # Загрузка словарей
        self.except_model_names_telegram_dict = FileWorker.dict_data.load(h.EXCEPT_MODEL_NAMES_TELEGRAM_PATH)
        self.stats_prods_dict = FileWorker.dict_data_str_int.load(h.STATS_PRODS_DICTIONARY_PATH)
        self.stats_shops_dict = FileWorker.dict_data_str_int.load(h.STATS_SHOPS_DICTIONARY_PATH)

        self.posts_in_telegram_list = bh.load_msg_in_telegram_list()
        self.num_all_post, self.num_actual_post = bh.load_num_posts()

    def __generate_caption(self, category, brand_name, model_name, ram, rom, price, avg_actual_price, hist_min_price,
                           hist_min_date, hist_min_shop, versions_list, is_actual):
        """
        Генерация текста для поста (описания для изображения)
         - versions_list: список кортежей вида [(shop, url, color), (...), ...]
        """

        if not versions_list:
            logger.error("Неизвестная ошибка с пустым versions_list, пропуск")
            return None

        # НАЗВАНИЕ МОДЕЛИ с учетом словаря с исключениями названий
        caption = h.replace_value_from_dictionary(self.except_model_names_telegram_dict, '<b>{} {} {}</b>\n'.format(
            category[0:-1].title(), brand_name.title(), model_name.title()))

        # КОМПЛЕКТАЦИЯ
        caption += '<b>{}/{} GB</b>\n\n'.format(ram, rom) \
            if (ram and brand_name != 'apple') \
            else '<b>{} GB</b>\n\n'.format(rom)

        # ОГОНЬКИ
        star = 0
        per = h.per_num_of_num(price, avg_actual_price)

        if self.one_star_per <= per < self.two_star_per:
            star = 1
        if self.two_star_per <= per < self.three_star_per:
            star = 2
        if self.three_star_per <= per < self.four_star_per:
            star = 3
        if self.four_star_per <= per < self.five_star_per:
            star = 4
        if self.five_star_per < per:
            star = 5

        caption += '🔥' * star + '\n'

        # ЦЕНА
        caption += 'Выгодная цена: <b><i>{}</i></b> ₽\n'.format(
            '{0:,}'.format(price).replace(',', ' ')
        )
        caption += '<i>(Дешевле на {}</i> ₽<i> от средней)</i>\n\n'.format(
            '{0:,}'.format(int(avg_actual_price - price)).replace(',', ' ')
        )

        # ИСТОРИЧЕСКИЙ МИНИМУМ
        if price <= hist_min_price:
            caption += '<i>Данная цена является самой низкой за всё время</i>\n'
        else:
            date_time = datetime.strptime(str(hist_min_date), '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y')
            caption += '<i>Минимальная цена {}</i> ₽ <i>была в {} {}</i>\n'.format(
                '{0:,}'.format(hist_min_price).replace(',', ' '),
                h.TRUE_SHOP_NAMES[hist_min_shop - 1], date_time
            )

        # СПИСОК ССЫЛОК ДЛЯ ПОКУПКИ
        pos_shop, pos_url, pos_color = 0, 1, 2
        shops_set = list(set(item[pos_shop] for item in versions_list))

        # Группировка позиций по магазину и создание списка ссылок на разные магазины с разными цветами
        hashtag_shops = ''
        links_shop_list = []
        for shop in shops_set:
            # Генерация тегов магазинов
            hashtag_shops += '#' + h.SHOPS_NAME_LIST[shop - 1][0] + ' '
            # Генерация ссылок
            urls = ''
            for product in versions_list:
                if product[pos_shop] == shop:
                    urls += '<a href="{}">► {}</a>\n'.format(bh.get_ref_link(product[pos_url]),
                                                             product[pos_color].title())
            links_shop_list.append(urls)

        # Генерация ссылок
        indx = 0
        for link_set in links_shop_list:
            caption += '\nКупить в <b><u>{}</u></b>:\n{}'.format(h.TRUE_SHOP_NAMES[shops_set[indx] - 1], link_set)
            indx += 1

        # ХЭШТЕГИ
        caption += '\n#{} {}'.format(brand_name, hashtag_shops)
        if is_actual:
            caption += self.hash_tag_actual

        return caption

    def __filtering_data(self):
        """
        Фильтрация входных данных - удаление дубликатов и применение игнор-листа
        """
        # Удалить дубликаты, если имеются
        result = []
        for item in self.pc_product_list:
            if not result.count(item):
                result.append(item)
        self.pc_product_list = result

        # Удалить товары, если его бренд имеется в игнор-листе
        result = []
        for item in self.pc_product_list:
            if not self.ignore_brands.count(item.brand_name):
                result.append(item)
        self.pc_product_list = result

    def __prepare_and_send_all_posts(self):
        """
        Разбор списка продуктов, группировка по цветам, отправка в телеграм
        """
        versions_list = []
        # Проход по всему списку, группировка элементов по версии и цвету, пост группы
        while self.pc_product_list:
            # Взятие группы комплектации с разными цветами
            item = self.pc_product_list[0]
            one_version_list = h.find_in_namedtuple_list(self.pc_product_list,
                                                         brand_name=item.brand_name, model_name=item.model_name,
                                                         ram=item.ram, rom=item.rom, price=item.price)
            # Составление списка комплектаций
            versions_list.append(one_version_list)
            # Удаление из основного списка взятой группы one_version_list
            for item in one_version_list:
                self.pc_product_list.remove(item)

        # Отправка постов в телеграм. Звук только у последних 2-ух
        for i in range(len(versions_list)):
            self.app.loop.run_until_complete(
                self.__send_one_post(versions_list[i], dis_notify=bool(i < (len(versions_list) - 2)))
            )

    async def __send_one_post(self, version_list, dis_notify):
        """
        Отправка поста в телеграм
        """
        item = version_list[0]

        # Проверка на наличие такого же поста в списке актуальных сообщений
        if h.find_in_namedtuple_list(self.posts_in_telegram_list,
                                     brand_name=item.brand_name, model_name=item.model_name, price=item.price,
                                     ram=item.ram, rom=item.rom, limit_one=True):
            logger.info("Duplicate post, SKIP")
            logger.info(item)
            return

        # Обновление счетчика постов
        self.num_all_post += 1
        self.num_actual_post += 1

        # Обновление словаря статистики товаров и магазинов
        bh.inc_stats_products(self.stats_prods_dict, item.brand_name, item.model_name)
        bh.inc_stats_shops(self.stats_shops_dict, list(set(item.shop for item in version_list)))

        # Генерация поста
        versions_list = [(item.shop, item.url, item.color) for item in version_list]
        text = self.__generate_caption(
            category=item.category, brand_name=item.brand_name, model_name=item.model_name, ram=item.ram,
            rom=item.rom, price=item.price, avg_actual_price=item.avg_actual_price,
            hist_min_price=item.hist_min_price, hist_min_date=item.hist_min_date, hist_min_shop=item.hist_min_shop,
            versions_list=versions_list, is_actual=True
        )

        img_path = bh.create_and_save_img_for_edit_post(img_url=item.img_url, is_actual=True)
        if not img_path:
            return

        for i in range(3):
            msg_id = self.send_photo_message(img_path=img_path, caption=text, dis_notify=dis_notify)

            if msg_id:
                self.posts_in_telegram_list.append(h.MessagesInTelegram(
                    message_id=msg_id,
                    category=item.category,
                    brand_name=item.brand_name,
                    model_name=item.model_name,
                    ram=item.ram,
                    rom=item.rom,
                    price=item.price,
                    avg_actual_price=item.avg_actual_price,
                    img_url=item.img_url,
                    where_buy_list=[(item.shop, item.color, item.url) for item in version_list],
                    post_datetime=datetime.now(),
                    hist_min_price=item.hist_min_price,
                    hist_min_shop=item.hist_min_shop,
                    hist_min_date=item.hist_min_date,
                    text_hash=hashlib.sha256(text.encode()).hexdigest(),
                    is_actual=True,
                ))
                break

    async def __edit_post_as_irrelevant(self, post, text, current_actual):
        """
        Отредактировать пост как частично или полностью неактуальный
        """
        # Если пост был неактуальный и до сих пор неактуальный - выходим, менять нечего
        if not post.is_actual and not current_actual:
            logger.info("Пост был и остается неактуальным, не меняем")
            return True

        # Если есть изменения состояния, то обновляем пост вместе с картинкой, иначе только описание
        if post.is_actual != current_actual:
            logger.info("Изменение актуальности {} -> {}".format(post.is_actual, current_actual))

            # Генерация новой картинки и сохранение на диск
            img_path = bh.create_and_save_img_for_edit_post(img_url=post.img_url, is_actual=current_actual)

            # 3 попытки изменить пост (из-за бага телеграм)
            for i in range(3):
                if self.edit_photo_message(msg_id=post.message_id, img_path=img_path, caption=text):
                    logger.info("Успешное выполнение edit_message_media!")
                    self.num_actual_post += 1 if current_actual else (-1)
                    time.sleep(1)
                    return True

            logger.error("Не удалось отредактировать пост после 3 попыток")
            return False

        # Если пост не менял актуальность (true=true) и хэш сообщения изменился - обновляем описание поста
        if hashlib.sha256(text.encode()).hexdigest() != post.text_hash:
            if not self.edit_photo_message_caption(msg_id=post.message_id, caption=text):
                return False

        logger.info("В посте ничего не изменилось")
        return True

    def __checking_irrelevant_posts(self, pr_product_in_stock_list):
        """
        Проверка неактуальных постов
        """
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        # Проход по всем актуальным постам, их проверка на полную, частичную актуальность и неактуальность
        new_posts_in_telegram_list = []
        for item in self.posts_in_telegram_list:

            # Получить список всех актуальных цен и данных на данную комплектацию:
            act_price_data_list = self.db.execute_read_query(sr.search_actual_prices_by_version_query,
                                                             (item.brand_name, item.model_name, item.ram, item.rom))
            # Фильтрация списка актуальных цен с учетом наличия в магазинах
            act_price_data_in_stock_list = bh.irr_post_search_data_in_stock(act_price_data_list,
                                                                            pr_product_in_stock_list)
            # Список данных с минимальными актуальными ценами в наличии
            min_act_price_data_in_stock_list = h.find_min_price_in_prices_list(act_price_data_in_stock_list)

            logger.info(("-" * 50) + "item: {}".format(item))
            logger.info("item actual: {}".format(item.is_actual))
            logger.info("act_price_data_list: {}".format(act_price_data_list))
            logger.info("act_price_data_in_stock_list: {}".format(act_price_data_in_stock_list))
            logger.info("min_act_price_data_in_stock_list: {}".format(min_act_price_data_in_stock_list))

            # Если минимальная цена отличается от цены в посте - ПОСТ ПОЛНОСТЬЮ НЕАКТУАЛЬНЫЙ
            is_actual = True
            if (min_act_price_data_in_stock_list and min_act_price_data_in_stock_list[0][0] != item.price) or \
                    not min_act_price_data_in_stock_list:
                logger.info("Пост полностью неактуальный - есть более выгодное(ые) предложение(ия) или акция прошла")
                is_actual = False

            # Генерация списка всех товаров для одного поста и генерация текста
            if is_actual:
                versions_list = [(it[1], it[4], it[3]) for it in min_act_price_data_in_stock_list]
            else:
                versions_list = [(it[0], it[2], it[1]) for it in item.where_buy_list]

            new_text = self.__generate_caption(
                category=item.category, brand_name=item.brand_name, model_name=item.model_name,
                ram=item.ram, rom=item.rom, price=item.price, avg_actual_price=item.avg_actual_price,
                hist_min_price=item.hist_min_price, hist_min_date=item.hist_min_date, hist_min_shop=item.hist_min_shop,
                versions_list=versions_list, is_actual=is_actual
            )

            if not self.app.loop.run_until_complete(
                    self.__edit_post_as_irrelevant(item, new_text, is_actual)
            ):
                logger.error("Не удалось отредактировать пост!")
                is_actual = True

            # Сохраняем пост в список постов
            bh.irr_post_add_item_in_msg_in_telegram_list(new_posts_in_telegram_list,
                                                         self.max_num_act_post_telegram, item,
                                                         hashlib.sha256(new_text.encode()).hexdigest(), is_actual)

        self.posts_in_telegram_list = new_posts_in_telegram_list
        self.db.disconnect()

    def send_posts(self, pc_product_list):
        """
        Запуск отправки новых постов
        """
        # pc_product_list = get_data()
        if not pc_product_list:
            logger.info("НЕТ ДАННЫХ ДЛЯ TELEGRAM")
            return

        self.pc_product_list = pc_product_list
        self.__filtering_data()
        self.__prepare_and_send_all_posts()

        # Сохранение словарей
        FileWorker.dict_data.save(h.STATS_PRODS_DICTIONARY_PATH, data=self.stats_prods_dict)
        FileWorker.dict_data.save(h.STATS_SHOPS_DICTIONARY_PATH, data=self.stats_shops_dict)
        FileWorker.list_data.save(h.NUM_POSTS_IN_TELEGRAM_PATH, data=[self.num_all_post, self.num_actual_post])
        FileWorker.csv_data.save(
            h.MESSAGES_IN_TELEGRAM_LIST_PATH, data=self.posts_in_telegram_list, namedtuple_type=h.MessagesInTelegram)

    def checking_irrelevant_posts(self, pr_product_in_stock_list):
        """
        Запуск проверки на неактуальность постов
        """
        if not pr_product_in_stock_list:
            logger.error("НЕТ ДАННЫХ ДЛЯ НЕАКТУАЛЬНЫХ ПОСТОВ")
            return

        self.__checking_irrelevant_posts(pr_product_in_stock_list)

        # Сохранение словарей
        FileWorker.list_data.save(h.NUM_POSTS_IN_TELEGRAM_PATH, data=[self.num_all_post, self.num_actual_post])
        FileWorker.csv_data.save(
            h.MESSAGES_IN_TELEGRAM_LIST_PATH, data=self.posts_in_telegram_list, namedtuple_type=h.MessagesInTelegram)

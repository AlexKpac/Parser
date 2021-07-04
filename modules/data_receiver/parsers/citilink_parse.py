import time
import re

from selenium.webdriver.common.by import By
from modules.data_receiver.parsers.parse_base import ParseBase

import modules.common.helper as h
from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('citilinkparse')
CITILINK_REBUILT_IPHONE = '"как новый"'


def citilink_parse_model_name(name):
    """
    Парсинг названия модели (получить название модели, цвет и ROM)
    """
    # Защита от неправильных названий
    if len(name.split()) < 3 or not name.count(','):
        return None, None, None
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Понижение регистра
    name = name.lower()
    name = name.replace('dual sim', '').replace('dual cam', '').replace(' lte ', ' ').replace(' nfc ', ' '). \
        replace(' 5g ', ' ').replace(' 4g ', ' ').replace(' 3g ', ' ').replace('«', '').replace('»', '')
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (CITILINK_REBUILT_IPHONE in name) else ''
    name = name.replace(CITILINK_REBUILT_IPHONE, '')
    # Цвет
    color = name[name.rfind(','):].replace(',', '').replace('(product)', '').strip()
    # Исключение для перечисленных брендов
    model_code = ''
    if 'bq' in name or 'blackview' in name or 'alcatel' in name:
        model_code = ' ' + name[name.find(',') + 1:name.rfind(',')].strip()
    # Удаление кода моделей
    name = name[:name.find(',')]
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Получить размер RAM и ROM, если есть
    ram_rom = re.findall(r'\d*/*\d+ *(?:gb|tb)', name)
    ram_rom = ram_rom[0] if ram_rom else ''
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Удалить лишние слова в названии модели
    name = name.replace('смартфон', '').replace(ram_rom, '').replace(color, ''). \
        replace(year, '').replace('  ', ' ').strip()
    name += model_code + rebuilt

    # Проверка названия в словаре исключений названий моделей
    name = h.replace_value_from_dictionary(h.EXCEPT_MODEL_NAMES_DICT, name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        FileWorker.list_data.save(h.UNDEFINED_MODEL_NAME_LIST_PATH, data=name, overwrite=False)
        return None, None, None

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color


class CitilinkParse(ParseBase):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Реализация базового класса ParseBase
    Парсит данные с магазина Ситилинк
    """
    def __init__(self):
        super().__init__(domain="https://www.citilink.ru", shop="citilink", logger=logger, is_proxy=True,
                         category="смартфоны")

        self.is_grid = True
        self.container_css_selector = 'div.product_data__gtm-js.product_data__pageevents-js.' \
                                      'ProductCardHorizontal.js--ProductCardInListing.js--ProductCardInWishlist'

    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций на странице каталога
        """
        city = self._wd_find_elem_with_timeout(By.CLASS_NAME, "MainHeader__city")
        if not city:
            self.logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if self.current_city.lower() not in city.text.lower():
            self.logger.info("Неверный город")

            # Клик по городу
            if not self._wd_ac_click_elem(city):
                self.logger.error("Не могу нажать на кнопку выбора города")
                return False

            self.logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self._wd_find_all_elems_with_timeout(By.CLASS_NAME, "CitiesSearch__main-cities-list-item")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self._wd_ac_click_elem(item)

            self.logger.info("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self._wd_find_elem_with_timeout(By.XPATH, "//input[@type='search']")
            if not input_city:
                self.logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            if not self._wd_ac_click_elem(input_city):
                self.logger.error("Не могу кликнуть на форму для ввода текста")
                return False

            # Ввод названия города по буквам
            for char in self.current_city:
                self._wd_ac_send_keys(input_city, char)
                time.sleep(0.2)

            time.sleep(2)

            # Выбор города из сгенерированного списка городов
            input_city_item = self._wd_find_elem_with_timeout(By.XPATH,
                                                              "//a[@databases-search='{}']".format(
                                                                  self.current_city.lower()))
            if not input_city_item:
                self.logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self._wd_ac_click_elem(input_city_item):
                self.logger.error("Не могу нажать на выбранный город")
                return False

        return True

    def _wd_city_selection_product(self):
        """
        Алгоритм выбора города для всех возмодных ситуаций на странице продукта
        """
        pass

    def _wd_check_load_page_catalog(self):
        """
        Проверка по ключевым div-ам что страница каталога прогружена полностью
        """
        # Ожидание прогрузки цен
        if not self._wd_find_elem_with_timeout(By.CLASS_NAME,
                                               "ProductCardVerticalPrice__price-current_current-price" if self.is_grid
                                               else "ProductCardHorizontal__price_current-price"):
            return False

        self.logger.info("Page loaded")
        return True

    def _wd_check_load_page_product(self):
        """
        Проверка по ключевым div-ам что страница продукта прогружена полностью
        """
        pass

    def _wd_select_list_view(self):
        """
        Переключение каталога в вид списка
        """
        # Если есть этот тег в html коде, значит сейчас стоит табличный вид, переключаем на список
        if self._wd_find_elem(By.XPATH,
                              "//label[@class='ProductCardCategoryList__icon ProductCardCategoryList__icon_grid "
                              "ProductCardCategoryList__icon-active']"):

            # Переключение с табличного вида на список
            listing_views = self._wd_find_elem_with_timeout(By.XPATH,
                                                            "//span[@class='gray-icon IconFont IconFont_size_m "
                                                            "IconFont_list']")
            if not listing_views:
                self.logger.error("Не могу найти listing views")
                return False

            # Клик
            if not self._wd_ac_click_elem(listing_views):
                self.logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

            self.is_grid = False

        return True

    def _wd_open_browser_catalog(self, url):
        """
        Запуск браузера, загрузка начальной страницы каталога, выбор города
        """
        if not super()._wd_open_browser_catalog(url=url):
            return False

        # Переключение на отображение товаров в виде списка
        if not self._wd_select_list_view():
            self.logger.error("Не смог переключить отображение товара в виде списока")
            return False

        # Ждем, пока не прогрузится страница
        if not self._wd_check_load_page_catalog():
            self.logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        return True

    def _wd_open_browser_product(self, url):
        """
        Запуск браузера, загрузка начальной страницы продукта, выбор города
        """
        pass

    def _wd_next_page(self):
        """
        Переход на заданную страницу num_page через клик (для имитации пользователя)
        """
        for num_try in range(3):

            if num_try and not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            # Поиск следующей кнопки страницы
            num_page_elem = self._wd_find_elem(By.XPATH,
                                               f"//a[@databases-page='{self.cur_page}']")
            if not num_page_elem:
                self.logger.info("Достигнут конец каталога")
                return False

            # Клик - переход на следующую страницу
            if not self._wd_ac_click_elem(num_page_elem):
                self.logger.error("Не могу кликнуть на страницу в __wd_next_page")
                self.driver.refresh()
                continue

            # Специальная задержка между переключениями страниц для имитации юзера
            time.sleep(self.wait_between_pages_sec)

            # Ждем, пока не прогрузится страница
            if not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            no_in_stock = self._wd_find_all_elems(By.XPATH, '//span[contains(text(), "Узнать о поступлении")]')
            if no_in_stock and len(no_in_stock) == 48:
                self.logger.info("Вся страница неактуальна, выход")
                return False

            self.cur_page += 1
            return True
        else:
            self.logger.error("!! После 3 попыток не получилось переключить страницу #{} !!".format(self.cur_page))
            return False

    def _parse_product_page(self, html, url):
        """
        Метод для парсинга html страницы продукта
        """
        pass

    def _parse_catalog_block(self, block):
        """
        Метод для парсинга html страницы товара
        """

        # Название модели
        full_name = block.select_one('a.ProductCardHorizontal__title.Link.js--Link.Link_type_default')
        if not full_name:
            self.logger.warning("No model name and URL")
            return
        else:
            url = full_name.get('href')
            full_name = full_name.text.replace('\n', '').replace('  ', ' ').strip()

        # Проверка на наличие
        if [item.text for item in block.select('button[type="button"]') if "Узнать о поступлении" in item.text]:
            self.logger.info("Товара '{}' нет в наличии, пропуск".format(full_name))
            return

        # Исключение
        if 'clevercel' in full_name.lower():
            self.logger.info('CLEVERCEL - Skip')
            return

        # URL
        if not url:
            self.logger.warning("No URL")
            return
        else:
            url = self.domain + url

        # Ссылка на изображение товара
        img_url = block.select_one('div.ProductCardHorizontal__picture-hover_part.'
                                   'js--ProductCardInListing__picture-hover_part')
        if not img_url:
            self.logger.warning("No img url")
            return
        else:
            img_url = img_url.get('databases-src')

        # Рейтинг товара и на основании скольки отзывов построен
        rating, num_rating = 0, 0
        rating_and_num_rating = block.select(
            'div.Tooltip__content.js--Tooltip__content.ProductCardHorizontal__tooltip__content.Tooltip__content_center')
        if rating_and_num_rating:
            for item in rating_and_num_rating:
                if 'рейтинг' in item.text.lower():
                    rating = float(re.findall(r'\d+.\d+', item.text)[0].replace(',', '.'))
                if 'отзыв' in item.text.lower():
                    num_rating = int(re.findall(r'\d+', item.text)[0])

        # Код продукта
        product_code = "None"

        # RAM, ROM
        ram, rom = 0, 0
        characteristics = block.select('li.ProductCardHorizontal__properties_item')
        if not characteristics:
            self.logger.error("Нет характеристик")
            return
        else:
            for item in characteristics:
                if 'оперативн' in item.text.lower():
                    ram = int(re.findall(r'\d+', item.text)[0])
                if 'встроенн' in item.text.lower():
                    rom = int(re.findall(r'\d+', item.text)[0])

        # Цена
        price = block.select_one('span.ProductCardHorizontal__price_current-price')
        if not price:
            self.logger.warning("No price")
            return
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Парсинг названия модели
        brand_name, model_name, color = citilink_parse_model_name(full_name)
        if not brand_name or not model_name or not color:
            self.logger.warning("No brand name, model name or color")
            return

        # Добавление полученных результатов в коллекцию
        self._add_to_pr_result_list(brand_name, model_name, color, price, ram, rom,
                                    img_url, url, rating, num_rating, product_code)


if __name__ == '__main__':
    import main

    time_start = time.time()
    main.load_allowed_model_names_list_for_base()
    main.load_exceptions_model_names()
    main.read_config()

    parser = CitilinkParse()
    parser.run_catalog('https://www.citilink.ru/catalog/mobile/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

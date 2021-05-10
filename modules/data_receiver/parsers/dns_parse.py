import time
import re

import selenium.common.exceptions as se
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from modules.data_receiver.parsers.parse_base import ParseBase
import modules.common.helper as h
from modules.common.file_worker import FileWorker

DNS_REBUILT_IPHONE = ' "как новый"'
logger = h.logging.getLogger('dnsparse')


# Парсинг названия модели (получить название модели, цвет и ROM)
def dns_parse_model_name(name):
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Понижение регистра
    name = name.lower()
    # Характеристики из названия
    characteristics = re.findall(r'\[.*]', name)[0]
    name = name.replace(characteristics, '')
    ram = dns_parse_specifications(characteristics)

    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (DNS_REBUILT_IPHONE in name) else ''
    name = name.replace(DNS_REBUILT_IPHONE if rebuilt else '', '')
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Убрать диагональ вначале строки
    name = name.partition(' ')[2]
    # Получить цвет
    color = name[name.find('гб ') + len('гб '):]
    # Получить ROM
    rom = re.findall(r'\d+\sгб', name)[0]
    # Если в названии указан еще и RAM через /
    ram_rom = re.findall(r'\d+[/]\d+\sгб', name)
    # Удалить из названия модели RAM/ROM или только ROM
    name = name.replace(ram_rom[0] if ram_rom else rom, '')
    # Удалить из строки ROM всё, кроме цифр
    rom = re.findall(r'\d+', rom)
    rom = int(rom[0]) if rom else 0
    # Удалить из строки модели цвет, название бренда и слово "смартфон"
    name = name.replace(color, '').replace('смартфон', '').replace(year, '').replace(' nfc ', ' ').replace(' 5g ', ' ')
    # Удалить лишние пробелы
    name = ' '.join(name.split())
    name += rebuilt

    # Проверка названия в словаре исключений названий моделей
    name = h.replace_value_from_dictionary(h.EXCEPT_MODEL_NAMES_DICT, name)

    # # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        FileWorker.list_data.save(h.UNDEFINED_MODEL_NAME_LIST_PATH, data=name, overwrite=False)
        return None, None, None, 0, 0

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color, ram, rom


# Парсинг характеристик (получить RAM)
def dns_parse_specifications(specifications):
    # Понижение регистра
    specifications = specifications.lower()
    # Получение значения ram из строки характеристик
    ram = re.findall(r'\d+\sгб', specifications)
    # Удалить из строки ROM всё, кроме цифр, если эта строка не пустая, иначе 0
    ram = re.findall(r'\d+', ram[0])[0] if ram else 0

    return int(ram)


class DNSParse(ParseBase):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Реализация базового класса ParseBase
    Парсит данные с магазина Днс
    """
    def __init__(self):
        super().__init__(domain='https://www.dns-shop.ru', shop='dns', logger=logger, category="смартфоны")
        self.container_css_selector = 'div.catalog-product.ui-button-widget'

    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций на странице каталога
        """
        # Поиск шапки выбора города и название города
        city_head = self._wd_find_elem(By.XPATH, "//i[@class='location-icon']")
        city_head_text = self._wd_find_elem(By.XPATH, "//div[@class='w-choose-city-widget-label']")
        if not city_head or not city_head_text:
            self.logger.error("Не могу найти элемент с текущим городом на странице")
            return False

        # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
        if self.current_city.lower() not in city_head_text.text.lower():

            if not self._wd_click_elem(city_head):
                self.logger.error("Не могу кликнуть по названию города для его смены")
                return False

            time.sleep(1)

            # Поиск города в заготовленном списке крупных городов
            city_list = self._wd_find_all_elems_with_timeout(By.XPATH, "//span[@databases-role='big-cities']")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(0.5)
                        return self._wd_ac_click_elem(item)
            else:
                self.logger.info("Не вижу нужный город в списке, пробую вбить вручную")

            # Если в заготовонном списке нет нужного города - ищем input и вводим в поиск
            input_city = self._wd_find_elem_with_timeout(By.XPATH, "//input[@databases-role='search-city']")
            if not input_city:
                self.logger.error("Не могу найти поле для ввода города")
                return False

            # Кликнуть на форму для ввода текста
            if not self._wd_ac_click_elem(input_city):
                self.logger.error("Не могу кликнуть на форму для ввода текста")
                return False
            time.sleep(1)

            # Ввод названия города по буквам
            for char in self.current_city:
                self._wd_ac_send_keys(input_city, char)

            # Найти в результирующем списке нужный город
            city_list = self._wd_find_all_elems_with_timeout(By.XPATH, "//li[@class='modal-row']/a/span/mark")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(0.5)
                        return self._wd_ac_click_elem(item)
            else:
                self.logger.error("Не вижу нужный город в списке input, выход")
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
        if not self._wd_find_elem_with_timeout(By.XPATH,
                                               "//div[contains(@class, 'product-buy__price')]"):
            return False

        self.logger.info("Page loaded")
        return True

    def _wd_check_load_page_product(self):
        """
        Проверка по ключевым div-ам что страница продукта прогружена полностью
        """
        pass

    def _wd_open_browser_catalog(self, url):
        """
        Запуск браузера, загрузка начальной страницы каталога, выбор города
        """
        if not super()._wd_open_browser_catalog(url=url):
            return False

        self._wd_scroll_down()
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

            if num_try:
                self._wd_scroll_up()

            # Поиск следующей кнопки страницы
            num_page_elem = self._wd_find_elem(By.XPATH,
                                                "//a[@class='pagination-widget__page-link' and text()='{}']".
                                                format(self.cur_page))
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
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Скролл
            self._wd_scroll_down()

            # Особенность ДНС - при переключении страницы иногда не меняется контент. Если так - обновляем страницу
            try:
                self.wait.until_not(presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                    self.pr_result_list[-5].url.replace(self.domain, '')))))

                self.logger.info("Cur_page = {}".format(self.cur_page))
                self.cur_page += 1
                return True
            except se.TimeoutException:
                print("НЕ ДОЖДАЛСЯ -5, обновляю")
                self.logger.error("TimeoutException в __wd_next_page, обновляю страницу")
                self.driver.refresh()
                continue
            except IndexError:
                self.logger.error('Список pr_result_list[-5] оказался пуст, выход за границы списка')
                return False
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
        Парсинг данных одного блока
        """
        # Название модели и URL
        model_name_url_block = block.select_one('a.catalog-product__name.ui-link.ui-link_black')
        if not model_name_url_block:
            self.logger.warning("No model name and URL")
            return
        else:
            url = self.domain + model_name_url_block.get('href')
            model_name = model_name_url_block.text

        # Проверка на предзаказ
        if [item.text for item in block.select("button") if item.text == "Предзаказ"]:
            self.logger.info("Товар '{}' по предзаказу, пропуск".format(model_name))
            return

        # Ссылка на изображение товара
        img_url = block.select_one('img.loaded')
        if not img_url:
            self.logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')

        # Рейтинг товара
        rating_block = block.select_one('a.catalog-product__rating.ui-link.ui-link_black')
        if not rating_block:
            rating = 0
            num_rating = 0
        else:
            rating = float(rating_block.get('data-rating'))

            # Кол-во отзывов
            num_rating = re.findall(r'\d+\.*\d*k*', rating_block.text)
            if num_rating:
                num_rating = num_rating[0]
                num_rating = int(float(num_rating.replace('k', '')) * 1000) if 'k' in num_rating \
                    else int(num_rating)
            else:
                num_rating = 0

        # Код продукта
        product_code = block.get('databases-code')
        if not product_code:
            self.logger.warning("No product code")

        # Цена
        price = block.select_one('div.product-buy__price')
        if not price:
            print("ДНС: НЕТ ЦЕНЫ !!!!!!")
            self.logger.warning("No price")
            return
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Парсинг названия модели
        brand_name, model_name, color, ram, rom = dns_parse_model_name(model_name)
        if not brand_name or not model_name or not color or not rom:
            self.logger.warning("No brand name, model name, color or rom")
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

    parser = DNSParse()

    parser.run_catalog('https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

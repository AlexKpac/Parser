import time
import re

from selenium.webdriver.common.by import By
from modules.data_receiver.parsers.parse_base import ParseBase

import modules.common.helper as h
from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('mtsparse')


def mts_parse_model_name(name):
    """
    Парсинг названия модели (получить название модели, цвет и ROM)
    """
    # Защита от неправильных названий
    if len(name.split()) < 3:
        return "error", "error", "error", 0, 0
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)
    # Понижение регистра
    name = name.lower()
    name = name.replace('dual sim', '').replace('lte', '').replace(' nfc ', ' ').\
        replace(' 5g ', ' ').replace('«', '').replace('»', '')
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Только для самсунгов - удалить код модели
    samsung_code = re.findall(r'samsung ([\w+]*?) galaxy', name)
    samsung_code = samsung_code[0] if samsung_code else ''
    # Получить размер RAM и ROM, если есть
    ram_rom = re.findall(r'\d*/*\d+ *(?:gb|tb)', name)
    rom, ram = 0, 0
    if ram_rom:
        ram_rom = ram_rom[0]
        if '/' in ram_rom:
            ram_rom_digit = re.findall(r'\d+', ram_rom)
            ram = int(ram_rom_digit[0])
            rom = int(ram_rom_digit[1])
        else:
            ram = 0
            rom = int(re.findall(r'\d+', ram_rom)[0])
    else:
        ram_rom = ''
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Получить 2 слова цвета
    color1, color2 = name.split()[-2:] if name.split()[-1] != ram_rom \
        else name.split()[-3:-1]
    # Если первое слово цвета состоит только из букв и длиннее 2 символов - добавить к итоговому цвету
    color = color1 + " " + color2 if (color1.isalpha() and len(color1) > 2) else color2
    # Удалить лишние слова в названии модели
    name = name.replace(ram_rom, '').replace(color, '').replace(year, ''). \
        replace(samsung_code, '').replace('  ', ' ').strip()

    # Проверка названия в словаре исключений названий моделей
    name = h.replace_value_from_dictionary(h.EXCEPT_MODEL_NAMES_DICT, name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        FileWorker.list_data.save(h.UNDEFINED_MODEL_NAME_LIST_PATH, data=name, overwrite=False)
        return None, None, None, 0, 0

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color, ram, rom


class MTSParse(ParseBase):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Реализация базового класса ParseBase
    Парсит данные с магазина МТС
    """
    def __init__(self):
        super().__init__(domain="https://www.shop.mts.ru", shop="mts", logger=logger, category="смартфоны")
        self.container_css_selector = 'div.card-product-wrapper.card-product-wrapper--catalog'

    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций на странице каталога
        """
        city = self._wd_find_elem_with_timeout(By.XPATH, "//span[@class='current-region__text']")
        if not city:
            self.logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (self.current_city.lower() in city.text.lower()):
            self.logger.info("Неверный город")

            # Клик по городу
            if not self._wd_ac_click_elem(city):
                self.logger.error("Не могу нажать на кнопку выбора города")
                return False

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self._wd_find_all_elems_with_timeout(By.CLASS_NAME, "default-regions__item")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self._wd_ac_click_elem(item)
            else:
                self.logger.warning("Нет списка городов, попробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self._wd_find_elem_with_timeout(By.XPATH, "//div[@class='select-region-form__fieldset "
                                                                    "input-group__fieldset']")
            if not input_city:
                self.logger.error("Не найдено поле, куда вводить новый город")
                return False

            time.sleep(1)

            # Кликнуть на форму для ввода текста
            if not self._wd_ac_click_elem(input_city):
                self.logger.error("Не могу нажать на поле поиска")
                return False

            # Ввод названия города по буквам
            for char in self.current_city:
                self._wd_ac_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self._wd_find_elem_with_timeout(By.XPATH, "//li[@class='list-results__item']")
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
        Алгоритм выбора города для всех возможных ситуаций на странице продукта
        """
        pass

    def _wd_check_load_page_catalog(self):
        """
        Проверка по ключевым div-ам что страница каталога прогружена полностью
        """
        # Ожидание прогрузки цен
        if not self._wd_find_elem_with_timeout(By.CLASS_NAME, "product-price__current"):
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

        # Скролл страницы 1
        if not self._wd_scroll_down(count_press=10, timeout=0.3):
            self.logger.error("Не удалось прогрузить страницу после скролла в __wd_open_browser (3)")
            return False

        time.sleep(4)

        # Скролл страницы 2 (подргужается автоматически)
        if not self._wd_scroll_down(count_press=10, timeout=0.3):
            self.logger.error("Не удалось прогрузить страницу после скролла в __wd_open_browser (4)")
            return False

        time.sleep(2)
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
            num_page_elem = self._wd_find_elem(By.XPATH, "//div[contains(@class, 'pagination__page')]/"
                                                          "a[text()='{}']".format(self.cur_page))
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

            no_in_stock = self._wd_find_all_elems(By.XPATH, '//div[contains(text(), "Нет в наличии") or contains(text(), "Скоро в продаже")]')
            if no_in_stock and len(no_in_stock) == 30:
                self.logger.info("Вся страница неактуальна, выход")
                return False

            # Ждем, пока не прогрузится страница
            if not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Скролл вниз и ожидание прогрузки страницы
            if not self._wd_scroll_down(count_press=10, timeout=0.3):
                self.logger.error("Не удалось прогрузить страницу после скролла в __wd_next_page")
                self.driver.refresh()
                continue

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
        full_name = block.select_one('a.card-product-description__heading')
        if not full_name:
            self.logger.warning("No model name and URL")
            return
        else:
            full_name = full_name.get('aria-label').replace('\n', '').strip()

        # Проверка на предзаказ
        if [item.text for item in block.select("span.button__text") if item.text == "Предзаказ"]:
            self.logger.info("Товар '{}' по предзаказу, пропуск".format(full_name))
            return

        # Проверка на мобильный телефон
        type_product = block.select_one("div.card-product-description__type")
        if type_product and "Мобильный телефон" in type_product.text:
            self.logger.info("Найден мобильный телефон, пропуск")
            return

        # URL
        url = block.select_one('a.card-product-description__heading')
        if not url:
            self.logger.warning("No URL")
            return
        else:
            url = self.domain + url.get('href')

        # Ссылка на изображение товара
        img_url = block.select_one('img.gallery__img')
        if not img_url:
            self.logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')

            if '/resize/' in img_url:
                img_url = img_url[:img_url.index('/resize/')]

        # Рейтинг товара
        rating = block.select_one('span.assessment-product__text')
        if not rating:
            rating = 0
        else:
            rating = float(rating.text.replace(' ', '').replace('\n', '').replace(',', '.'))

        # На основании скольки отзывов построен рейтинг
        num_rating = block.select_one('span.assessment-product__text')
        if not num_rating:
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text)[0])

        # Код продукта
        product_code = "None"

        # Цена
        price = block.select_one('span.product-price__current')
        if not price:
            self.logger.warning("No price")
            return
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Попытка применить промокод
        # old_price = block.select_one('div.product-price__old')
        # promo_code = block.select('div.action-product-item.promo-action')
        # if not old_price and promo_code:
        #     for item in promo_code:
        #         if 'промокод' in item.text:
        #             self.logger.info('Нашел промокод "{}", применяю'.format(item.text))
        #             promo_code = re.findall(r'\d+', item.text.replace(' ', ''))
        #             promo_code = int(promo_code[0]) if promo_code else 0
        #             price -= promo_code
        #             break

        # Парсинг названия модели
        brand_name, model_name, color, ram, rom = mts_parse_model_name(full_name)
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

    parser = MTSParse()
    parser.run_catalog('https://shop.mts.ru/catalog/smartfony/14/', 14)
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

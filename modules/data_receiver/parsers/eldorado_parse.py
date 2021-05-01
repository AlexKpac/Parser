import time
import re

from selenium.webdriver.common.by import By
from modules.data_receiver.parsers.parse_base import ParseBase

import modules.common.helper as h
from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('eldoradoparse')
ELDORADO_REBUILT_IPHONE = 'как новый'


def eldorado_parse_model_name(name):
    """
    Парсинг названия модели (получить название модели, цвет и ROM)
    """
    # Защита от неправильных названий
    if len(name.split()) < 5:
        return None, None, None
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (ELDORADO_REBUILT_IPHONE in name.lower()) else ''
    name = name.replace(ELDORADO_REBUILT_IPHONE, '')
    # Оборачивание скобками названия модели, если их не было
    last_word = name.split()[-1]
    if last_word.isupper() and \
            not ('(' in last_word) and \
            not (')' in last_word):
        name = name.replace(last_word, '({})'.format(last_word))
    # Понижение регистра
    name = name.lower()
    # Удалить nfc и 5g
    name = name.replace(' nfc ', ' ').replace(' 5g ', ' ')
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Получить размер ROM
    rom = re.findall(r'\d*[gb]*[\+/]*\d+(?:gb|tb)', name)
    rom = (rom[0]) if rom else ""
    # Получить ЦВЕТ
    # Получить 2 слова цвета
    color1, color2 = name.split()[-2:] if name.split()[-1] != rom \
        else name.split()[-3:-1]
    # Если первое слово цвета состоит только из букв и длиннее 2 символов и отсутствует в игнор-листе - добавить
    # к итоговому цвету
    color1 = color1 if (
            color1.isalpha() and len(color1) > 2 and not (color1.strip() in h.IGNORE_WORDS_FOR_COLOR)) else ""
    color = color1 + " " + color2 if (color1.isalpha() and len(color1) > 2) else color2
    # Удалить первую часть часть
    name = name.replace('смартфон', '').replace(rom, '').replace(year, '').replace('  ', ' ')
    # Убрать вторую часть лишних слов из названия
    name = name.replace(color, '').replace('  ', ' ').strip()
    name += rebuilt

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


class EldoradoParse(ParseBase):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Реализация базового класса ParseBase
    Парсит данные с магазина Эльдорадо
    """

    def __init__(self):
        super().__init__(domain="https://www.eldorado.ru", shop="eldorado", logger=logger, category="смартфоны")
        self.is_grid = True
        self.container_css_selector = 'li[databases-dy="product"]'

    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций на странице каталога
        """
        city = self._wd_find_elem_with_timeout(By.XPATH, "//span[@class='h8xlw5-3 kLXpZr']")
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

            self.logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self._wd_find_all_elems_with_timeout(By.CLASS_NAME, "N5ndClh")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self._wd_ac_click_elem(item)
            else:
                self.logger.info("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self._wd_find_elem_with_timeout(By.XPATH, "//input[@name='region-search']")
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
            input_city_item = self._wd_find_elem_with_timeout(By.XPATH, "//span[contains(text(),'{}')]".format(
                self.current_city))
            if not input_city_item:
                self.logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self._wd_ac_click_elem(input_city_item):
                self.logger.error("Не могу нажать на выбранный город")
                return False

        return True

    def __wd_city_selection_product(self):
        """
        Алгоритм выбора города для всех возмодных ситуаций на странице продукта
        """
        pass

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
        if not self._wd_find_elem_with_timeout(By.XPATH, '//span[@databases-pc="offer_price"]'):
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

        return True

    def _wd_open_browser_product(self, url):
        """
        Запуск браузера, загрузка начальной страницы продукта, выбор города
        """
        pass

    def _wd_next_page(self):
        """
        Переход на заданную страницу num_page через клик
        """
        for num_try in range(3):

            if num_try and not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            # Поиск следующей кнопки страницы
            num_page_elem = self._wd_find_elem(By.XPATH, "//a[@aria-label='Page {}']".format(self.cur_page))
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

            no_in_stock = self._wd_find_all_elems(By.XPATH, '//span[text()="Нет в наличии"]')
            if no_in_stock and len(no_in_stock) == 36:
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
        full_name = block.select_one('a[databases-dy="title"]')
        if not full_name:
            self.logger.warning("No model name and URL")
            return
        else:
            url = full_name.get('href')
            full_name = full_name.text.replace('\n', '').replace('  ', ' ').strip()

        # Проверка на "Нет в наличии" И предзаказ
        if [item.text for item in block.select('span') if ("Нет в наличии" in item.text or
                                                           "Оформить предзаказ" in item.text)]:
            self.logger.info("Товара '{}' нет в наличии или предзаказ, пропуск".format(full_name))
            return

        # URL
        if not url:
            self.logger.warning("No URL")
            return
        else:
            url = self.domain + url

        # Ссылка на изображение товара
        img_url = block.select_one('a[href="{}"] > img'.format(url.replace(self.domain, '')))
        if not img_url:
            self.logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')

            if '/resize/' in img_url:
                img_url = img_url[:img_url.index('/resize/')]

        # Рейтинг товара и на основании скольки отзывов построен
        rating = len(block.select('span.tevqf5-2.fBryir'))
        num_rating = block.select_one('a[databases-dy="review"]')
        if not num_rating:
            self.logger.info("No num rating")
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text)[0])

        # Код продукта
        product_code = "None"

        # RAM, ROM
        ram, rom = 0, 0
        characteristics = block.select('li.aKmrwMA')
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
        price = block.select_one('span[databases-pc="offer_price"]')
        if not price:
            self.logger.warning("No price")
            return
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Парсинг названия модели
        brand_name, model_name, color = eldorado_parse_model_name(full_name)
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

    parser = EldoradoParse()
    parser.run_catalog('https://www.eldorado.ru/c/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

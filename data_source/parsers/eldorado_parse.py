import time
import re
import csv
import configparser

import bs4
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
import selenium.webdriver.support.expected_conditions as ec
from selenium.webdriver.common.action_chains import ActionChains

import common.general_helper as h

logger = h.logging.getLogger('eldoradoparse')
ELDORADO_REBUILT_IPHONE = 'как новый'


# Парсинг названия модели (получить название модели, цвет и ROM)
def eldorado_parse_model_name(name):
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
    name = h.find_and_replace_except_model_name(name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        return None, None, None

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color


class EldoradoParse:

    def __init__(self):
        options = Options()
        options.add_argument("window-size=1920,1080")
        options.add_argument("--disable-notifications")

        # try:
        #     self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        # except se.WebDriverException:
        #     print("НЕ СМОГ ИНИЦИАЛИЗИРОВАТЬ WEBDRIVER")
        #     self.driver = None
        #     return

        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)

        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 20)
        self.pr_result_list = []
        self.cur_page = 2
        # Данные магазина
        self.domain = "https://www.eldorado.ru"
        self.shop = "эльдорадо"
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.current_city = self.config.defaults()['current_city']
        self.wait_between_pages_sec = int(self.config.defaults()['wait_between_pages_sec'])
        self.is_grid = True

    # Обертка поиска элемента для обработки исключений
    def __wd_find_elem(self, by, xpath):
        try:
            result = self.driver.find_element(by, xpath)
            return result
        except se.NoSuchElementException:
            return None

    # Поиск элемента с таймаутом
    def __wd_find_elem_with_timeout(self, by, elem):
        try:
            result = self.wait.until(ec.presence_of_element_located((by, elem)))
            return result
        except se.TimeoutException:
            return None

    # Поиск всех элементов с таймаутом
    def __wd_find_all_elems_with_timeout(self, by, elem):
        try:
            result = self.wait.until(ec.presence_of_all_elements_located((by, elem)))
            return result
        except se.TimeoutException:
            return None

    # Поиск всех элементов без таймаута
    def __wd_find_all_elems(self, by, xpath):
        try:
            result = self.driver.find_elements(by, xpath)
            return result
        except se.NoSuchElementException:
            return None

    # Отправка клавиши в элемент через ActionChains
    def __wd_ac_send_keys(self, elem, keys):
        if not elem:
            return False

        try:
            ActionChains(self.driver).move_to_element(elem).send_keys(keys).perform()
        except Exception:
            return False

        return True

    # Обертка для клика по элементу через ActionChains
    def __wd_ac_click_elem(self, elem):
        if not elem:
            return False

        try:
            ActionChains(self.driver).move_to_element(elem).click().perform()
        except Exception:
            return False

        return True

    # Алгоритм выбора города для всех возможных ситуаций на странице каталога
    def __wd_city_selection_catalog(self):
        city = self.__wd_find_elem_with_timeout(By.XPATH, "//span[@class='h8xlw5-3 kLXpZr']")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (self.current_city.lower() in city.text.lower()):
            logger.info("Неверный город")

            # Клик по городу
            if not self.__wd_ac_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "N5ndClh")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self.__wd_ac_click_elem(item)
            else:
                logger.info("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//input[@name='region-search']")
            if not input_city:
                logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            if not self.__wd_ac_click_elem(input_city):
                logger.error("Не могу кликнуть на форму для ввода текста")
                return False

            # Ввод названия города по буквам
            for char in self.current_city:
                self.__wd_ac_send_keys(input_city, char)
                time.sleep(0.2)

            time.sleep(2)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//span[contains(text(),'{}')]".format(
                self.current_city))
            if not input_city_item:
                logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_ac_click_elem(input_city_item):
                logger.error("Не могу нажать на выбранный город")
                return False

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.XPATH, '//span[@databases-pc="offer_price"]'):
            return False

        logger.info("Page loaded")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Скролл вниз для прогрузки товаров на странице
    def __wd_scroll_down(self):
        pass

    # Переключение на отображение товаров в виде списка
    def __wd_select_list_view(self):
        pass

    # Запуск браузера, загрузка начальной страницы каталога, выбор города
    def __wd_open_browser_catalog(self, url):
        try:
            self.driver.get(url)
        except (se.TimeoutException, se.WebDriverException):
            print("Не смог загрузить страницу")
            logger.error("Не смог загрузить страницу")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (1)")
            return False

        # Выбор города
        if not self.__wd_city_selection_catalog():
            logger.error("Не могу выбрать город")
            return False

        time.sleep(2)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        ####################################################

        return True

    # Запуск браузера, загрузка начальной страницы продукта, выбор города
    def __wd_open_browser_product(self, url):
        pass

    # Получить текущий код страницы
    def __wd_get_cur_page(self):
        try:
            return self.driver.page_source
        except se.TimeoutException:
            return None
        except se.WebDriverException:
            return None

    # Переход на заданную страницу num_page через клик
    def __wd_next_page(self):
        for num_try in range(3):

            if num_try and not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            # Поиск следующей кнопки страницы
            num_page_elem = self.__wd_find_elem(By.XPATH, "//a[@aria-label='Page {}']".format(self.cur_page))
            if not num_page_elem:
                logger.info("Достигнут конец каталога")
                return False

            # Клик - переход на следующую страницу
            if not self.__wd_ac_click_elem(num_page_elem):
                logger.error("Не могу кликнуть на страницу в __wd_next_page")
                self.driver.refresh()
                continue

            # Специальная задержка между переключениями страниц для имитации юзера
            time.sleep(self.wait_between_pages_sec)

            # Ждем, пока не прогрузится страница
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            no_in_stock = self.__wd_find_all_elems(By.XPATH, '//span[text()="Нет в наличии"]')
            if no_in_stock and len(no_in_stock) == 36:
                logger.info("Вся страница неактуальна, выход")
                return False

            self.cur_page += 1
            return True
        else:
            logger.error("!! После 3 попыток не получилось переключить страницу #{} !!".format(self.cur_page))
            return False

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        if self.driver:
            self.driver.quit()

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html, url):
        pass

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        soup = bs4.BeautifulSoup(html, 'lxml')

        # Категория (из хлебных крошек)
        self.category = soup.select_one('h1[databases-pc="cat_name"]')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = self.category.text.replace('\n', '').strip().lower()

        # Контейнер с элементами
        container = soup.select('li[databases-dy="product"]')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):
        # Название модели
        full_name = block.select_one('a[databases-dy="title"]')
        if not full_name:
            logger.warning("No model name and URL")
            return
        else:
            url = full_name.get('href')
            full_name = full_name.text.replace('\n', '').replace('  ', ' ').strip()

        # Проверка на "Нет в наличии" И предзаказ
        if [item.text for item in block.select('span') if ("Нет в наличии" in item.text or
                                                           "Оформить предзаказ" in item.text)]:
            logger.info("Товара '{}' нет в наличии или предзаказ, пропуск".format(full_name))
            return

        # URL
        if not url:
            logger.warning("No URL")
            return
        else:
            url = self.domain + url

        # Ссылка на изображение товара
        img_url = block.select_one('a[href="{}"] > img'.format(url.replace(self.domain, '')))
        if not img_url:
            logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')

            if '/resize/' in img_url:
                img_url = img_url[:img_url.index('/resize/')]

        # Рейтинг товара и на основании скольки отзывов построен
        rating = len(block.select('span.tevqf5-2.fBryir'))
        num_rating = block.select_one('a[databases-dy="review"]')
        if not num_rating:
            logger.info("No num rating")
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text)[0])

        # Код продукта
        product_code = "None"

        # RAM, ROM
        ram, rom = 0, 0
        characteristics = block.select('li.aKmrwMA')
        if not characteristics:
            logger.error("Нет характеристик")
            return
        else:
            for item in characteristics:
                if 'оперативн' in item.text.lower():
                    ram = int(re.findall(r'\d+', item.text)[0])
                if 'встроенн' in item.text.lower():
                    rom = int(re.findall(r'\d+', item.text)[0])

        # Цена
        cur_price = block.select_one('span[databases-pc="offer_price"]')
        if not cur_price:
            logger.warning("No price")
            return
        else:
            cur_price = int(re.findall(r'\d+', cur_price.text.replace(' ', ''))[0])

        # Парсинг названия модели
        brand_name, model_name, color = eldorado_parse_model_name(full_name)
        if not brand_name or not model_name or not color:
            logger.warning("No brand name, model name or color")
            return

        if 'apple' in brand_name.lower():
            ram = 0

        # Добавление полученных результатов в коллекцию
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=self.category.lower(),
            brand_name=brand_name.lower(),
            model_name=model_name.lower(),
            color=color.lower(),
            cur_price=cur_price,
            ram=ram,
            rom=rom,
            img_url=img_url.lower(),
            url=url.lower(),
            rating=rating,
            num_rating=num_rating,
            product_code=product_code.lower(),
        ))

    # Сохранение всего результата в csv файл
    def __save_result(self, name):
        with open(h.CSV_PATH_RAW + name, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS)
            for item in self.pr_result_list:
                writer.writerow(item)

    # Запуск работы парсера для каталога
    def run_catalog(self, url, cur_page=None):
        if not self.driver:
            self.__wd_close_browser()
            return None

        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return None

        if cur_page:
            self.cur_page = cur_page + 1

        while True:
            html = self.__wd_get_cur_page()
            self.__parse_catalog_page(html)
            if not self.__wd_next_page():
                break

        self.__wd_close_browser()
        self.__save_result("eldorado.csv")
        return self.pr_result_list

    # Запуск работы парсера для продукта
    def run_product(self, url):
        pass


if __name__ == '__main__':
    import main

    time_start = time.time()
    main.load_allowed_model_names_list_for_base()
    main.load_exceptions_model_names()
    main.read_config()

    parser = EldoradoParse()
    parser.run_catalog('https://www.eldorado.ru/c/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

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

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import bot
import header as h
import checker

logger = h.logging.getLogger('citilinkparse')
CITILINK_REBUILT_IPHONE = '"как новый"'


# Парсинг названия модели (получить название модели, цвет и ROM)
def citilink_parse_model_name(name):
    # Защита от неправильных названий
    if len(name.split()) < 3 or not name.count(','):
        return None, None, None
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Понижение регистра
    name = str.lower(name)
    name = name.replace('dual sim', '').replace('lte', '').replace(' nfc ', ' ').\
        replace(' 5g ', ' ').replace('«', '').replace('»', '')
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (CITILINK_REBUILT_IPHONE in name) else ''
    name = name.replace(CITILINK_REBUILT_IPHONE, '')
    # Цвет
    color = name[name.rfind(','):].replace(',', '').replace('(product)', '').strip()
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
    name = name.replace('смартфон', '').replace(ram_rom, '').replace(color, '').\
        replace(year, '').replace('  ', ' ').strip()

    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)
    name += rebuilt
    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        return None, None, None

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color


class CitilinkParse:

    def __init__(self):
        options = Options()
        options.add_argument("window-size=1920,1080")
        options.add_argument("--disable-notifications")
        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 30)
        self.pr_result_list = []
        self.cur_page = 2
        # Данные магазина
        self.domain = "https://www.citilink.ru"
        self.shop = "ситилинк"
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

    # Отправка клавиши в элемент через ActionChains
    def __wd_send_keys(self, elem, keys):
        ActionChains(self.driver).move_to_element(elem).send_keys(keys).perform()
        return True
        #     if not elem:
        #         return False
        #
        #     # TODO: доделать обертку try-except
        #     ActionChains(self.driver).move_to_element(elem).send_keys(keys).perform()
        #     return True

    # Обертка для клика по элементу через ActionChains
    def __wd_click_elem(self, elem):
        if not elem:
            return False

        # try:
        #     elem.click()
        #     return True
        # except se.ElementClickInterceptedException:
        #     print("Элемент некликабельный")
        #     return False

        # # TODO: доделать обертку try-except
        ActionChains(self.driver).move_to_element(elem).click().perform()
        return True

    # Алгоритм выбора города для всех возможных ситуаций на странице каталога
    def __wd_city_selection_catalog(self):
        city = self.__wd_find_elem_with_timeout(By.CLASS_NAME, "MainHeader__city")
        if not city:
            print("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (self.current_city.lower() in city.text.lower()):
            print("Неверный город")

            # Клик по городу
            if not self.__wd_click_elem(city):
                print("Не могу нажать на кнопку выбора города")
                return False

            print("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "CitiesSearch__main-cities-list-item")
            if city_list:
                for item in city_list:
                    if str.lower(self.current_city) in str.lower(item.text):
                        time.sleep(1.5)
                        return self.__wd_click_elem(item)
            else:
                print("Нет списка городов, попробую вбить вручную")

            print("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//input[@type='search']")
            if not input_city:
                print("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            ActionChains(self.driver).move_to_element(input_city).click().perform()

            # Ввод названия города по буквам
            for char in self.current_city:
                self.__wd_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(4)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH,
                                                               "//a[@data-search='{}']".format(self.current_city.lower()))
            if not input_city_item:
                print("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_click_elem(input_city_item):
                print("Не могу нажать на выбранный город")
                return False

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):

        # CLASS ProductCardHorizontal__price_current-price - списком
        # CLASS ProductCardVerticalPrice__price-current_current-price - сеткой

        # Ожидание прогрузки цен

        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "ProductCardVerticalPrice__price-current_current-price"
                                                if self.is_grid else "ProductCardHorizontal__price_current-price"):
            return False

        # Ожидание прогрузки пагинации
        # if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "pagination"):
        #     return False
        # logger.info('Пагинация прогрузилась')

        print("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Скролл вниз для прогрузки товаров на странице
    def __wd_scroll_down(self):
        for i in range(20):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.3)

        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
            return False

        return True

    def __wd_select_list_view(self):
        # Если есть этот тег в html коде, значит сейчас стоит табличный вид, переключаем на список
        if self.__wd_find_elem(By.XPATH,
                               "//label[@class='ProductCardCategoryList__icon ProductCardCategoryList__icon_grid "
                               "ProductCardCategoryList__icon-active']"):

            # Переключение с табличного вида на список
            listing_views = self.__wd_find_elem_with_timeout(By.XPATH,
                                                             "//span[@class='gray-icon IconFont IconFont_size_m "
                                                             "IconFont_list']")
            if not listing_views:
                logger.error("Не могу найти listing views")
                return False

            # Клик
            if not self.__wd_click_elem(listing_views):
                logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

            self.is_grid = False

        return True

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

        # Переключение на отображение товаров в виде списка
        if not self.__wd_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        # Скролл страницы
        # if not self.__wd_scroll_down():
        #     logger.error("Не удалось прогрузить страницу после скролла в __wd_open_browser (3)")
        #     return False

        time.sleep(2)

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

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):

        print(self.cur_page)

        # self.driver.refresh()
        # time.sleep(3)
        # # Ждем, пока не прогрузится страница
        # if not self.__wd_check_load_page_catalog():
        #     print("Не удалось прогрузить страницу в __wd_next_page (1)")
        #     return False

        time.sleep(2)

        # Поиск следующей кнопки страницы
        num_page_elem = self.__wd_find_elem(By.XPATH,
                                            f"//a[@data-page='{self.cur_page}']")
        if not num_page_elem:
            # num_last_page_elem = self.__wd_find_elem(By.XPATH, "")
            # if num_last_page_elem and self.cur_page + 1 ==
            print("Достигнут конец каталога")
            return False

        # num_page_elem.click()
        # Клик - переход на следующую страницу
        if not self.__wd_click_elem(num_page_elem):
            print("Не могу кликнуть на страницу в __wd_next_page")
        else:
            self.cur_page += 1

        time.sleep(2)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            print("Не удалось прогрузить страницу в __wd_next_page (1)")
            return False

        # Специальная задержка между переключениями страниц для имитации юзера
        time.sleep(self.wait_between_pages_sec)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            print("Не удалось прогрузить страницу в __wd_next_page (2)")
            return False

        # Скролл вниз и ожидание прогрузки страницы
        # if not self.__wd_scroll_down():
        #     logger.error("Не удалось прогрузить страницу после скролла в __wd_next_page (1)")
        #     return False

        return True

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html, url):
        pass

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        soup = bs4.BeautifulSoup(html, 'lxml')

        # Категория (из хлебных крошек)
        self.category = soup.select_one('h1.Heading.Heading_level_1.Subcategory__title')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = self.category.text.replace('\n', '').strip().lower()

        # Контейнер с элементами
        container = soup.select('div.product_data__gtm-js.product_data__pageevents-js.'
                                'ProductCardHorizontal.js--ProductCardInListing.js--ProductCardInWishlist')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):

        # Название модели
        full_name = block.select_one('a.ProductCardHorizontal__title.Link.js--Link.Link_type_default')
        if not full_name:
            print("No model name and URL")
            return
        else:
            url = full_name.get('href')
            full_name = full_name.text.replace('\n', '').replace('  ', ' ').strip()

        # Исключение
        if 'clevercel' in full_name.lower():
            logger.info('CLEVERCEL - Skip')
            return

        # URL
        if not url:
            print("No URL")
            return
        else:
            url = self.domain + url

        # Ссылка на изображение товара
        img_url = block.select_one('div.ProductCardHorizontal__picture-hover_part.'
                                   'js--ProductCardInListing__picture-hover_part')
        if not img_url:
            print("No img url")
            return
        else:
            img_url = img_url.get('data-src')

        # Рейтинг товара и на основании скольки отзывов построен
        rating = 0
        num_rating = 0

        rating_and_num_rating = block.select('div.Tooltip__content.js--Tooltip__content.ProductCardHorizontal__tooltip__content.Tooltip__content_center')
        if rating_and_num_rating:
            for item in rating_and_num_rating:
                if 'рейтинг' in item.text.lower():
                    rating = float(re.findall(r'\d+.\d+', item.text)[0].replace(',', '.'))
                if 'отзыв' in item.text.lower():
                    num_rating = int(re.findall(r'\d+', item.text)[0])

        # Код продукта
        product_code = "None"

        ram = 0
        rom = 0
        characteristics = block.select('li.ProductCardHorizontal__properties_item')
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
        cur_price = block.select_one('span.ProductCardHorizontal__price_current-price')
        if not cur_price:
            print("No price")
            return
        else:
            cur_price = int(re.findall(r'\d+', cur_price.text.replace(' ', ''))[0])

        print(full_name)
        # print("Category = {}".format(self.category))
        # print("Name = {}".format(full_name))
        # print('RAM = {}'.format(ram))
        # print('ROM = {}'.format(rom))
        # print("Rating = {}".format(rating))
        # print("Num Rating = {}".format(num_rating))
        # print("Url = {}".format(url))
        # print("Img Url = {}".format(img_url))
        # print("Price = {}".format(cur_price))
        # print("-" * 50)

        brand_name, model_name, color = citilink_parse_model_name(full_name)
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
    def __save_result(self):
        with open(h.CSV_PATH_RAW + "citilink.csv", 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS)
            for item in self.pr_result_list:
                writer.writerow(item)

    # Запуск работы парсера для каталога
    def run_catalog(self, url, cur_page=None):
        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return None

        if cur_page:
            self.cur_page = cur_page

        while True:
            html = self.__wd_get_cur_page()
            self.__parse_catalog_page(html)
            if not self.__wd_next_page():
                break

        self.__wd_close_browser()
        self.__save_result()
        return self.pr_result_list

    # Запуск работы парсера для продукта
    def run_product(self, url):
        pass


models = ['Смартфон APPLE iPhone 12 mini 64Gb, MGE03RU/A, (PRODUCT)RED',
          'Смартфон VERTEX Impress Lion 3G Dual Cam 8Gb, синий',
          'Смартфон APPLE iPhone SE 2020 128Gb, MHGU3RU/A, белый',
          'Смартфон ZTE Blade V2020 Smart 64Gb, темно-синий',
          'Смартфон BLACKVIEW 32Gb, BV4900, черный/желтый',
          'Смартфон CLEVERCEL APPLE iPhone 6s 16Gb (подержанный c гарантией), розовое золото',
          'Смартфон SAMSUNG Galaxy Note 20 Ultra 256Gb, SM-N985F, черный',
          'Смартфон HONOR 30 Premium 256Gb, черный',
          'Смартфон CLEVERCEL APPLE iPhone XR 64Gb (подержанный c гарантией), черный',
          'Смартфон CLEVERCEL APPLE iPhone X 64Gb (подержанный c гарантией), серый космос',
          'Смартфон HUAWEI Y8P 4/128Gb, черный',
          'Смартфон SAMSUNG Galaxy S20+ 8/128Gb, SM-G985F, черный',
          'Смартфон HUAWEI Y7 (2019) 64Gb, пурпурный', ]


# Чтение данных
def read_config():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding="utf-8")
    h.REBUILT_IPHONE_NAME = ' ' + config.defaults()['rebuilt_iphone_name']
    h.IGNORE_WORDS_FOR_COLOR = config['parser']['color_ignore'].lower().split('\n')


# Чтение списка разрешенных названий моделей для добавления в БД
def load_allowed_model_names_list_for_base():
    with open(h.PATH_LIST_MODEL_NAMES_BASE, 'r', encoding='UTF-8') as f:
        h.ALLOWED_MODEL_NAMES_LIST_FOR_BASE = f.read().splitlines()


# Чтение словаря исключений названий моделей
def load_exceptions_model_names():
    with open(h.EXCEPT_MODEL_NAMES_PATH, 'r', encoding='UTF-8') as f:
        for line in f:
            res = re.findall(r"\[.+?]", line)
            # Отсечь кривые записи
            if len(res) != 2:
                continue
            # Добавить в словарь
            h.EXCEPT_MODEL_NAMES_DICT[res[0].replace('[', '').replace(']', '')] = \
                res[1].replace('[', '').replace(']', '')


if __name__ == '__main__':
    time_start = time.time()
    load_allowed_model_names_list_for_base()
    load_exceptions_model_names()
    read_config()

    parser = CitilinkParse()
    parser.run_catalog('https://www.citilink.ru/catalog/mobile/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

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

logger = h.logging.getLogger('mtsparse')


# Загрузить данные с csv, чтобы не парсить сайт
def load_result_from_csv():
    pr_result_list = []
    with open(h.CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_result_list.append(h.ParseResult(
                shop=row['Магазин'],
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                price=int(row['Цена']),
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                rating=float(row['Рейтинг']),
                num_rating=int(row['Кол-во отзывов']),
                product_code=row['Код продукта'],
            ))

    return pr_result_list


# Парсинг названия модели (получить название модели, цвет и ROM)
def mts_parse_model_name(name):
    # Защита от неправильных названий
    if len(name.split()) < 3:
        return "error", "error", "error", 0, 0
    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)
    # Понижение регистра
    name = str.lower(name)
    name = name.replace('dual sim', '').replace('lte', '')
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
    # Получить название бренда
    brand_name = name.split()[0]
    # Удалить лишние слова в названии модели
    model_name = name.replace(ram_rom, '').replace(color, '').replace(brand_name, '').replace(year, '').\
        replace(samsung_code, '').replace('  ', ' ').strip()

    return brand_name, model_name, color, ram, rom


class MTSParse:

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
        self.domain = "https://www.shop.mts.ru"
        self.shop = "мтс"
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.current_city = self.config.defaults()['current_city']
        self.wait_between_pages_sec = int(self.config.defaults()['wait_between_pages_sec'])

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

        # TODO: доделать обертку try-except
        ActionChains(self.driver).move_to_element(elem).click().perform()
        return True

    # Алгоритм выбора города для всех возможных ситуаций на странице каталога
    def __wd_city_selection_catalog(self):
        city = self.__wd_find_elem_with_timeout(By.XPATH, "//span[@class='current-region__text']")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (str.lower(self.current_city) in str.lower(city.text)):
            print("Неверный город")

            # Клик по городу
            if not self.__wd_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            print("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "default-regions__item")
            if city_list:
                for item in city_list:
                    if str.lower(self.current_city) in str.lower(item.text):
                        time.sleep(1.5)
                        return self.__wd_click_elem(item)
            else:
                logger.warning("Нет списка городов, попробую вбить вручную")

            logger.warning("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='select-region-form__fieldset "
                                                                    "input-group__fieldset']")
            if not input_city:
                logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            ActionChains(self.driver).move_to_element(input_city).click().perform()

            # Ввод названия города по буквам
            for char in self.current_city:
                self.__wd_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//li[@class='list-results__item']")
            if not input_city_item:
                logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_click_elem(input_city_item):
                logger.error("Не могу нажать на выбранный город")
                return False

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "product-price__current"):
            return False

        # Ожидание прогрузки пагинации
        # if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "pagination"):
        #     return False
        # print('Пагинация прогрузилась')

        print("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Скролл вниз для прогрузки товаров на странице
    def __wd_mts_scroll_down(self):
        for i in range(14):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.3)

        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
            return False

        return True

    def __wd_mts_close_modal(self):
        print("Попытка закрыть сраное окно")
        modal = self.__wd_find_elem(By.XPATH, "//iframe[@class='flocktory-widget']")

        if modal:
            print("Сраное окно детектед")
            close_button = self.__wd_find_elem(By.XPATH, "//button[@class='close']")
            if close_button:
                print("Кнопка закрытия сраного окна детектед")
                self.__wd_click_elem(close_button)
        print("Конец попытки")

    # Запуск браузера, загрузка начальной страницы каталога, выбор города
    def __wd_open_browser_catalog(self, url):
        self.driver.get(url)

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

        # Ждем, пока не прогрузится страница
        if not self.__wd_mts_scroll_down():
            logger.error("Не удалось прогрузить страницу после скролла в __wd_open_browser (3)")
            return False

        time.sleep(2)

        return True

    # Запуск браузера, загрузка начальной страницы продукта, выбор города
    def __wd_open_browser_product(self, url):
        pass

    # Получить текущий код страницы
    def __wd_get_cur_page(self):
        return self.driver.page_source

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):
        self.cur_page += 1

        # Поиск следующей кнопки страницы
        num_page_elem = self.__wd_find_elem(By.XPATH,
                                            f"//div[contains(@class, 'pagination__page')]/a[text()='{self.cur_page}']")
        if not num_page_elem:
            # num_last_page_elem = self.__wd_find_elem(By.XPATH, "")
            # if num_last_page_elem and self.cur_page + 1 ==
            logger.info("Достигнут конец каталога")
            return False

        # Клик - переход на следующую страницу
        if not self.__wd_click_elem(num_page_elem):
            logger.error("Не могу кликнуть на страницу в __wd_next_page")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
            return False

        # Специальная задержка между переключениями страниц для имитации юзера
        time.sleep(self.wait_between_pages_sec)

        # Особенность ДНС - при переключении страницы иногда не меняется контент. Если так - обновляем страницу
        # try:
        #     self.wait.until_not(ec.presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
        #         self.pr_result_list[-5].url.replace(self.domain, '')))))
        # except se.TimeoutException:
        #     logger.error("TimeoutException в __wd_next_page, обновляю страницу")
        #     self.driver.refresh()

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
            return False

        # Скролл вниз и ожидание прогрузки страницы
        if not self.__wd_mts_scroll_down():
            logger.error("Не удалось прогрузить страницу после скролла в __wd_next_page (1)")
            return False

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
        self.category = soup.select('li.breadcrumbs__item')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = str.lower(self.category[-1].text.replace(' ', '').replace('\n', ''))

        # Контейнер с элементами
        container = soup.select('div.card-product-wrapper.card-product-wrapper--catalog')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):

        # Название модели
        model_name = block.select_one('div.card-product-description__name')
        if not model_name:
            logger.warning("No model name and URL")
            return
        else:
            model_name = model_name.text.replace('\n', '').strip()

        # URL
        url = block.select_one('a.card-product-description__heading')
        if not url:
            logger.warning("No URL")
            return
        else:
            url = self.domain + url.get('href')

        # Ссылка на изображение товара
        img_url = block.select_one('img.gallery__img')
        if not img_url:
            logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')

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

        # Цена, ветвление: 2 вида акций, поиск по тегам
        cur_price = block.select_one('span.product-price__current')
        if not cur_price:
            logger.warning("No price")
            return
        else:
            cur_price = int(re.findall(r'\d+', cur_price.text.replace(' ', ''))[0])

        promo_code = block.select('div.action-product-item.promo-action')
        if promo_code:
            for item in promo_code:
                if 'промокод' in item.text:
                    print('Нашел промокод "{}", применяю'.format(item.text))
                    promo_code = re.findall(r'\d+', item.text.replace(' ', ''))
                    promo_code = int(promo_code[0]) if promo_code else 0
                    cur_price -= promo_code
                    break

        # Парсинг названия модели
        brand_name, model_name, color, ram, rom = mts_parse_model_name(model_name)

        if not brand_name or not model_name or not color:
            logger.warning("No brand name, model name or color")
            return

        # Добавление полученных результатов в коллекцию
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=self.category.lower(),
            brand_name=brand_name.lower(),
            model_name=model_name.lower(),
            color=color.lower(),
            price=cur_price,
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
        with open(h.CSV_PATH_RAW + "mts.csv", 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS)
            for item in self.pr_result_list:
                writer.writerow(item)

    # Загрузить данные с csv, чтобы не парсить сайт
    def __load_result_in_csv(self):
        with open(h.CSV_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.pr_result_list.append(h.ParseResult(
                    shop=row['Магазин'],
                    category=row['Категория'],
                    brand_name=row['Бренд'],
                    model_name=row['Модель'],
                    color=row['Цвет'],
                    price=int(row['Цена']),
                    ram=int(row['RAM']),
                    rom=int(row['ROM']),
                    img_url=row['Ссылка на изображение'],
                    url=row['Ссылка'],
                    rating=float(row['Рейтинг']),
                    num_rating=int(row['Кол-во отзывов']),
                    product_code=row['Код продукта'],
                ))

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
        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return None

        html = self.__wd_get_cur_page()
        self.__parse_product_page(html, url)
        self.__wd_close_browser()
        self.__save_result()
        return self.pr_result_list


models = ('Apple iPhone 7 32 GB Black (MN8X2RU/A)',
          'Alcatel 1 5033D 8Gb Black',
          'Apple iPhone XR 64Gb White (Белый)',
          'Apple iPhone 11 Pro 256Gb Серый космос',
          'Huawei P30 Pro 8/256 Gb Breathing crystal',
          'Apple iPhone SE 2020 128Gb White',
          'Apple iPhone 12 256Gb (PRODUCT)Red',
          'Apple iPhone 11 (new) 64Gb Белый',
          'Huawei Y6 2019 2/32Gb Black',
          'Bright&Quick 2400L Voice 20 Dual sim Black/Red',
          'teXet TM-D205 Dual sim Black-red',
          'Huawei Nova 5T 6/128Gb Midsummer Purple',
          'Samsung N770 Galaxy Note10 Lite 6/128Gb Aura',
          'Nokia 105 2019 Dual sim Blue',
          'OPPO A52 4/64Gb White',
          'Nokia 5310 (2020) White -Red',
          'Irbis SF08 Dual sim Red')


if __name__ == '__main__':
    time_start = time.time()

    parser = MTSParse()
    result_list = parser.run_catalog(
        #"https://shop.mts.ru/catalog/smartfony/")
        "https://shop.mts.ru/catalog/smartfony/?id=62427_233815")

    # result_list = load_result_from_csv()
    # check = checker.Checker(result_list)
    # check.run()

    # bot = bot.Bot()
    # bot.run()
    print(f"Время выполнения: {time.time() - time_start} сек")

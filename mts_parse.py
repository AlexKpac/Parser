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
        self.shop = "mts"
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
            logger.error("No model name and URL")
            model_name = "error"
        else:
            model_name = model_name.text.replace('\n', '').strip()

        # URL
        url = block.select_one('a.card-product-description__heading')
        if not url:
            logger.error("No URL")
            url = "error"
        else:
            url = self.domain + url.get('href')

        # Ссылка на изображение товара
        img_url = block.select_one('img.gallery__img')
        if not img_url:
            logger.error("No img url")
            img_url = "error"
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
            logger.error("No price")
            cur_price = 0
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
        brand_name, model_name, color, ram, rom = mts_parse_model_name(model_name) \
            if model_name != "error" \
            else ("error", "error", "error", 0, 0)

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
        with open(h.CSV_PATH, 'w', newline='') as f:
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

        # self.__wd_close_browser()
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

models1 = ('Alcatel 1 5033D 8Gb Blue',
           'Alcatel 1 5033D 8Gb Black',
           'Apple iPhone 7 32GB Gold (MN902RU/A)',
           'Apple iPhone 7 32GB Silver (MN8Y2RU/A)',
           'Apple iPhone 7 32GB Black (MN8X2RU/A)',
           'Apple iPhone 7 128GB Rose Gold (MN952RU/A)',
           'Apple iPhone 7 128GB Gold (MN942RU/A)',
           'Apple iPhone 7 128GB Silver (MN932RU/A)',
           'Apple iPhone 7 128GB Black (MN922RU/A)',
           'Apple iPhone 7 Plus 32GB Rose Gold (MNQQ2RU/A)',
           'Alcatel 1A 5002F 1/16Gb Pine Green',
           'Alcatel 1 5033D 8Gb Gold',
           'Alcatel OneTouch 2053D Dual sim Black',
           'Alcatel OneTouch 2053D Dual sim White',
           'МТС Smart Line 1/8Gb Black',
           'Alcatel 2019G Grey',
           'Alcatel 2019G Silver',
           'Alcatel 1A 5002F 1/16Gb Prime Black',
           'Apple iPhone 7 32GB Rose Gold (MN912RU/A)',
           'Alcatel 1V (2020) 5007U 2/32Gb Prime Black',
           'Apple iPhone 11 128Gb Черный',
           'Apple iPhone XR 128Gb Black (Черный)',
           'Apple iPhone XR 64Gb White (Белый)',
           'Apple iPhone XR 64Gb Yellow (Жёлтый)',
           'Apple iPhone XR 64Gb Red (Красный)',
           'Apple iPhone XR 64Gb Blue (Синий)',
           'Apple iPhone XR 64Gb Coral (Коралловый)',
           'Apple iPhone XR 128Gb White (Белый)',
           'Apple iPhone XR 128Gb Yellow (Жёлтый)',
           'Apple iPhone XR 128Gb Red (Красный)',
           'Apple iPhone XR 128Gb Blue (Синий)',
           'Apple iPhone XR 128Gb Coral (Коралловый)',
           'Apple iPhone 11 64Gb Черный',
           'Apple iPhone 11 64Gb Желтый',
           'Apple iPhone 11 64Gb Зеленый',
           'Apple iPhone 11 64Gb Фиолетовый',
           'Apple iPhone 11 64Gb Красный',
           'Apple iPhone 11 128Gb Белый',
           'Apple iPhone 11 128Gb Зеленый',
           'Apple iPhone 11 128Gb Желтый',
           'Apple iPhone 11 Pro 64Gb Тёмно-зелёный',
           'Apple iPhone 11 Pro Max 256Gb Серый космос',
           'Apple iPhone 11 256Gb Желтый',
           'Apple iPhone 11 256Gb Фиолетовый',
           'Apple iPhone 11 256Gb Красный',
           'Apple iPhone 11 Pro 64Gb Серый космос',
           'Apple iPhone 11 Pro 64Gb Серебристый',
           'Apple iPhone 11 Pro 64Gb Золотой',
           'Apple iPhone 11 Pro 256Gb Серый космос',
           'Apple iPhone 11 Pro 256Gb Серебристый',
           'Apple iPhone 11 Pro 256Gb Темно-зеленый',
           'Apple iPhone 11 Pro 256Gb Золотой',
           'Apple iPhone 11 Pro 512Gb Серебристый',
           'Apple iPhone 11 Pro 512Gb Золотой',
           'Apple iPhone 11 Pro Max 256Gb Тёмно-зелёный',
           'Apple iPhone 11 Pro Max 64Gb Серый космос',
           'Apple iPhone 11 Pro Max 64Gb Серебристый',
           'Apple iPhone 11 Pro Max 64Gb Золотой',
           'Apple iPhone 11 Pro Max 256Gb Серебристый',
           'Apple iPhone 11 Pro Max 256Gb Золотой',
           'Apple iPhone SE 2020 64Gb Red',
           'Apple iPhone SE 2020 128Gb Black',
           'Apple iPhone SE 2020 128Gb White',
           'Apple iPhone SE 2020 128Gb Red',
           'Apple iPhone SE 2020 256Gb Black',
           'Apple iPhone SE 2020 256Gb White',
           'Apple iPhone SE 2020 256Gb Red',
           'Apple iPhone SE 2020 64Gb White',
           'Apple iPhone 12 64Gb Чёрный',
           'Apple iPhone 12 64Gb Белый',
           'Apple iPhone 12 256Gb (PRODUCT)Red',
           'Apple iPhone 12 256Gb Зеленый',
           'Apple iPhone 12 64Gb (PRODUCT)Red',
           'Apple iPhone 12 64Gb Синий',
           'Apple iPhone 12 128Gb Чёрный',
           'Apple iPhone 12 128Gb Белый',
           'Apple iPhone 12 128Gb Зеленый',
           'Apple iPhone 12 128Gb (PRODUCT)Red',
           'Apple iPhone 12 128Gb Синий',
           'Apple iPhone 12 256Gb Чёрный',
           'Apple iPhone XR (new) 128Gb Black (Черный)',
           'Apple iPhone XR (new) 128Gb White (Белый)',
           'Apple iPhone SE 2020 (new) 128Gb Black',
           'Apple iPhone XR (new) 64Gb Black (Черный)',
           'Apple iPhone XR (new) 64Gb White (Белый)',
           'Apple iPhone XR (new) 64Gb Red (Красный)',
           'Apple iPhone XR (new) 64Gb Blue (Синий)',
           'Apple iPhone XR (new) 64Gb Coral (Коралловый)',
           'Apple iPhone 12 256Gb Синий',
           'Apple iPhone XR (new) 128Gb Yellow (Жёлтый)',
           'Apple iPhone 11 (new) 128Gb Белый',
           'Apple iPhone XR (new) 128Gb Red (Красный)',
           'Apple iPhone XR (new) 128Gb Blue (Синий)',
           'Apple iPhone 11 (new) 64Gb Черный',
           'Apple iPhone 11 (new) 64Gb Белый',
           'Apple iPhone 11 (new) 64Gb Фиолетовый',
           'Apple iPhone 11 (new) 64Gb Зеленый',
           'Apple iPhone 11 (new) 128Gb Черный',
           'Apple iPhone SE 2020 (new) 64Gb White',
           'Apple iPhone 11 (new) 64Gb Желтый',
           'Huawei P30 Pro 8/256Gb Breathing crystal',
           'Huawei Y5 2019 2/32Gb Black',
           'Huawei Y6 2019 2/32Gb Black',
           'Huawei Y6 2019 2/32Gb Blue',
           'Huawei Y6 2019 2/32Gb Brown',
           'Huawei P30 Pro 8/256Gb Aurora',
           'Huawei P30 6/128Gb Aurora',
           'Huawei P30 Lite 4/128Gb Black',
           'Huawei P30 Lite 4/128Gb Blue',
           'Huawei Y5 2019 2/32Gb Blue',
           'Huawei Y5 2019 2/32Gb Brown',
           'Huawei P Smart Z 4/64 Gb Green',
           'Huawei P Smart Z 4/64 Gb Blue',
           'Bright&Quick 2400L Voice 20 Dual sim Black/Red',
           'Huawei P Smart Z 4/64 Gb Black',
           'Huawei Y6 2019 2/32Gb Modern Black',
           'Bright&Quick BQ-4028 UP Black',
           'Apple iPhone SE 2020 (new) 64Gb Black',
           'Apple iPhone 11 (new) 256Gb Зеленый',
           'Apple iPhone 11 (new) 256Gb Фиолетовый',
           'Huawei P30 Lite 6/256Gb Blue',
           'Huawei P30 Lite 6/256Gb Black',
           'Huawei P40 Pro 8/256Gb Black',
           'Huawei P40 8/128Gb Black',
           'Huawei Y7 2019 4/64Gb Purple',
           'Huawei Y5 Lite 1/16Gb Brown',
           'Huawei P30 Pro 8/256Gb Black',
           'Huawei Nova 5T 6/128Gb Midsummer Purple',
           'Huawei Y6s 3/64Gb Starry Black',
           'Huawei Y6s 3/64Gb Orchid Blue',
           'Huawei P30 Pro 8/256Gb Lavender',
           'Huawei P40 Lite 6/128Gb Midnight Black',
           'Huawei P40 Lite 6/128Gb Crush Green',
           'Huawei P40 Lite E 4/64Gb Midnight Black',
           'Huawei P40 8/128Gb Silver Frost',
           'Huawei P40 Pro 8/256Gb Silver Frost',
           'Huawei Y5p 2/32Gb Phantom Blue',
           'Huawei Y5p 2/32Gb Mint Green',
           'Huawei Y8p 4/128Gb Midnight Black',
           'Huawei P40 Lite E (NFC) 4/64 Gb Aurora Blue',
           'Samsung Galaxy G975 S10 Plus 8/128Gb Оникс',
           'Samsung A515 Galaxy A51 4/64Gb Black',
           'Samsung Galaxy S10 G973 8/128Gb Оникс',
           'Samsung N970 Galaxy Note 10 8/256Gb Красный',
           'Samsung G973 Galaxy S10 8/128Gb Перламутр',
           'Samsung G975 Galaxy S10 Plus 8/128Gb Аквамарин',
           'Samsung A105 Galaxy A10 2/32Gb Black',
           'Samsung A105 Galaxy A10 2/32Gb Blue',
           'Samsung A105 Galaxy A10 2/32Gb Red',
           'Samsung A405 Galaxy A40 4/64Gb Black',
           'Samsung A405 Galaxy A40 4/64Gb Blue',
           'Samsung J260 Galaxy J2 Core 1/8Gb Black',
           'Samsung Galaxy G975 S10 Plus 8/128Gb Red',
           'Samsung A207 Galaxy A20s 3/32Gb Blue',
           'Samsung A207 Galaxy A20s 3/32Gb Black',
           'Samsung G770 Galaxy S10 Lite 6/128Gb White',
           'Samsung A015 Galaxy A01 2/16Gb Black',
           'Samsung A015 Galaxy A01 2/16Gb Blue',
           'Samsung A015 Galaxy A01 2/16Gb Red',
           'Samsung A515 Galaxy A51 4/64Gb Red',
           'Samsung A315 Galaxy A31 4/128Gb Black',
           'Samsung F700 Galaxy Z Flip 8/256Gb Black',
           'Samsung G980 Galaxy S20 8/128Gb Blue',
           'Samsung F700 Galaxy Z Flip 8/256Gb Purple',
           'Samsung A715 Galaxy A71 6/128Gb Silver',
           'Samsung A715 Galaxy A71 6/128Gb Black',
           'Samsung G985 Galaxy S20+ 8/128Gb Red',
           'Samsung G770 Galaxy S10 Lite 6/128Gb Black',
           'Samsung G770 Galaxy S10 Lite 6/128Gb Blue',
           'Samsung N770 Galaxy Note10 Lite 6/128Gb Black',
           'Samsung N770 Galaxy Note10 Lite 6/128Gb Aura',
           'Samsung N770 Galaxy Note10 Lite 6/128Gb Red',
           'Samsung G980 Galaxy S20 8/128Gb Grey',
           'Samsung G980 Galaxy S20 8/128Gb Red',
           'Samsung G985 Galaxy S20+ 8/128Gb Black',
           'Samsung G985 Galaxy S20+ 8/128Gb Grey',
           'Samsung A515 Galaxy A51 6/128Gb White',
           'Samsung G988 Galaxy S20 Ultra 12/128Gb Black',
           'Samsung G988 Galaxy S20 Ultra 12/128Gb Grey',
           'Samsung A415 Galaxy A41 4/64Gb White',
           'Samsung A217 Galaxy A21s 3/32Gb Black',
           'teXet TM-D205 Dual sim Black-red',
           'teXet TM-208 Dual sim Black/Red',
           'teXet TM-208 Dual sim Black-Yellow',
           'Samsung A217 Galaxy A21s 4/64Gb Black',
           'Samsung A217 Galaxy A21s 4/64Gb Red',
           'Samsung A217 Galaxy A21s 4/64Gb Blue',
           'Samsung A217 Galaxy A21s 3/32Gb Red',
           'Samsung A217 Galaxy A21s 3/32Gb Blue',
           'teXet TM-D206 Black-Red',
           'Samsung A115 Galaxy A11 2/32 Gb Black',
           'Samsung A115 Galaxy A11 2/32 Gb Red',
           'Samsung A115 Galaxy A11 2/32 Gb White',
           'Samsung A013 Galaxy A01 Core 1/16GB Black',
           'Samsung A013 Galaxy A01 Core 1/16Gb Red',
           'Samsung A013 Galaxy A01 Core 1/16Gb Blue',
           'Samsung N980 Galaxy Note 20 8/256 Gb grey',
           'Samsung N980 Galaxy Note 20 8/256 Gb mint',
           'Samsung N980 Galaxy Note 20 8/256 Gb bronze',
           'Samsung N985 Galaxy Note 20 Ultra 8/256 Gb black',
           'Xiaomi Redmi Note 8 Pro 6/64GB Blue',
           'Xiaomi Redmi Note 8 Pro 6/128GB Grey',
           'Philips Xenium E169 Dual sim Red',
           'Philips E109 Dual sim Red',
           'Philips Xenium E169 Dual sim Grey',
           'Xiaomi Redmi Note 8 Pro 6/64GB Grey',
           'Xiaomi Redmi Note 8 Pro 6/64GB Green',
           'Xiaomi Redmi Note 8 Pro 6/128GB Blue',
           'Xiaomi Redmi Note 8 Pro 6/128GB Green',
           'Xiaomi Redmi Note 8T 4/64Gb Starscape Blue',
           'Xiaomi Redmi Note 8 Pro 6/128GB White',
           'Xiaomi Redmi Note 8T 3/32Gb Moonshadow Grey',
           'Xiaomi Redmi Note 8T 3/32Gb Starscape Blue',
           'Xiaomi Redmi Note 8T 4/64Gb Moonshadow Grey',
           'Philips Xenium E255 Dual sim Blue',
           'Philips Xenium E580 Dual sim Black',
           'Philips Xenium E182 Dual sim Blue',
           'Philips E109 Dual sim Black',
           'Philips Xenium E255 Dual sim Red',
           'Xiaomi Mi Note 10 Pro 8/256Gb Aurora Green',
           'Xiaomi Redmi Note 9 4/128Gb Midnight Grey',
           'Xiaomi Mi 10 8/256Gb Coral Green',
           'Xiaomi Redmi Note 9 Pro 6/128Gb Interstellar Grey',
           'Xiaomi Redmi 9C 2/32Gb Midnight Gray',
           'Xiaomi Redmi Note 9 3/64Gb Midnight Grey',
           'Xiaomi Redmi Note 9 3/64Gb Polar White',
           'Xiaomi Redmi Note 9 3/64Gb Forest Green',
           'Xiaomi Redmi Note 9 4/128Gb Forest Green',
           'Xiaomi Redmi 9 4/64Gb purple',
           'Xiaomi Redmi 9 4/64Gb green',
           'Xiaomi Redmi 9 4/64Gb grey',
           'Xiaomi Redmi 9 3/32Gb Purple',
           'Xiaomi Redmi Note 9 Pro 6/128Gb Glacier White',
           'Xiaomi Redmi 9C 3/64Gb Twilight Blue',
           'Xiaomi Redmi 9C 3/64Gb Sunrise Orange',
           'Xiaomi Redmi 9C 3/64Gb Midnight Gray',
           'Xiaomi Redmi 9C 2/32Gb Sunrise Orange',
           'Xiaomi Redmi 9C 2/32Gb Twilight Blue',
           'Xiaomi Redmi 9A 2/32Gb Peacock Green',
           'Xiaomi Redmi 9A 2/32Gb Sky Blue',
           'Nokia 2720 Dual sim Red',
           'Nokia 2720 Dual sim Black',
           'Nokia 3310 Dual sim grey',
           'Nokia 3310 Dual sim blue',
           'Nokia 3310 Dual sim yellow',
           'Nokia 8110 Dual sim Black',
           'Nokia 8110 Dual sim Yellow',
           'Nokia 230 Dual sim Blue',
           'Nokia 105 2019 Dual sim Black',
           'Nokia 105 2019 Dual sim Blue',
           'Nokia 105 2019 Dual sim Pink',
           'Nokia 105 2019 Black',
           'Nokia 105 2019 Blue',
           'Nokia 216 Dual Sim Black',
           'Xiaomi Redmi Note 8 Pro 6/128GB Orange',
           'Nokia 220 2019 LTE Dual sim Black',
           'Nokia 220 2019 LTE Dual sim Blue',
           'Nokia 800 LTE Dual sim Black',
           'Nokia 105 (без ЗУ) black',
           'Nokia 105 (без ЗУ) blue',
           'Honor 9X 4/128Gb Black',
           'Honor 20 LITE 4/128Gb Pearl White',
           'Honor 10 Lite 3/64 Gb Sapphire Blue',
           'Honor 10i 4/128Gb Phantom Blue',
           'Honor 9X 4/128Gb Blue',
           'Honor 9X Premium 6/128Gb Black',
           'Honor 9X Premium 6/128Gb Blue',
           'Honor 20 LITE 4/128Gb Midnight Black',
           'Honor 20 LITE 4/128Gb Peacock Blue',
           'Honor 7S 1/16Gb Black',
           'Honor 9X 4/128Gb Sapphire Green',
           'Honor 7S 1/16Gb Blue',
           'Honor 7S 1/16Gb Gold',
           'Honor 8A Prime 3/64Gb Midnight Black',
           'Honor 8A Prime 3/64Gb Navy Blue',
           'Honor 8A Prime 3/64Gb Emerald Green',
           'Honor 9S 2/32Gb Blue',
           'Honor 9S 2/32Gb Red',
           'Nokia 5310 (2020) White -Red',
           'Honor 10 Lite 3/64 Gb Black',
           'Honor 10X Lite 4/128Gb Midnight Black',
           'Honor 30I 4/128Gb Black',
           'Honor 30I 4/128Gb Green/Blue',
           'Honor 9C 4/64Gb Blue',
           'Honor 10X Lite 4/128Gb Emerald Green',
           'Honor 30 Premium 8/256Gb Midnight Black',
           'Honor 7A Prime 2/32Gb Green',
           'Honor 8S Prime 3/64Gb Black',
           'Honor 8S Prime 3/64Gb Blue',
           'Honor 8S Prime 3/64Gb Green',
           'Honor 9C 4/64Gb Black',
           'Honor 9A 3/64Gb Midnight Black',
           'Honor 9A 3/64Gb Phantom Blue',
           'Honor 9A 3/64Gb Ice Green',
           'Honor 9S 2/32Gb Black',
           'Honor 30 8/128Gb Emerald Green',
           'Honor 30 Pro+ 8/256Gb Titanium Silver',
           'Honor 30 Premium 8/256Gb Titanium Silver',
           'Honor 7A Prime 2/32Gb Black',
           'Honor 30S 6/128Gb Black',
           'Vivo Y91C 2/32Gb Fusion Black',
           'Irbis SF32 Dual sim Black',
           'Irbis SF08 Dual sim Red',
           'Irbis SF71 Dual sim Red',
           'Vivo Y17 4/64 Gb Blue',
           'Vivo Y17 4/64 Gb Purple',
           'Vivo V17 Neo 6/128 Gb Diamond Black',
           'Vivo V17 Neo 6/128 Gb Skyline Blue',
           'Vivo Y12 3/64Gb Aqua Blue',
           'Vivo Y12 3/64Gb Burgundy Red',
           'Vivo Y11 3/32Gb Blue',
           'Vivo Y11 3/32Gb Red',
           'Vivo V17 8/128Gb Fancy Sky',
           'Vivo V20 SE 8/128Gb Oxygen Blue',
           'Vivo Y30 4/64 GB Black',
           'Vivo Y30 4/64 Gb Blue',
           'Honor 20E 4/64Gb Blue',
           'Honor 20E 4/64Gb Black',
           'Vivo Y1s 2/32Gb Olive Black',
           'Vivo Y1s 2/32Gb Ripple Blue',
           'Realme 6i 4/128Gb White',
           'OPPO A1k 2/32 Gb Black',
           'OPPO Reno 6/256 Gb Black',
           'OPPO A5 2020 3/64Gb Black',
           'OPPO A5 2020 3/64Gb White',
           'OPPO Reno 2Z 8/128Gb Luminous Black',
           'OPPO Reno 2 8/256Gb Luminos Black',
           'Irbis SF32 Dual sim Black/Red',
           'Irbis SF32 Dual sim Black/Blue',
           'Irbis SF65 Dual sim Black',
           'OPPO Reno3 8/128Gb Blue',
           'Realme 6i 4/128Gb Green',
           'Realme 6 8/128Gb Comet Blue',
           'Realme 6 8/128Gb Comet White',
           'Realme 6 4/128Gb Comet Blue',
           'Realme 6 4/128Gb Comet White',
           'OPPO A52 4/64Gb Black',
           'OPPO A52 4/64Gb White',
           'Realme C3 3/32Gb (NFC) Red',
           'Realme C3 3/32Gb (NFC) Blue',
           'Palm PVG100 3/32Gb Titanium',
           'Realme 6s 6/128Gb Lunar White',
           'Realme 6s 6/128Gb Eclipse Black',
           'Realme 6 Pro 8/128Gb Red',
           'Realme 6 Pro 8/128Gb Blue',
           'Realme C3 3/64Gb Grey',
           'OPPO Reno4 Lite 8/128Gb Black',
           'OPPO A12 3/32Gb Blue',
           'INOI 241 Dual sim Grey',
           'INOI 241 Dual sim Dark Blue',
           'INOI 241 Dual sim Dark Grey',
           'OPPO Reno4 Lite 8/128Gb Blue',
           'OPPO Reno4 Pro 12/256Gb Blue',
           'OPPO Reno4 Pro 12/256Gb Black',
           'Poco X3 6/128Gb Cobalt Blue',
           'Poco X3 6/128Gb Shadow Gray',
           'OPPO A53 4/128Gb Black',)

if __name__ == '__main__':
    time_start = time.time()

    # for itemm in models:
    #     a, b, c, d, e = mts_parse_model_name(itemm)
    #     print('raw = {}\nbrand = {}\nmodel = {}\ncolor = {}\nram = {} / rom = {}\n-----------------------'.format(itemm, a, b, c, d, e))
    parser = MTSParse()
    result_list = parser.run_catalog(
        "https://shop.mts.ru/catalog/smartfony/")

    # result_list = load_result_from_csv()
    # check = checker.Checker(result_list)
    # check.run()

    # bot = bot.Bot()
    # bot.run()
    print(f"Время выполнения: {time.time() - time_start} сек")

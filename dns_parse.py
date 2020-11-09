import time
import re
import csv
import datetime
import configparser

import bs4
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.expected_conditions import presence_of_element_located

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import bot
import header as h
import checker

logger = h.logging.getLogger('dnsparse')


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
def dns_parse_model_name(brand, name):
    # Понижение регистра
    name = name.lower()
    brand = brand.lower()
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
    rom = re.findall(r'\d+', rom)[0]
    # Удалить из строки модели цвет, название бренда и слово "смартфон"
    name = name.replace(color, '').replace(brand, '').replace('смартфон', '')
    # Удалить лишние пробелы
    name = ' '.join(name.split())

    return name, color, int(rom)


# Парсинг характеристик (получить RAM)
def dns_parse_specifications(specifications):
    # Понижение регистра
    specifications = specifications.lower()
    # Получение значения ram из строки характеристик
    ram = re.findall(r'\d+\sгб', specifications)
    # Удалить из строки ROM всё, кроме цифр, если эта строка не пустая, иначе 0
    ram = re.findall(r'\d+', ram[0])[0] if ram else 0

    return int(ram)


class DNSParse:

    def __init__(self):
        options = Options()
        options.add_argument("window-size=1920,1080")
        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 30)
        self.pr_result_list = []
        self.cur_page = 1
        # Данные магазина
        self.domain = "https://www.dns-shop.ru"
        self.shop = "dns"
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
            result = self.wait.until(presence_of_element_located((by, elem)))
            return result
        except se.TimeoutException:
            return None

    # Поиск всех элементов с таймаутом
    def __wd_find_all_elems_with_timeout(self, by, elem):
        pass

    # Отправка клавиши в элемент через ActionChains
    def __wd_send_keys(self, elem, keys):
        pass
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

        for i in range(3):
            try:
                elem.click()
                return True
            except se.ElementClickInterceptedException:
                logger.warning("Не могу кликнуть на элемент, пробую еще")
                time.sleep(1.5)

        return False

    # Алгоритм выбора города для всех возможных ситуаций на странице каталога
    def __wd_city_selection_catalog(self):
        modal_confirm_city = self.__wd_find_elem(By.XPATH, "//div[@class='dropdown-city']")

        # Если нашел всплывающее окно с подтверждением города
        if modal_confirm_city:
            # Если сайт предлагает нужный город
            # if modal_confirm_city.text.find(h.CURRENT_CITY) != -1:
            if self.current_city.lower() in modal_confirm_city.text.lower():
                yes_button = self.__wd_find_elem(By.XPATH, "//div[@class='dropdown-city']/a[text()='Да']")
                if not yes_button:
                    logger.error("Не вижу кнопки ДА")
                    return False

                yes_button.click()
                # if not self.__wd_click_elem(yes_button):
                #     logger.error("Не смог нажать на кнопку ДА")
                #     return False
            # Иначе выбор другого
            else:
                other_button = self.__wd_find_elem(By.XPATH, "//div[@class='dropdown-city']/a[text()='Выбрать другой']")
                if not other_button:
                    logger.error("Не вижу кнопки ДРУГОЙ ГОРОД")
                    return False

                other_button.click()
                # if not self.__wd_click_elem(other_button):
                #     logger.error("Не могу нажать на кнопку ДРУГОЙ")
                #     return False

                # Ждем загрузки формы с выбором города и получаем input для ввода города
                input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='search-field']/"
                                                                        "input[@data-role='search-city']")
                if not input_city:
                    logger.error("Не могу найти поле для ввода города (1)")
                    return False

                # Отправка нужного города
                input_city.send_keys(self.current_city, Keys.ENTER)
                # ActionChains(self.driver).move_to_element(input_city).click().pause(1). \
                #     send_keys(h.CURRENT_CITY, Keys.ENTER).perform()

        # Если не нашел всплывающего окна с подтверждением города
        else:
            city_head = self.__wd_find_elem(By.XPATH, "//div[@class='w-choose-city-widget-label']")
            if not city_head:
                logger.error("Не могу найти элемент с текущим городом на странице")
                return False

            # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
            # if city_head.text.find(h.CURRENT_CITY) == -1:
            if not (self.current_city.lower() in city_head.text.lower()):
                city_head.click()
                # if not self.__wd_click_elem(city_head):
                #     logger.error("Не могу кликнуть по названию города для его смены")
                #     return False

                input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='search-field']/"
                                                                        "input[@data-role='search-city']")
                if not input_city:
                    logger.error("Не могу найти поле для ввода города (2)")
                    return False

                # Отправка нужного города
                input_city.send_keys(self.current_city, Keys.ENTER)
                # ActionChains(self.driver).move_to_element(input_city).click().pause(1). \
                #     send_keys(h.CURRENT_CITY, Keys.ENTER).perform()

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "product-min-price__current"):
            return False

        print("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

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

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

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
                                            f"//li[@class='pagination-widget__page ']/a[text()='{self.cur_page}']")
        if not num_page_elem:
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

        # Особенность ДНС - при переключении страницы иногда не меняется контент. Если так - обновляем страницу
        try:
            self.wait.until_not(presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                self.pr_result_list[-5].url.replace(self.domain, '')))))
        except se.TimeoutException:
            logger.error("TimeoutException в __wd_next_page, обновляю страницу")
            self.driver.refresh()

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
            return False

        # Специальная задержка между переключениями страниц для имитации юзера
        time.sleep(self.wait_between_pages_sec)
        return True

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html, url):
        soup = bs4.BeautifulSoup(html, 'lxml')

        product_block = soup.select_one("div#product-page")
        if not product_block:
            logger.error("NO PRODUCT BLOCK")
            return

        # Категория товара
        category = product_block.select_one("div.item-header > i[data-product-param=category]")
        if not category:
            logger.error("No category")
            category = "error"
        else:
            category = category.get('data-value')

        # Название модели
        model_name = product_block.select_one("h1.page-title.price-item-title")
        if not model_name:
            logger.error("No model name")
            model_name = "error"
        else:
            model_name = model_name.text

        # Название бренда
        brand_name = product_block.select_one("i[data-product-param=brand]")
        if not brand_name:
            logger.error("No brand name")
            brand_name = "error"
        else:
            brand_name = brand_name.get('data-value')

        # Ссылка на изображение товара
        img_url = product_block.select_one("div.img > a.lightbox-img")
        if not img_url:
            logger.error("No img url")
            img_url = "error"
        else:
            img_url = img_url.get('href')

        # Характеристики товара
        specifications = product_block.select_one("div.hidden.price-item-description")
        if not specifications:
            logger.error("No specifications")
            specifications = "error"
        else:
            specifications = specifications.text[specifications.text.find("[") + 1:specifications.text.find("]")]

        # Рейтинг товара
        rating = product_block.select_one("div.product-item-rating.rating")
        if not rating:
            rating = 0
        else:
            rating = float(rating.get('data-rating'))

        # На основании скольки отзывов построен рейтинг
        num_rating = product_block.select_one("span[itemprop=ratingCount]")
        if not num_rating:
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text)[0])

        # Код продукта
        product_code = product_block.select_one("div.price-item-code > span")
        if not product_code:
            logger.error("No product code")
            product_code = "error"
        else:
            product_code = product_code.text

        # Текущая цена
        cur_price = product_block.select_one("span.product-card-price__current")
        if not cur_price:
            logger.error("No cur price")
            cur_price = 0
        else:
            cur_price = int(re.findall(r'\d+', cur_price.text.replace(' ', ''))[0])

        # Парсинг полученных данных
        model_name, color, rom = dns_parse_model_name(brand_name, model_name) \
            if brand_name != "error" and model_name != "error" \
            else ("error", "error", 0)

        ram = dns_parse_specifications(specifications) if specifications != "error" else 0

        # Добавление полученных результатов в коллекцию
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=category.lower(),
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

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        soup = bs4.BeautifulSoup(html, 'lxml')

        # Категория (из хлебных крошек)
        self.category = soup.select_one('ol.breadcrumb-list > li.breadcrumb_last.breadcrumb-list__item')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = self.category.text.replace('\n', '')

        # Контейнер с элементами
        container = soup.select('div.catalog-item')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):

        # Название модели и URL
        model_name_url_block = block.select_one('div.product-info__title-link > a.ui-link')
        if not model_name_url_block:
            logger.error("No model name and URL")
            model_name = "error"
            url = "error"
        else:
            url = self.domain + model_name_url_block.get('href')
            model_name = model_name_url_block.text

        # Название бренда
        brand_name = block.select_one('i[data-product-param=brand]')
        if not brand_name:
            logger.error("No brand name")
            brand_name = "error"
        else:
            brand_name = brand_name.get('data-value')

        # Ссылка на изображение товара
        img_url = block.select_one('img')
        if not img_url:
            logger.error("No img url")
            img_url = "error"
        else:
            img_url = img_url.get('data-src')

        # Характеристики товара
        specifications = block.select_one('span.product-info__title-description')
        if not specifications:
            logger.error("No specifications")
            specifications = "error"
        else:
            specifications = specifications.text

        # Рейтинг товара
        rating = block.select_one('div.product-info__rating')
        if not rating:
            rating = 0
        else:
            rating = float(rating.get('data-rating'))

        # На основании скольки отзывов построен рейтинг
        num_rating = block.select_one('div.product-info__stat > a.product-info__opinions-count')
        if not num_rating:
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text)[0])

        # Код продукта
        product_code = block.select_one('div.product-info__code > span')
        if not product_code:
            logger.error("No product code")
            product_code = "error"
        else:
            product_code = product_code.text

        # Цена, ветвление: 2 вида акций, поиск по тегам
        cur_price = block.select_one('mark.product-min-price__min-price')

        # Если есть "акция"
        if cur_price:
            cur_price = int(re.findall(r'\d+', cur_price.text.replace(' ', ''))[0])
        # Если есть "выгода"
        else:
            cur_price = block.select_one('div.product-min-price__current')
            if not cur_price:
                logger.error("No current price")
                cur_price = 0
            else:
                cur_price = int(cur_price.text.replace('₽', '').replace(' ', ''))

        # Парсинг полученных данных
        model_name, color, rom = dns_parse_model_name(brand_name, model_name) \
            if brand_name != "error" and model_name != "error" \
            else ("error", "error", 0)

        ram = dns_parse_specifications(specifications) if specifications != "error" else 0

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
        # if not self.__wd_open_browser_catalog(url):
        #     logger.error("Open browser fail")
        #     self.__wd_close_browser()
        #     return
        #
        # if cur_page:
        #     self.cur_page = cur_page
        #
        # while True:
        #     html = self.__wd_get_cur_page()
        #     self.__parse_catalog_page(html)
        #     if not self.__wd_next_page():
        #         break

        self.__wd_close_browser()
        # self.__save_result()
        self.__load_result_in_csv()
        return self.pr_result_list

    # Запуск работы парсера для продукта
    def run_product(self, url):
        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return

        html = self.__wd_get_cur_page()
        self.__parse_product_page(html, url)
        self.__wd_close_browser()
        self.__save_result()
        return self.pr_result_list


models = ('4" Смартфон INOI 1 Lite 4 ГБ черный',
          '6.95" Смартфон Tecno Spark 5 Air 32 ГБ зеленый',
          '6.53" Смартфон Xiaomi Redmi 9C NFC 64 ГБ оранжевый',
          '6.5" Смартфон Samsung Galaxy A21s 32 ГБ красный',
          '7.6" Смартфон Samsung Galaxy Z Fold2 256 ГБ коричневый',
          '6.5" Смартфон realme 6 4/128 ГБ синий',
          '4.7" Смартфон Apple iPhone 7 32 Гб черный матовый')

if __name__ == '__main__':
    time_start = time.time()
    # parser = DNSParse()
    # result = parser.run_catalog(
    #      "https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
    result = load_result_from_csv()
    check = checker.Checker(result)
    check.run()
    # bot = bot.Bot()
    # bot.run()
    print(f"Время выполнения: {time.time() - time_start} сек")

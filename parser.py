import logging
import collections
import time
import re
import csv

import bs4
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('parser')

ParseResult = collections.namedtuple(
    'ParseResult',
    (
        'category',
        'brand_name',
        'model_name',
        'specifications',
        'price',
        'old_price',
        'discount',
        'url_img',
        'url',
        'rating',
        'num_rating',
        'product_code',
        'shop',
    ),
)
HEADERS = (
    'Категория',
    'Бренд',
    'Модель',
    'Характеристики',
    'Текущая цена',
    'Старая цена',
    'Скидка',
    'Ссылка на изображение',
    'Ссылка',
    'Рейтинг',
    'Кол-во отзывов',
    'Код продукта',
    'Магазин',
)
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
CURRENT_CITY = 'Новосибирск'
WAIT_BETWEEN_PAGES_SEC = 3


class Parser:

    def __init__(self):
        options = Options()
        # options.add_argument("window-size=1,1")
        self.driver = webdriver.Chrome(executable_path=WD_PATH, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.cur_page = 1
        self.result = []
        self.domain = "https://www.dns-shop.ru/"
        self.shop = "ДНС"

    # Поиск элемента с таймаутом
    def __find_elem_with_timeout(self, by, elem):
        try:
            result = self.wait.until(presence_of_element_located((by, elem)))
            return result
        except se.TimeoutException:
            return False

    # Алгоритм выбора города для всех возможных ситуаций
    def __city_selection(self):
        try:
            modal_city = self.driver.find_element_by_xpath("//div[@class='dropdown-city']")
            # Если нашел всплывающее окно с подтверждением города

            if modal_city.text.find(CURRENT_CITY) != -1:
                # Если сайт предлагает нужный город
                self.driver.find_element_by_xpath("//div[@class='dropdown-city']/a[text()='Да']").click()
            else:
                # Иначе выбор другого
                self.driver.find_element_by_xpath("//div[@class='dropdown-city']/a[text()='Выбрать другой']").click()
                # Ждем загрузки формы с выбором города и получаем input для ввода города
                input_city = self.wait.until(presence_of_element_located((By.XPATH, "//div[@class='search-field']/"
                                                                                    "input[@data-role='search-city']")))
                # Отправка нужного города
                input_city.send_keys(CURRENT_CITY, Keys.ENTER)

        except se.NoSuchElementException:
            # Если не нашел всплывающего окна с подтверждением города
            city_head = self.driver.find_element_by_xpath("//div[@class='w-choose-city-widget-label']")
            # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
            if city_head.text.find(CURRENT_CITY) == -1:
                city_head.click()
                input_city = self.wait.until(presence_of_element_located((By.XPATH, "//div[@class='search-field']/"
                                                                                    "input[@data-role='search-city']")))
                # Отправка нужного города
                input_city.send_keys(CURRENT_CITY, Keys.ENTER)

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html):
        # TODO: Реализовать парсинг страницы товара
        return

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        soup = bs4.BeautifulSoup(html, 'lxml')

        # Категория (из хлебных крошек)
        self.category = soup.select_one('ol.breadcrumb-list > li.breadcrumb_last.breadcrumb-list__item')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = self.category.text.split()

        # Контейнер с элементами
        container = soup.select('div.catalog-item')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):

        # НАЗВАНИЕ ТОВАРА, ХАРАКТЕРИСТИКИ, ФОТО, URL
        product_info_block = block.select_one('div.n-catalog-product__info')

        # Название модели и URL
        model_name_url_block = product_info_block.select_one('div.product-info__title-link > a.ui-link')
        if not model_name_url_block:
            logger.error("No model name and URL")

        url = self.domain + model_name_url_block.get('href')
        model_name = model_name_url_block.text

        # Название бренда
        brand_name = product_info_block.select_one('div.product-info__title > i.hidden')
        if not brand_name:
            logger.error("No brand name")
            brand_name = "error"
        else:
            brand_name = brand_name.get('data-value')

        # Ссылка на изображение товара
        img_url = product_info_block.select_one('img')
        if not img_url:
            logger.error("No img url")
            img_url = "error"
        else:
            img_url = img_url.get('data-src')

        # Характеристики товара
        specifications = product_info_block.select_one('span.product-info__title-description')
        if not specifications:
            logger.error("No specifications")
            specifications = "error"
        else:
            specifications = specifications.text

        # Рейтинг товара
        rating = product_info_block.select_one('div.product-info__rating')
        if not rating:
            logger.error("No rating")
            rating = "error"
        else:
            rating = rating.get('data-rating')

        # На основании скольки отзывов построен рейтинг
        num_rating = product_info_block.select_one('div.product-info__stat > a.product-info__opinions-count')
        if not num_rating:
            logger.error("No num rating")
            num_rating = 0
        else:
            num_rating = re.findall(r'\d+', num_rating.text)[0]

        # Код продукта
        product_code = product_info_block.select_one('div.product-info__code > span')
        if not product_code:
            logger.error("No product code")
            product_code = "error"
        else:
            product_code = product_code.text

        # ЦЕНА, СКИДКА, ВЫГОДА
        product_price_block = block.select_one('div.n-catalog-product__price')

        # Ветвление: 2 вида акций, поиск по тегам
        cur_price = product_price_block.select_one('mark.product-min-price__min-price')

        # Если есть "акция"
        if cur_price:
            cur_price = re.findall(r'\d+', cur_price.text.replace(' ', ''))[0]

            # Предыдущая цена (без скидки) - если есть акция
            prev_price = product_price_block.select_one('div.product-min-price__current')
            if not prev_price:
                prev_price = cur_price
            else:
                prev_price = prev_price.text.replace('₽', '').replace(' ', '')

        # Если есть "выгода"
        else:
            # Текущая цена
            cur_price = product_price_block.select_one('div.product-min-price__current')
            if not cur_price:
                logger.error("No current price")
                cur_price = "error"
            else:
                cur_price = cur_price.text.replace('₽', '').replace(' ', '')

            # Предыдущая цена (без скидки) - если есть акция
            prev_price = product_price_block.select_one('mark.product-min-price__previous-price')
            if not prev_price:
                prev_price = cur_price
            else:
                prev_price = prev_price.text.replace('₽', '').replace(' ', '')

        # Разница цен
        discount = int(prev_price) - int(cur_price)

        # Добавление полученных результатов в коллекцию
        self.result.append(ParseResult(
            category=self.category,
            brand_name=brand_name,
            model_name=model_name,
            specifications=specifications,
            price=cur_price,
            old_price=prev_price,
            discount=discount,
            url_img=img_url,
            url=url,
            rating=rating,
            num_rating=num_rating,
            product_code=product_code,
            shop=self.shop
        ))

    # Запуск браузера, загрузка начальной страницы парсинга, выбор города
    def __wd_open_browser(self, url):
        self.driver.get(url)

        # Ожидание загрузки цен, таймаут = 10, в случае исключения - выход
        if not self.__find_elem_with_timeout(By.CLASS_NAME, "product-min-price__current"):
            self.driver.quit()
            return None

        # Выбор города
        self.__city_selection()

    # Получить текущий код страницы
    def __wd_get_cur_page(self):
        return self.driver.page_source

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):
        self.cur_page += 1
        try:
            num_page_elem = self.driver.find_element_by_xpath(
                f"//li[@class='pagination-widget__page ']/a[text()='{self.cur_page}']")
            num_page_elem.click()

            # Ждем, пока на новой странице не подгрузятся цены, только потом передаем управление
            if not self.__find_elem_with_timeout(By.CLASS_NAME, "product-min-price__current"):
                logger.info(f"Не удалось подгрузить цены на '{self.cur_page}' странице")
                return False

            time.sleep(WAIT_BETWEEN_PAGES_SEC)
            return True

        # Если страница не найдена - достигнут конец каталога
        except se.NoSuchElementException:
            logger.info("Достигнут конец каталога")
            return False

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Сохранение всего результата в csv файл
    def __save_result(self):
        path = '/Users/Никита/Desktop/goods.csv'
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(HEADERS)
            for item in self.result:
                writer.writerow(item)

    # Запуск работы парсера для каталога
    def run_catalog(self, url):
        self.__wd_open_browser(url)

        while True:
            html = self.__wd_get_cur_page()
            self.__parse_catalog_page(html)
            if not self.__wd_next_page():
                break

        self.__wd_close_browser()
        self.__save_result()
        print(self.result)

    # Запуск работы парсера для продукта
    def run_product(self, url):
        self.__wd_open_browser(url)
        html = self.__wd_get_cur_page()
        self.__parse_product_page(html)
        self.__wd_close_browser()


if __name__ == '__main__':
    parser = Parser()
    parser.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/?order=1&groupBy=none&action=rassrockailivygoda0000-tovarysoskidkoj0000&brand=oppo-samsung&f%5B9a9%5D=32tl&f%5B9a8%5D=8f9i-cnhx-i2ft-mhrw1&stock=2")

import logging
import collections
import time

from enum import Enum
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('parser')

PARSE_RESULT = collections.namedtuple(
    'ParseResult',
    (
        'category',
        'brand_name',
        'model',
        'specifications',
        'price',
        'old_price',
        'url_img',
        'url',
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
    'Ссылка на изображение',
    'Ссылка',
    'Магазин',
)
CURRENT_CITY = 'Новосибирск'
WD_PATH = "venv/WebDriverManager/chromedriver.exe"
WAIT_BETWEEN_PAGES_SEC = 3


class ParseWhat(Enum):
    PRODUCT_PAGE = 1
    CATALOG_PAGE = 2


class Parser:

    def __init__(self):
        options = Options()
        # options.add_argument("window-size=1,1")
        self.driver = webdriver.Chrome(executable_path=WD_PATH, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.cur_page = 1

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
        print(html)
        return

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        return

    # Запуск браузера, загрузка начальной страницы парсинга, выбор города
    def wd_open_browser(self, url):
        self.driver.get(url)

        # Ожидание загрузки цен, таймаут = 10, в случае исключения - выход
        if not self.__find_elem_with_timeout(By.CLASS_NAME, "product-min-price__current"):
            self.driver.quit()
            return None

        # Выбор города
        self.__city_selection()

    # Получить текущий код страницы
    def wd_get_cur_page(self):
        return self.driver.page_source

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def wd_next_page(self):
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
    def wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Запуск работы парсера для каталога
    def run_catalog(self, url):
        self.wd_open_browser(url)

        while True:
            html = self.wd_get_cur_page()
            self.__parse_catalog_page(html)

            if not self.wd_next_page():
                break

        self.wd_close_browser()

    # Запуск работы парсера для продукта
    def run_product(self, url):
        self.wd_open_browser(url)
        html = self.wd_get_cur_page()
        self.__parse_product_page(html)
        self.wd_close_browser()


if __name__ == '__main__':
    parser = Parser()
    parser.run_product("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")

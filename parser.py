import logging
import collections
import time

import selenium.common.exceptions as SE
from selenium.webdriver import Chrome
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
WEBDRIVER_PATH = "venv/WebDriverManager/chromedriver.exe"


class Parser:

    def __init__(self):
        options = Options()
        # options.add_argument("window-size=1,1")
        self.driver = Chrome(executable_path=WEBDRIVER_PATH, options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def load_one_page(self, url):
        self.driver.get(url)

        # Ожидание загрузки цен, таймаут = 10, в случае исключения - выход
        try:
            self.wait.until(presence_of_element_located((By.CLASS_NAME,
                                                         "product-min-price__current")))
        except SE.TimeoutException:
            self.driver.quit()
            return None

        # Выбор города
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

        except SE.NoSuchElementException:
            # Если не нашел всплывающего окна с подтверждением города
            city_head = self.driver.find_element_by_xpath("//div[@class='w-choose-city-widget-label']")
            # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
            if city_head.text.find(CURRENT_CITY) == -1:
                city_head.click()
                input_city = self.wait.until(presence_of_element_located((By.XPATH, "//div[@class='search-field']/"
                                                                                    "input[@data-role='search-city']")))
                # Отправка нужного города
                input_city.send_keys(CURRENT_CITY, Keys.ENTER)

        logger.info("Цены загружены успешно, передача html кода")
        content = self.driver.page_source
        # self.driver.close()
        return content

    def load_page(self, url):
        self.driver.get(url)

        # Ожидание загрузки цен, таймаут = 10, в случае исключения - выход
        try:
            self.wait.until(presence_of_element_located((By.CLASS_NAME,
                                                         "product-min-price__current")))
        except SE.TimeoutException:
            self.driver.quit()
            return None

        num_page = 4
        # Переход на заданную страницу num_page через клик (для имитации пользователя)
        self.driver.find_element_by_xpath(f"//li[@class='pagination-widget__page ']/a[text()='{num_page}']").click()


if __name__ == '__main__':
    parser = Parser()
    parser.load_one_page("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")


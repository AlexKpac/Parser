from abc import ABC, abstractmethod
import time
import csv
import configparser

import bs4
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.expected_conditions import presence_of_element_located, presence_of_all_elements_located
from selenium.webdriver.common.keys import Keys
import modules.common.helper as h
from modules.common.file_worker import FileWorker


class ParseBase(ABC):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Абстрактный базовый класс для всех парсеров, использующий Selenium
    """

    def __init__(self, domain, shop, logger, category, is_proxy=False, cur_page=2):
        self.logger = logger
        self.container_css_selector = None

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # options.add_argument("window-size=1920,1080")
        # options.add_argument("--disable-notifications")
        if is_proxy:
            options.add_argument("--proxy-server=%s" % h.get_proxy())

        try:
            self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        except se.WebDriverException as e:
            self.logger.error("НЕ СМОГ ИНИЦИАЛИЗИРОВАТЬ WEBDRIVER, {}".format(e))
            self.driver = None
            return

        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 20)
        self.pr_result_list = []
        self.cur_page = cur_page
        # Данные магазина
        self.domain = domain
        self.shop = shop
        self.category = category
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.current_city = self.config.defaults()['current_city']
        self.wait_between_pages_sec = int(self.config.defaults()['wait_between_pages_sec'])

    def _wd_find_elem(self, by, xpath):
        """
        Поиск одного элемента без таймаута
        """
        try:
            result = self.driver.find_element(by, xpath)
            return result
        except (se.NoSuchElementException, se.TimeoutException):
            return None

    def _wd_find_all_elems(self, by, xpath):
        """
        Поиск всех элементов без таймаута
        """
        try:
            result = self.driver.find_elements(by, xpath)
            return result
        except se.NoSuchElementException:
            return None

    def _wd_find_elem_with_timeout(self, by, element):
        """
        Поиск элемента с таймаутом
        """
        try:
            result = self.wait.until(presence_of_element_located((by, element)))
            return result
        except se.TimeoutException:
            return None

    def _wd_find_all_elems_with_timeout(self, by, element):
        """
        Поиск всех элементов с таймаутом
        """
        try:
            result = self.wait.until(presence_of_all_elements_located((by, element)))
            return result
        except se.TimeoutException:
            return None

    def _wd_ac_send_keys(self, element, keys):
        """
        Отправка клавиши в элемент через ActionChains
        """
        if not element:
            return False

        try:
            ActionChains(self.driver).move_to_element(element).send_keys(keys).perform()
        except Exception as e:
            self.logger.error("Не смог отправить клавишу через ActionChains, {}".format(e))
            return False

        return True

    def _wd_ac_click_elem(self, element):
        """
        Обертка для клика по элементу через ActionChains
        """
        if not element:
            return False

        try:
            ActionChains(self.driver).move_to_element(element).click().perform()
        except Exception as e:
            self.logger.error("Не смог нажать на элемент через ActionChains, {}".format(e))
            return False

        return True

    def _wd_click_elem(self, element):
        """
        Обертка для клика по элементу через click
        """
        if not element:
            return False

        try:
            element.click()
            return True
        except Exception as e:
            self.logger.error("Не смог нажать на элемент через click, {}".format(e))
            return False

    def _wd_scroll_down(self, count_press=7, timeout=0.2):
        """
        Скролл вниз для прогрузки товаров на странице
        """
        for _ in range(count_press):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(timeout)

    def _wd_scroll_up(self, count_press=7, timeout=0.2):
        """
        Скролл вверх для прогрузки товаров на странице
        """
        for _ in range(count_press):
            ActionChains(self.driver).send_keys(Keys.PAGE_UP).perform()
            time.sleep(timeout)

    def _multiple_func_call(self, fun, count=3, true_result=True):
        """
        Множественный вызов передаваемой функции, пока она не вернет true_result
        """
        for i in range(count):
            if fun() == true_result:
                break
            self.logger.warning("[{}/{}] Функция {} в цикле MULTI_CALL вернула NotTrueResult".format(i + 1, count, fun))
        else:
            self.logger.error("Все попытки в цикле MULTI_CALL для метода {} провалились".format(fun))
            return False

        self.logger.info("Успешный вызов метода {} в цикле MULTI_CALL".format(fun))
        return True

    def _add_to_pr_result_list(self, brand_name, model_name, color, price, ram, rom,
                               img_url, url, rating, num_rating, product_code):
        """
        Добавление спарсенных данных одного блока к результирующему списку всех спарсенных позиций
        """
        if 'apple' in brand_name.lower():
            ram = 0

        # Добавление полученных результатов в коллекцию
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=self.category.lower(),
            brand_name=brand_name.lower(),
            model_name=model_name.lower(),
            color=color.lower(),
            price=price,
            ram=ram,
            rom=rom,
            img_url=img_url.lower(),
            url=url.lower(),
            rating=rating,
            num_rating=num_rating,
            product_code=product_code.lower(),
        ))

    def _wd_get_cur_page(self):
        """
        Получить текущий код страницы
        """
        try:
            return self.driver.page_source
        except Exception as e:
            self.logger.error("Не смог получить код страницы, {}".format(e))
            return None

    def _wd_close_browser(self):
        """
        Завершение работы браузера
        """
        self.logger.info("Завершение работы")
        if self.driver:
            self.driver.quit()

    def _parse_catalog_page(self, html):
        """
        Парсинг блоков каталога
        """
        if not self.container_css_selector:
            raise AttributeError('self.container_css_selector not initialized in child class.')

        soup = bs4.BeautifulSoup(html, 'lxml')

        # Контейнер с элементами
        container = soup.select(self.container_css_selector)
        for block in container:
            self._parse_catalog_block(block)
        del container

    def _save_result(self):
        """
        Сохранение всего результата в csv файл
        """
        FileWorker.csv_data.save(path=h.CSV_PATH_RAW + self.shop + '.csv',
                                 data=self.pr_result_list, namedtuple_type=h.ParseResult)

    def run_catalog(self, url, cur_page=None):
        """
        Запуск работы парсера для каталога
        """
        if not self.driver:
            self._wd_close_browser()
            return None

        if not self._wd_open_browser_catalog(url):
            self.logger.error("Open browser fail")
            self._wd_close_browser()
            return None

        if cur_page:
            self.cur_page = cur_page + 1

        while True:
            html = self._wd_get_cur_page()
            self._parse_catalog_page(html)
            if not self._wd_next_page():
                break

        self._wd_close_browser()
        self._save_result()
        return self.pr_result_list

    def run_product(self, url):
        """
        Запуск работы парсера для продукта
        """
        pass

    @abstractmethod
    def _wd_open_browser_catalog(self, url):
        """
        Запуск браузера, загрузка начальной страницы каталога, выбор города
        """
        try:
            self.driver.get(url)
        except Exception as e:
            self.logger.error("Не смог загрузить страницу, {}".format(e))
            return False

        # Ждем, пока не прогрузится страница, даем 3 попытки, т.к. сайт при первом запуске часто выдает пустую страницу
        if not self._multiple_func_call(self._wd_check_load_page_catalog):
            self.logger.error("Не удалось прогрузить страницу в _wd_open_browser [base]")
            return False

        # Выбор города
        if not self._wd_city_selection_catalog():
            self.logger.info("Не могу выбрать город")
            return False

        time.sleep(2)

        # Ждем, пока не прогрузится страница
        if not self._wd_check_load_page_catalog():
            self.logger.error("Не удалось прогрузить страницу в _wd_open_browser [base] (2)")
            return False

        return True

    @abstractmethod
    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций на странице каталога
        """
        pass

    @abstractmethod
    def _wd_city_selection_product(self):
        """
        Алгоритм выбора города для всех возмодных ситуаций на странице продукта
        """
        pass

    @abstractmethod
    def _wd_check_load_page_catalog(self):
        """
        Проверка по ключевым div-ам что страница каталога прогружена полностью
        """
        pass

    @abstractmethod
    def _wd_check_load_page_product(self):
        """
        Проверка по ключевым div-ам что страница продукта прогружена полностью
        """
        pass

    @abstractmethod
    def _wd_open_browser_product(self, url):
        """
        Запуск браузера, загрузка начальной страницы продукта, выбор города
        """
        pass

    @abstractmethod
    def _wd_next_page(self):
        """
        Переход на заданную страницу num_page через клик (для имитации пользователя)
        """
        pass

    @abstractmethod
    def _parse_product_page(self, html, url):
        """
        Метод для парсинга html страницы продукта
        """
        pass

    @abstractmethod
    def _parse_catalog_block(self, block):
        """
        Парсинг данных одного блока
        """
        pass

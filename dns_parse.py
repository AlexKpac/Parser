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
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import header as h


DNS_REBUILT_IPHONE = ' "как новый"'
logger = h.logging.getLogger('dnsparse')


# Парсинг названия модели (получить название модели, цвет и ROM)
def dns_parse_model_name(brand_name, name):
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Понижение регистра
    name = name.lower()
    brand_name = brand_name.lower()
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (DNS_REBUILT_IPHONE in name) else ''
    name = name.replace(DNS_REBUILT_IPHONE if rebuilt else '', '')
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
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
    rom = re.findall(r'\d+', rom)
    rom = int(rom[0]) if rom else 0
    # Удалить из строки модели цвет, название бренда и слово "смартфон"
    name = name.replace(color, '').replace('смартфон', '').replace(year, '').replace(' nfc ', ' ').replace(' 5g ', ' ')
    # Удалить лишние пробелы
    name = ' '.join(name.split())
    name += rebuilt

    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        return None, None, None

    model_name = name.replace(brand_name, '').strip()
    return model_name, color, rom


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
        options.add_argument("--disable-notifications")
        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 20)
        self.pr_result_list = []
        self.cur_page = 2
        self.err_page = 0
        # Данные магазина
        self.domain = "https://www.dns-shop.ru"
        self.shop = "dns"
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.current_city = self.config.defaults()['current_city']
        self.wait_between_pages_sec = int(self.config.defaults()['wait_between_pages_sec'])

    # Обертка поиска элемента для обработки исключений
    def __wd_find_elem(self, by, xpath):
        try:
            result = self.driver.find_element(by, xpath)
            return result
        except (se.NoSuchElementException, se.TimeoutException):
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

    # Поиск всех элементов без таймаута
    def __wd_find_all_elems(self, by, xpath):
        pass

    # Отправка клавиши в элемент через ActionChains
    def __wd_ac_send_keys(self, elem, keys):
        pass

    # Обертка для клика по элементу через ActionChains
    def __wd_ac_click_elem(self, elem):
        pass

    # Обертка для клика по элементу через click
    def __wd_click_elem(self, elem):
        if not elem:
            return False

        try:
            elem.click()
            return True
        except se.ElementClickInterceptedException:
            logger.error("Элемент некликабельный")
            return False
        except se.StaleElementReferenceException:
            logger.error(" -- КЛИК ПО УСТАРЕВШЕМУ ЭЛЕМЕНТУ --")
            return False

    # Алгоритм выбора города для всех возможных ситуаций на странице каталога
    def __wd_city_selection_catalog(self):
        city_head = self.__wd_find_elem(By.XPATH, "//i[@class='location-icon']")
        if not city_head:
            logger.error("Не могу найти элемент с текущим городом на странице")
            return False

        # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
        if not (self.current_city.lower() in city_head.text.lower()):

            if not self.__wd_click_elem(city_head):
                logger.error("Не могу кликнуть по названию города для его смены")
                return False

            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='search-field']/"
                                                                    "input[@data-role='search-city']")
            if not input_city:
                logger.error("Не могу найти поле для ввода города")
                return False

            # Отправка нужного города
            input_city.send_keys(self.current_city, Keys.ENTER)

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "product-min-price__current"):
            return False

        logger.info("Page loaded")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Скролл вниз для прогрузки товаров на странице
    def __wd_scroll_down(self):
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
        try:
            return self.driver.page_source
        except se.TimeoutException:
            return None

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):
        for num_try in range(3):

            if num_try and not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            # Поиск следующей кнопки страницы
            num_page_elem = self.__wd_find_elem(By.XPATH,
                                                "//li[@class='pagination-widget__page ']/a[text()='{}']".format(self.cur_page))
            if not num_page_elem:
                logger.info("Достигнут конец каталога")
                return False

            # Клик - переход на следующую страницу
            if not self.__wd_click_elem(num_page_elem):
                logger.error("Не могу кликнуть на страницу в __wd_next_page")
                self.driver.refresh()
                continue

            # Специальная задержка между переключениями страниц для имитации юзера
            time.sleep(self.wait_between_pages_sec)

            # Ждем, пока не прогрузится страница
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Особенность ДНС - при переключении страницы иногда не меняется контент. Если так - обновляем страницу
            try:
                self.wait.until_not(presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                    self.pr_result_list[-5].url.replace(self.domain, '')))))
                self.cur_page += 1
                return True
            except se.TimeoutException:
                logger.error("TimeoutException в __wd_next_page, обновляю страницу")
                self.driver.refresh()
                continue
            except IndexError:
                logger.error('По непонятной причине список pr_result_list[-5] оказался пуст, выход за границы списка')
                return False
        else:
            logger.error("!! После 3 попыток не получилось переключить страницу !!")
            return False

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html, url):
        pass

    # Парсинг блоков каталога
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

    # Парсинг данных одного блока
    def __parse_catalog_block(self, block):

        # Название модели и URL
        model_name_url_block = block.select_one('div.product-info__title-link > a.ui-link')
        if not model_name_url_block:
            logger.warning("No model name and URL")
            return
        else:
            url = self.domain + model_name_url_block.get('href')
            model_name = model_name_url_block.text

        # Проверка на предзаказ
        if [item.text for item in block.select("button") if item.text == "Предзаказ"]:
            logger.info("Товар '{}' по предзаказу, пропуск".format(model_name))
            return

        # Название бренда
        brand_name = block.select_one('i[data-product-param=brand]')
        if not brand_name:
            logger.warning("No brand name")
            return
        else:
            brand_name = brand_name.get('data-value')

        # Ссылка на изображение товара
        img_url = block.select_one('img')
        if not img_url:
            logger.warning("No img url")
            return
        else:
            img_url = img_url.get('data-src')

        # Характеристики товара
        specifications = block.select_one('span.product-info__title-description')
        if not specifications:
            logger.warning("No specifications")
            return
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
            logger.warning("No product code")
            return
        else:
            product_code = product_code.text

        # Цена, ветвление: 2 вида акций, поиск по тегам
        price = block.select_one('div.product-min-price__min')

        # Если есть "акция"
        if price and not ('скидка' in price.text):
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])
        # Если есть "выгода"
        else:
            price = block.select_one('div.product-min-price__current')
            if not price:
                logger.warning("No current price")
                return
            else:
                price = int(price.text.replace('₽', '').replace(' ', ''))

        # Парсинг названия модели
        model_name, color, rom = dns_parse_model_name(brand_name, model_name)
        if not model_name or not color or not rom:
            logger.warning("No model name, color or rom")
            return

        ram = 0 if ('apple' in brand_name.lower()) else dns_parse_specifications(specifications)

        # Добавление полученных результатов в коллекцию
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=self.category.lower(),
            brand_name=brand_name.lower(),
            model_name=model_name.lower(),
            color=color.lower(),
            cur_price=price,
            ram=ram,
            rom=rom,
            img_url=img_url,
            url=url,
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
        self.__save_result('dns.csv')
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

    parser = DNSParse()
    parser.run_catalog('https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

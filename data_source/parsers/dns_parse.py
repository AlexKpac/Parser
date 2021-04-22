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
from selenium.webdriver.support.expected_conditions import presence_of_element_located, presence_of_all_elements_located
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import common.general_helper as h

DNS_REBUILT_IPHONE = ' "как новый"'
logger = h.logging.getLogger('dnsparse')


# Парсинг названия модели (получить название модели, цвет и ROM)
def dns_parse_model_name(name):
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Понижение регистра
    name = name.lower()
    # Характеристики из названия
    characteristics = re.findall(r'\[.*]', name)[0]
    name = name.replace(characteristics, '')
    ram = dns_parse_specifications(characteristics)

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

    # # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        return None, None, None, 0, 0

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color, ram, rom


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

        try:
            self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        except se.WebDriverException:
            print("НЕ СМОГ ИНИЦИАЛИЗИРОВАТЬ WEBDRIVER")
            self.driver = None
            return

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
        try:
            result = self.wait.until(presence_of_all_elements_located((by, elem)))
            return result
        except se.TimeoutException:
            return None

    # Поиск всех элементов без таймаута
    def __wd_find_all_elems(self, by, xpath):
        pass

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
        # Поиск шапки выбора города и название города
        city_head = self.__wd_find_elem(By.XPATH, "//i[@class='location-icon']")
        city_head_text = self.__wd_find_elem(By.XPATH, "//div[@class='w-choose-city-widget-label']")
        if not city_head or not city_head_text:
            logger.error("Не могу найти элемент с текущим городом на странице")
            return False

        # Если в шапке сайта указан неверный город - кликаем по нему и выбираем нужный
        if self.current_city.lower() not in city_head_text.text.lower():

            if not self.__wd_click_elem(city_head):
                logger.error("Не могу кликнуть по названию города для его смены")
                return False

            time.sleep(1)

            # Поиск города в заготовленном списке крупных городов
            city_list = self.__wd_find_all_elems_with_timeout(By.XPATH, "//span[@databases-role='big-cities']")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(0.5)
                        return self.__wd_ac_click_elem(item)
            else:
                logger.info("Не вижу нужный город в списке, пробую вбить вручную")

            # Если в заготовонном списке нет нужного города - ищем input и вводим в поиск
            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//input[@databases-role='search-city']")
            if not input_city:
                logger.error("Не могу найти поле для ввода города")
                return False

            # Кликнуть на форму для ввода текста
            if not self.__wd_ac_click_elem(input_city):
                logger.error("Не могу кликнуть на форму для ввода текста")
                return False
            time.sleep(1)

            # Ввод названия города по буквам
            for char in self.current_city:
                self.__wd_ac_send_keys(input_city, char)

            # Найти в результирующем списке нужный город
            city_list = self.__wd_find_all_elems_with_timeout(By.XPATH, "//li[@class='modal-row']/a/span/mark")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(0.5)
                        return self.__wd_ac_click_elem(item)
            else:
                logger.error("Не вижу нужный город в списке input, выход")
                return False

        return True

    # Алгоритм выбора города для всех возмодных ситуаций на странице продукта
    def __wd_city_selection_product(self):
        pass

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.XPATH,
                                                "//div[contains(@class, 'product-buy__price')]"):
            return False

        logger.info("Page loaded")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Скролл вниз для прогрузки товаров на странице
    def __wd_scroll_down(self):
        for _ in range(7):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.2)

    def __wd_scroll_up(self):
        for _ in range(7):
            ActionChains(self.driver).send_keys(Keys.PAGE_UP).perform()
            time.sleep(0.2)

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

        self.__wd_scroll_down()

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

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):
        for num_try in range(3):

            if num_try and not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            if num_try:
                # Скролл
                self.__wd_scroll_up()

            # Поиск следующей кнопки страницы
            num_page_elem = self.__wd_find_elem(By.XPATH,
                                                "//a[@class='pagination-widget__page-link' and text()='{}']".
                                                format(self.cur_page))
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
                logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Скролл
            self.__wd_scroll_down()

            # Особенность ДНС - при переключении страницы иногда не меняется контент. Если так - обновляем страницу
            try:
                self.wait.until_not(presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                    self.pr_result_list[-5].url.replace(self.domain, '')))))

                logger.info("Cur_page = {}".format(self.cur_page))
                self.cur_page += 1
                return True
            except se.TimeoutException:
                print("НЕ ДОЖДАЛСЯ -5, обновляю")
                logger.error("TimeoutException в __wd_next_page, обновляю страницу")
                self.driver.refresh()
                continue
            except IndexError:
                logger.error('По непонятной причине список pr_result_list[-5] оказался пуст, выход за границы списка')
                return False
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
        container = soup.select('div.catalog-product.ui-button-widget')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Парсинг данных одного блока
    def __parse_catalog_block(self, block):

        # Название модели и URL
        model_name_url_block = block.select_one('a.catalog-product__name.ui-link.ui-link_black')
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

        # Ссылка на изображение товара
        img_url = block.select_one('img.loaded')
        if not img_url:
            logger.warning("No img url")
            return
        else:
            img_url = img_url.get('databases-src')

        # Рейтинг товара
        rating_block = block.select_one('a.catalog-product__rating.ui-link.ui-link_black')
        if not rating_block:
            rating = 0
            num_rating = 0
        else:
            rating = float(rating_block.get('databases-rating'))

            # Кол-во отзывов
            num_rating = re.findall(r'\d+\.*\d*k*', rating_block.text)
            if num_rating:
                num_rating = num_rating[0]
                num_rating = int(float(num_rating.replace('k', '')) * 1000) if 'k' in num_rating \
                    else int(num_rating)
            else:
                num_rating = 0

        # Код продукта
        product_code = block.get('databases-code')
        if not product_code:
            logger.warning("No product code")

        # Цена
        price = block.select_one('div.product-buy__price')
        if not price:
            print("ДНС: НЕТ ЦЕНЫ !!!!!!")
            logger.warning("No price")
            return 
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Парсинг названия модели
        brand_name, model_name, color, ram, rom = dns_parse_model_name(model_name)
        if not brand_name or not model_name or not color or not rom:
            logger.warning("No brand name, model name, color or rom")
            return

        if 'apple' in brand_name:
            ram = 0

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
                try:
                    writer.writerow(item)
                except UnicodeEncodeError as e:
                    print("!!!ОШИБКА КОДИРОВКИ!!!")
                    print('item = "{}"'.format(item))
                    print("error = {}".format(e))

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
        self.__save_result('dns.csv')
        return self.pr_result_list

    # Запуск работы парсера для продукта
    def run_product(self, url):
        pass


if __name__ == '__main__':
    import main
    import os

    # os.system("taskkill /f /im  chrome.exe")

    time_start = time.time()
    main.load_allowed_model_names_list_for_base()
    main.load_exceptions_model_names()
    main.read_config()

    parser = DNSParse()

    parser.run_catalog('https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

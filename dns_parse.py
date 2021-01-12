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

logger = h.logging.getLogger('dnsparse')
DNS_REBUILT_IPHONE = ' "как новый"'


# Загрузить данные с csv, чтобы не парсить сайт
def load_result_from_csv():
    pr_result_list = []
    with open(h.CSV_PATH, 'r', encoding='UTF-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            pr_result_list.append(h.ParseResult(
                shop=row['Магазин'],
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                cur_price=int(row['Цена']),
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
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)
    # Понижение регистра
    name = name.lower()
    brand = brand.lower()
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
    name = name.replace(color, '').replace(brand, '').replace('смартфон', '').replace(year, '').replace(' nfc ', ' ').\
        replace(' 5g ', ' ')
    # Удалить лишние пробелы
    name = ' '.join(name.split())

    return (name + rebuilt), color, rom


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
        self.wait = WebDriverWait(self.driver, 30)
        self.pr_result_list = []
        self.cur_page = 1
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

        logger.info("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница продукта прогружена полностью
    def __wd_check_load_page_product(self):
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
        except IndexError:
            logger.error('По непонятной причине список pr_result_list[-5] оказался пуст, выход за границы списка')
            return False

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
            # # Заплатка для POCO
            # if 'poco' in brand_name.lower():
            #     brand_name = 'xiaomi'

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
        price = product_block.select_one("span.product-card-price__current")
        if not price:
            logger.error("No cur price")
            price = 0
        else:
            price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

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
            cur_price=price,
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
            logger.warning("No model name and URL")
            return
        else:
            url = self.domain + model_name_url_block.get('href')
            model_name = model_name_url_block.text

        # Название бренда
        brand_name = block.select_one('i[data-product-param=brand]')
        if not brand_name:
            logger.warning("No brand name")
            return
        else:
            brand_name = brand_name.get('data-value')
            # # Заплатка для POCO
            # if 'poco' in brand_name.lower():
            #     brand_name = 'xiaomi'

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

        # Парсинг полученных данных
        model_name, color, rom = dns_parse_model_name(brand_name, model_name)

        if not model_name or not color:
            logger.warning("No model name or color")
            return

        ram = dns_parse_specifications(specifications)
        if not ram:
            logger.warning("No ram")

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
    def __save_result(self):
        with open(h.CSV_PATH_RAW + "dns.csv", 'w', newline='') as f:
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
        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return None

        html = self.__wd_get_cur_page()
        self.__parse_product_page(html, url)
        self.__wd_close_browser()
        self.__save_result()
        return self.pr_result_list


models = (
    '4" Смартфон DEXP A340 16 ГБ розовый',
    '4" Смартфон DEXP A340 16 ГБ черный',
    '5" Смартфон DEXP G450 8 ГБ серый',
    '5" Смартфон DEXP G450 8 ГБ синий',
    '5" Смартфон INOI 2 Lite 2019 4 ГБ золотистый',
    '5" Смартфон DEXP BL350 16 ГБ зеленый',
    '5" Смартфон DEXP BL350 16 ГБ серый',
    '5.5" Смартфон Itel A52 Lite 8 ГБ голубой',
    '5.5" Смартфон Itel A52 Lite 8 ГБ серый',
    '5" Смартфон DEXP A350 MIX 32 ГБ зеленый',
    '5" Смартфон DEXP A350 MIX 32 ГБ красный',
    '5" Смартфон DEXP A350 MIX 32 ГБ синий',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ золотистый',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ серый',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ синий',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ черный',
    '5" Смартфон INOI 2 2019 8 ГБ черный',
    '5" Смартфон Itel A16 Plus 8 ГБ голубой',
    '4" Смартфон DEXP A340 16 ГБ розовый',
    '4" Смартфон DEXP A340 16 ГБ черный',
    '5" Смартфон DEXP G450 8 ГБ серый',
    '5" Смартфон DEXP G450 8 ГБ синий',
    '5" Смартфон INOI 2 Lite 2019 4 ГБ золотистый',
    '5" Смартфон DEXP BL350 16 ГБ зеленый',
    '5" Смартфон DEXP BL350 16 ГБ серый',
    '5.5" Смартфон Itel A52 Lite 8 ГБ голубой',
    '5.5" Смартфон Itel A52 Lite 8 ГБ серый',
    '5" Смартфон DEXP A350 MIX 32 ГБ зеленый',
    '5" Смартфон DEXP A350 MIX 32 ГБ красный',
    '5" Смартфон DEXP A350 MIX 32 ГБ синий',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ золотистый',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ серый',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ синий',
    '4.95" Смартфон Nobby S300 Pro 16 ГБ черный',
    '5" Смартфон INOI 2 2019 8 ГБ черный',
    '5" Смартфон Itel A16 Plus 8 ГБ голубой',
    '5" Смартфон Itel A25 16 ГБ синий',
    '5" Смартфон Itel A25 16 ГБ фиолетовый',
    '5.45" Смартфон DEXP BL155 32 ГБ серый',
    '5.45" Смартфон DEXP BL155 32 ГБ синий',
    '5.5" Смартфон INOI 5X Lite 8 ГБ серый',
    '6" Смартфон DEXP A160 32 ГБ серый',
    '6" Смартфон DEXP A160 32 ГБ синий',
    '4.95" Смартфон BQ 5045L Wallet 16 ГБ зеленый',
    '4.95" Смартфон BQ 5045L Wallet 16 ГБ синий',
    '4.95" Смартфон BQ 5045L Wallet 16 ГБ черный',
    '5.99" Смартфон bright & quick BQ 6022G Aura 16 ГБ белый',
    '5" Смартфон DEXP AL350 64 ГБ черный',
    '5.99" Смартфон BQ 6030G Practic 32 ГБ зеленый',
    '5.99" Смартфон BQ 6030G Practic 32 ГБ красный',
    '6.22" Смартфон INOI 7 2020 16 ГБ черный',
    '6.1" Смартфон Doogee X90 16 ГБ золотистый',
    '6.1" Смартфон Doogee X90 16 ГБ синий',
    '6.1" Смартфон Doogee X90 16 ГБ черный',
    '5.3" Смартфон Samsung Galaxy A01 Core 16 ГБ красный',
    '5.3" Смартфон Samsung Galaxy A01 Core 16 ГБ синий',
    '5.3" Смартфон Samsung Galaxy A01 Core 16 ГБ черный',
    '6.1" Смартфон Blackview A60 16 ГБ синий',
    '6.1" Смартфон Blackview A60 16 ГБ черный',
    '5.45" Смартфон DEXP AS155 32 ГБ зеленый',
    '5.45" Смартфон DEXP AS155 32 ГБ серый',
    '5.45" Смартфон Honor 7S 16 ГБ золотистый',
    '5.45" Смартфон Honor 7S 16 ГБ синий',
    '5.45" Смартфон Honor 7S 16 ГБ черный',
    '5.45" Смартфон Huawei Y5 Lite 16 ГБ коричневый',
    '5.45" Смартфон Huawei Y5 Lite 16 ГБ черный',
    '5.71" Смартфон Nokia 1.3 16 ГБ голубой',
    '5.71" Смартфон Nokia 1.3 16 ГБ черный',
    '6.2" Смартфон INOI 7i 8 ГБ черный',
    '5.99" Смартфон DEXP BL160 32 ГБ серый',
    '5.45" Смартфон Huawei Y5P 32 ГБ зеленый',
    '5.45" Смартфон Huawei Y5P 32 ГБ синий',
    '5.45" Смартфон Huawei Y5P 32 ГБ черный',
    '5.7" Смартфон Samsung Galaxy A01 16 ГБ красный',
    '5.7" Смартфон Samsung Galaxy A01 16 ГБ синий',
    '5.7" Смартфон Samsung Galaxy A01 16 ГБ черный',
    '5.99" Смартфон bright & quick BQ 6045L Nice 32 ГБ зеленый',
    '5.99" Смартфон bright & quick BQ 6045L Nice 32 ГБ золотистый',
    '5.99" Смартфон bright & quick BQ 6045L Nice 32 ГБ черный',
    '5.45" Смартфон Honor 9S 32 ГБ красный',
    '5.45" Смартфон Honor 9S 32 ГБ синий',
    '5.45" Смартфон Honor 9S 32 ГБ черный',
    '5.5" Смартфон Blackview BV5500 16 ГБ черный',
    '5.5" Смартфон INOI 5 Pro 16 ГБ черный',
    '6" Смартфон Blackview A60 Pro 16 ГБ синий',
    '6" Смартфон Blackview A60 Pro 16 ГБ черный',
    '6.08" Смартфон Itel Vision 1 32 ГБ синий',
    '6.08" Смартфон Itel Vision 1 32 ГБ фиолетовый',
    '6.088" Смартфон Philips Xenium S266 32 ГБ черный',
    '6.2" Смартфон Blackview A80 16 ГБ красный',
    '6.2" Смартфон Blackview A80 16 ГБ синий',
    '6.2" Смартфон Blackview A80 16 ГБ черный',
    '5.86" Смартфон bright & quick BQ 5732L AURORA SE 32 ГБ синий',
    '5.86" Смартфон bright & quick BQ 5732L AURORA SE 32 ГБ фиолетовый',
    '5.86" Смартфон bright & quick BQ 5732L AURORA SE 32 ГБ черный',
    '6.52" Смартфон Doogee X95 16 ГБ зеленый',
    '6.52" Смартфон Doogee X95 16 ГБ синий',
    '6.52" Смартфон Doogee X95 16 ГБ черный',
    '5.45" Смартфон Honor 7A Prime 32 ГБ зеленый',
    '5.45" Смартфон Honor 7A Prime 32 ГБ синий',
    '5.45" Смартфон Honor 7A Prime 32 ГБ черный',
    '5.45" Смартфон Philips S561 32 ГБ черный',
    '5.5" Смартфон Doogee S40 Lite 16 ГБ оранжевый',
    '5.5" Смартфон Doogee S40 Lite 16 ГБ черный',
    '6.088" Смартфон Philips Xenium S566 32 ГБ черный',
    '6.09" Смартфон Huawei Y6 2019 32 ГБ коричневый',
    '6.09" Смартфон Huawei Y6 2019 32 ГБ синий',
    '6.09" Смартфон Huawei Y6 2019 32 ГБ черный',
    '6.22" Смартфон Vivo Y1S 32 ГБ голубой',
    '6.22" Смартфон Vivo Y1S 32 ГБ черный',
    '6.22" Смартфон Vivo Y91C 32 ГБ красный',
    '6.22" Смартфон Vivo Y91C 32 ГБ черный',
    '6.52" Смартфон Tecno Spark 4 32 ГБ серый',
    '6.52" Смартфон Tecno Spark 6 Go 32 ГБ белый',
    '6.52" Смартфон Tecno Spark 6 Go 32 ГБ зеленый',
    '6.52" Смартфон Tecno Spark 6 Go 32 ГБ синий',
    '6.52" Смартфон realme C11 32 ГБ зеленый',
    '6.52" Смартфон realme C11 32 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9A 32 ГБ зеленый',
    '6.53" Смартфон Xiaomi Redmi 9A 32 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9A 32 ГБ синий',
    '6.95" Смартфон Tecno Spark 5 Air 32 ГБ зеленый',
    '6.95" Смартфон Tecno Spark 5 Air 32 ГБ оранжевый',
    '6.95" Смартфон Tecno Spark 5 Air 32 ГБ серый',
    '6.95" Смартфон Tecno Spark 5 Air 32 ГБ синий',
    '5.71" Смартфон Honor 8S Prime 64 ГБ голубой',
    '5.71" Смартфон Honor 8S Prime 64 ГБ синий',
    '5.71" Смартфон Honor 8S Prime 64 ГБ черный',
    '5.5" Смартфон Blackview BV5500 Plus 32 ГБ желтый',
    '5.5" Смартфон Blackview BV5500 Plus 32 ГБ черный',
    '5.99" Смартфон Highscreen Power Five Max 2 32 ГБ коричневый',
    '5.99" Смартфон Highscreen Power Five Max 2 32 ГБ черный',
    '6.09" Смартфон Huawei Y6S 64 ГБ синий',
    '6.09" Смартфон Huawei Y6S 64 ГБ черный',
    '6.22" Смартфон OPPO A12 32 ГБ голубой',
    '6.22" Смартфон OPPO A12 32 ГБ черный',
    '6.35" Смартфон Vivo Y11 2019 32 ГБ красный',
    '6.35" Смартфон Vivo Y11 2019 32 ГБ синий',
    '6.35" Смартфон bright & quick BQ 6424L MAGIC O 32 ГБ красный',
    '6.35" Смартфон bright & quick BQ 6424L MAGIC O 32 ГБ фиолетовый',
    '6.52" Смартфон realme C3 32 ГБ серый',
    '6.52" Смартфон realme C3 32 ГБ синий',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 32 ГБ оранжевый',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 32 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 32 ГБ синий',
    '6.55" Смартфон Tecno Camon 12 Air 32 ГБ золотистый',
    '6.55" Смартфон Tecno Camon 12 Air 32 ГБ синий',
    '6.6" Смартфон Tecno Spark 5 32 ГБ зеленый',
    '6.6" Смартфон Tecno Spark 5 32 ГБ оранжевый',
    '6.6" Смартфон Tecno Spark 5 32 ГБ синий',
    '5.7" Смартфон Samsung Galaxy M01 32 ГБ красный',
    '5.7" Смартфон Samsung Galaxy M01 32 ГБ синий',
    '5.7" Смартфон Samsung Galaxy M01 32 ГБ черный',
    '6.4" Смартфон Samsung Galaxy A11 32 ГБ белый',
    '6.4" Смартфон Samsung Galaxy A11 32 ГБ красный',
    '6.4" Смартфон Samsung Galaxy A11 32 ГБ черный',
    '6.95" Смартфон Tecno Pouvoir 4 32 ГБ зеленый',
    '6.95" Смартфон Tecno Pouvoir 4 32 ГБ синий',
    '6.95" Смартфон Tecno Pouvoir 4 32 ГБ фиолетовый',
    '6.3" Смартфон Huawei Y6P 64 ГБ зеленый',
    '6.3" Смартфон Huawei Y6P 64 ГБ черный',
    '6.08" Смартфон Honor 8A Prime 64 ГБ зеленый',
    '6.08" Смартфон Honor 8A Prime 64 ГБ синий',
    '6.08" Смартфон Honor 8A Prime 64 ГБ черный',
    '6.49" Смартфон Blackview A80 Pro 64 ГБ зеленый',
    '6.49" Смартфон Blackview A80 Pro 64 ГБ красный',
    '6.49" Смартфон Blackview A80 Pro 64 ГБ синий',
    '6.49" Смартфон Blackview A80 Pro 64 ГБ черный',
    '6.5" Смартфон Nokia 2.4 32 ГБ серый',
    '6.5" Смартфон Nokia 2.4 32 ГБ синий',
    '6.52" Смартфон Tecno Camon 12 64 ГБ голубой',
    '6.52" Смартфон realme C3 64 ГБ красный',
    '6.52" Смартфон realme C3 64 ГБ серый',
    '6.52" Смартфон realme C3 64 ГБ синий',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 64 ГБ оранжевый',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 64 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9C NFC 64 ГБ синий',
    '6.3" Смартфон Doogee Y9 Plus 64 ГБ черный',
    '6.3" Смартфон Honor 9A 64 ГБ голубой',
    '6.3" Смартфон Honor 9A 64 ГБ зеленый',
    '6.3" Смартфон Honor 9A 64 ГБ черный',
    '6.35" Смартфон Vivo Y12 64 ГБ красный',
    '6.35" Смартфон Vivo Y12 64 ГБ синий',
    '6.5" Смартфон OPPO A31 64 ГБ белый',
    '6.5" Смартфон OPPO A31 64 ГБ зеленый',
    '6.5" Смартфон OPPO A31 64 ГБ черный',
    '6.4" Смартфон Samsung Galaxy M11 32 ГБ голубой',
    '6.4" Смартфон Samsung Galaxy M11 32 ГБ фиолетовый',
    '6.4" Смартфон Samsung Galaxy M11 32 ГБ черный',
    '5.99" Смартфон Highscreen Power Five Max 2 64 ГБ черный',
    '6.26" Смартфон Huawei Y7 2019 64 ГБ фиолетовый',
    '6.26" Смартфон Huawei Y7 2019 64 ГБ черный',
    '6.5" Смартфон Nokia 2.4 64 ГБ серый',
    '6.5" Смартфон Nokia 2.4 64 ГБ синий',
    '6.5" Смартфон Nokia 2.4 64 ГБ фиолетовый',
    '6.39" Смартфон Huawei P40 Lite E 64 ГБ голубой',
    '6.39" Смартфон Huawei P40 Lite E 64 ГБ черный',
    '6.6" Смартфон Tecno CAMON 15 Air 64 ГБ голубой',
    '6.6" Смартфон Tecno CAMON 15 Air 64 ГБ зеленый',
    '6.6" Смартфон Tecno CAMON 15 Air 64 ГБ черный',
    '6.51" Смартфон Vivo Y20 64 ГБ голубой',
    '6.51" Смартфон Vivo Y20 64 ГБ черный',
    '6.5" Смартфон realme C15 64 ГБ серебристый',
    '6.5" Смартфон realme C15 64 ГБ синий',
    '6.53" Смартфон Xiaomi Redmi 9 32 ГБ зеленый',
    '6.53" Смартфон Xiaomi Redmi 9 32 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9 32 ГБ фиолетовый',
    '6.47" Смартфон Vivo Y30 64 ГБ черный',
    '6.5" Смартфон OPPO A5 2020 64 ГБ белый',
    '6.5" Смартфон OPPO A5 2020 64 ГБ черный',
    '6.5" Смартфон Samsung Galaxy A20S 32 ГБ красный',
    '6.5" Смартфон Samsung Galaxy A20S 32 ГБ синий',
    '6.5" Смартфон Samsung Galaxy A20S 32 ГБ черный',
    '6.57" Смартфон Vivo Y30 64 ГБ синий',
    '6.6" Смартфон Tecno CAMON 15 64 ГБ зеленый',
    '6.6" Смартфон Tecno CAMON 15 64 ГБ синий',
    '6.6" Смартфон Tecno CAMON 15 64 ГБ фиолетовый',
    '5.7" Смартфон Blackview BV5900 32 ГБ зеленый',
    '5.7" Смартфон Blackview BV5900 32 ГБ черный',
    '5.93" Смартфон Highscreen Max 3 64 ГБ красный',
    '5.93" Смартфон Highscreen Max 3 64 ГБ черный',
    '6.21" Смартфон Honor 10 Lite 64 ГБ голубой',
    '6.21" Смартфон Honor 10 Lite 64 ГБ синий',
    '6.21" Смартфон Honor 10 Lite 64 ГБ черный',
    '6.21" Смартфон Honor 20E 64 ГБ синий',
    '6.21" Смартфон Honor 20E 64 ГБ черный',
    '6.39" Смартфон Honor 9C 64 ГБ синий',
    '6.39" Смартфон Honor 9C 64 ГБ черный',
    '6.39" Смартфон Huawei P40 Lite E 64 ГБ черный',
    '6.4" Смартфон Motorola Moto G8 64 ГБ синий',
    '6.5" Смартфон OPPO A53 64 ГБ зеленый',
    '6.5" Смартфон OPPO A53 64 ГБ синий',
    '6.5" Смартфон OPPO A53 64 ГБ черный',
    '6.55" Смартфон Nokia 5.3 64 ГБ голубой',
    '6.55" Смартфон Nokia 5.3 64 ГБ золотистый',
    '6.55" Смартфон Nokia 5.3 64 ГБ черный',
    '6.53" Смартфон Xiaomi Redmi 9 64 ГБ зеленый',
    '6.53" Смартфон Xiaomi Redmi 9 64 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi 9 64 ГБ фиолетовый',
    '6.4" Смартфон Samsung Galaxy M21 64 ГБ зеленый',
    '6.4" Смартфон Samsung Galaxy M21 64 ГБ синий',
    '6.4" Смартфон Samsung Galaxy M21 64 ГБ черный',
    '6.2" Смартфон Meizu Note 9 64 ГБ черный',
    '6.3" Смартфон Honor 30i 128 ГБ белый',
    '6.3" Смартфон Honor 30i 128 ГБ синий',
    '6.3" Смартфон Honor 30i 128 ГБ черный',
    '6.3" Смартфон Xiaomi Redmi Note 8T 64 ГБ серый',
    '6.5" Смартфон realme 6i 128 ГБ белый',
    '6.5" Смартфон realme 6i 128 ГБ зеленый',
    '6.5" Смартфон Samsung Galaxy A21s 64 ГБ красный',
    '6.5" Смартфон Samsung Galaxy A21s 64 ГБ синий',
    '6.5" Смартфон Samsung Galaxy A21s 64 ГБ черный',
    '6.3" Смартфон Huawei Y8P 128 ГБ голубой',
    '6.3" Смартфон Huawei Y8P 128 ГБ черный',
    '6.5" Смартфон Honor 9X Lite 128 ГБ голубой',
    '6.5" Смартфон Honor 9X Lite 128 ГБ черный',
    '6.5" Смартфон OPPO A52 64 ГБ белый',
    '6.5" Смартфон OPPO A52 64 ГБ черный',
    '6.5" Смартфон Samsung Galaxy A21s 32 ГБ красный',
    '6.5" Смартфон Samsung Galaxy A21s 32 ГБ синий',
    '6.5" Смартфон Samsung Galaxy A21s 32 ГБ черный',
    '6.67" Смартфон Honor 10X Lite 128 ГБ фиолетовый',
    '6.67" Смартфон Honor 10X Lite 128 ГБ черный',
    '6.21" Смартфон Honor 10i 128 ГБ красный',
    '6.21" Смартфон Honor 10i 128 ГБ синий',
    '6.21" Смартфон Honor 10i 128 ГБ черный',
    '6.5" Смартфон OPPO A53 128 ГБ зеленый',
    '6.5" Смартфон OPPO A53 128 ГБ синий',
    '6.5" Смартфон OPPO A53 128 ГБ черный',
    '6.5" Смартфон Xiaomi Redmi Note 9 64 ГБ белый',
    '6.5" Смартфон Xiaomi Redmi Note 9 64 ГБ зеленый',
    '6.5" Смартфон Xiaomi Redmi Note 9 64 ГБ серый',
    '6.5" Смартфон Xiaomi Redmi Note 9 64 ГБ черный',
    '6.53" Смартфон Vivo Y19 128 ГБ черный',
    '6.38" Смартфон Vivo V17 Neo 128 ГБ голубой',
    '6.38" Смартфон Vivo V17 Neo 128 ГБ черный',
    '6.59" Смартфон Honor 9X 128 ГБ зеленый',
    '6.59" Смартфон Honor 9X 128 ГБ синий',
    '6.59" Смартфон Honor 9X 128 ГБ черный',
    '6.6" Смартфон Tecno CAMON 15 Pro 128 ГБ белый',
    '6.6" Смартфон Tecno CAMON 15 Pro 128 ГБ зеленый',
    '6.67" Смартфон Xiaomi Redmi Note 9S 64 ГБ белый',
    '6.67" Смартфон Xiaomi Redmi Note 9S 64 ГБ голубой',
    '6.67" Смартфон Xiaomi Redmi Note 9S 64 ГБ серый',
    '6.15" Смартфон Huawei P30 Lite 128 ГБ синий',
    '6.15" Смартфон Huawei P30 Lite 128 ГБ черный',
    '6.2" Смартфон Meizu Note 9 128 ГБ черный',
    '6.21" Смартфон Honor 10i 128 ГБ красный',
    '6.21" Смартфон Honor 10i 128 ГБ синий',
    '6.15" Смартфон Honor 20 Lite 128 ГБ голубой',
    '6.15" Смартфон Honor 20 Lite 128 ГБ синий',
    '6.15" Смартфон Honor 20 Lite 128 ГБ черный',
    '6.4" Смартфон Samsung Galaxy A31 64 ГБ белый',
    '6.4" Смартфон Samsung Galaxy A31 64 ГБ красный',
    '6.4" Смартфон Samsung Galaxy A31 64 ГБ черный',
    '5.71" Смартфон Doogee S58 Pro 64 ГБ зеленый',
    '5.71" Смартфон Doogee S58 Pro 64 ГБ оранжевый',
    '5.71" Смартфон Doogee S58 Pro 64 ГБ черный',
    '5.7" Смартфон Blackview BV6800 Pro 64 ГБ черный',
    '5.84" Смартфон Blackview BV6900 64 ГБ зеленый',
    '5.84" Смартфон Blackview BV6900 64 ГБ оранжевый',
    '5.84" Смартфон Blackview BV6900 64 ГБ черный',
    '6.3" Смартфон Motorola moto G8 plus 64 ГБ красный',
    '6.38" Смартфон Vivo V17 128 ГБ белый',
    '6.38" Смартфон Vivo V17 128 ГБ синий',
    '6.4" Смартфон OPPO A91 128 ГБ красный',
    '6.4" Смартфон OPPO A91 128 ГБ синий',
    '6.4" Смартфон OPPO A91 128 ГБ черный',
    '6.5" Смартфон Xiaomi Redmi Note 9 128 ГБ белый',
    '6.5" Смартфон Xiaomi Redmi Note 9 128 ГБ зеленый',
    '6.5" Смартфон Xiaomi Redmi Note 9 128 ГБ серый',
    '6.5" Смартфон Xiaomi Redmi Note 9 128 ГБ черный',
    '6.5" Смартфон realme 6 4/128 ГБ белый',
    '6.5" Смартфон realme 6 4/128 ГБ синий',
    '6.5" Смартфон realme 6s 128 ГБ белый',
    '6.5" Смартфон realme 6s 128 ГБ черный',
    '6.59" Смартфон Huawei P Smart Z 64 ГБ синий',
    '6.59" Смартфон Huawei P Smart Z 64 ГБ черный',
    '6.4" Смартфон Huawei P40 Lite 128 ГБ зеленый',
    '6.4" Смартфон Huawei P40 Lite 128 ГБ черный',
    '6.59" Смартфон Honor 9X Premium 128 ГБ черный',
    '6.4" Смартфон Samsung Galaxy M31 128 ГБ красный',
    '6.4" Смартфон Samsung Galaxy M31 128 ГБ синий',
    '6.4" Смартфон Samsung Galaxy M31 128 ГБ черный',
    '5.9" Смартфон Samsung Galaxy A40 64 ГБ красный',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 128 ГБ белый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 128 ГБ зеленый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 128 ГБ оранжевый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 128 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 128 ГБ синий',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 64 ГБ белый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 64 ГБ зеленый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 64 ГБ оранжевый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 64 ГБ серый',
    '6.53" Смартфон Xiaomi Redmi Note 8 Pro 64 ГБ синий',
    '6.1" Смартфон Samsung Galaxy A41 64 ГБ белый',
    '6.1" Смартфон Samsung Galaxy A41 64 ГБ красный',
    '6.1" Смартфон Samsung Galaxy A41 64 ГБ черный',
    '6.4" Смартфон Samsung Galaxy A31 128 ГБ белый',
    '6.4" Смартфон Samsung Galaxy A31 128 ГБ красный',
    '6.4" Смартфон Samsung Galaxy A31 128 ГБ черный',
    '6.15" Смартфон Honor 20S 128 ГБ белый',
    '6.44" Смартфон Vivo V20 SE 128 ГБ голубой',
    '6.44" Смартфон Vivo V20 SE 128 ГБ черный',
    '6.5" Смартфон OPPO A72 128 ГБ белый',
    '6.5" Смартфон OPPO A72 128 ГБ черный',
    '6.5" Смартфон Samsung Galaxy A51 64 ГБ белый',
    '6.5" Смартфон Samsung Galaxy A51 64 ГБ голубой',
    '6.5" Смартфон Samsung Galaxy A51 64 ГБ красный',
    '6.5" Смартфон Samsung Galaxy A51 64 ГБ черный',
    '6.5" Смартфон realme 6 8/128 ГБ белый',
    '6.5" Смартфон realme 6 8/128 ГБ синий',
    '6.5" Смартфон realme 7 128 ГБ белый',
    '6.5" Смартфон realme 7 128 ГБ синий',
    '6.3" Смартфон Blackview BV9100 64 ГБ серый',
    '6.5" Смартфон Samsung Galaxy M31S 128 ГБ синий',
    '6.5" Смартфон Samsung Galaxy M31S 128 ГБ черный',
    '6.6" Смартфон realme 6 Pro 128 ГБ красный',
    '6.6" Смартфон realme 6 Pro 128 ГБ синий',
    '5.7" Смартфон Blackview BV6300 Pro 128 ГБ зеленый',
    '5.7" Смартфон Blackview BV6300 Pro 128 ГБ черный',
    '5.7" Смартфон Blackview BV9500 Plus 64 ГБ черный',
    '5.9" Смартфон Doogee S68 Pro 128 ГБ оранжевый',
    '5.9" Смартфон Doogee S68 Pro 128 ГБ черный',
    '6.5" Смартфон Samsung Galaxy A51 128 ГБ белый',
    '6.5" Смартфон Samsung Galaxy A51 128 ГБ голубой',
    '6.5" Смартфон Samsung Galaxy A51 128 ГБ красный',
    '6.5" Смартфон Samsung Galaxy A51 128 ГБ черный',
    '5.5" Смартфон Apple iPhone 6S Plus "Как новый" 128 ГБ серый',
    '6.18" Смартфон Pocophone F1 64 ГБ синий',
    '6.39" Смартфон Xiaomi Mi 9 Lite 64 ГБ синий',
    '6.5" Смартфон OPPO Reno 2Z 128 ГБ белый',
    '6.5" Смартфон OPPO Reno 2Z 128 ГБ черный',
    '6.67" Смартфон Xiaomi Redmi Note 9 Pro 128 ГБ белый',
    '6.67" Смартфон Xiaomi Redmi Note 9 Pro 128 ГБ зеленый',
    '6.67" Смартфон Xiaomi Redmi Note 9 Pro 128 ГБ серый',
    '4.7" Смартфон Apple iPhone 7 "Как новый" 128 ГБ черный',
    '6.26" Смартфон Huawei Nova 5T 128 ГБ синий',
    '6.26" Смартфон Huawei Nova 5T 128 ГБ фиолетовый',
    '6.4" Смартфон OPPO Reno 4 Lite 128 ГБ синий',
    '6.4" Смартфон OPPO Reno 4 Lite 128 ГБ черный',
    '6.5" Смартфон Honor 30S 128 ГБ серебристый',
    '6.5" Смартфон Honor 30S 128 ГБ фиолетовый',
    '6.5" Смартфон Honor 30S 128 ГБ черный',
    '6.44" Смартфон Vivo V20 128 ГБ синий',
    '6.44" Смартфон Vivo V20 128 ГБ черный',
    '5.84" Смартфон Blackview BV9700 Pro 128 ГБ черный',
    '6.4" Смартфон realme 7 Pro 128 ГБ серебристый',
    '6.4" Смартфон realme 7 Pro 128 ГБ синий',
    '4.7" Смартфон Apple iPhone 7 32 ГБ золотистый',
    '4.7" Смартфон Apple iPhone 7 32 ГБ розовый',
    '4.7" Смартфон Apple iPhone 7 32 ГБ серебристый',
    '4.7" Смартфон Apple iPhone 7 32 Гб черный матовый',
    '6.21" Смартфон Xiaomi Mi 8 64 ГБ синий',
    '5.99" Смартфон Xiaomi Mi Mix 2S 64 ГБ белый',
    '6.4" Смартфон OPPO Reno 3 128 ГБ синий',
    '6.4" Смартфон OPPO Reno 3 128 ГБ черный',
    '6.57" Смартфон realme X3 SuperZoom 128 ГБ белый',
    '6.57" Смартфон realme X3 SuperZoom 128 ГБ синий',
    '6.67" Смартфон Samsung Galaxy M51 128 ГБ белый',
    '6.67" Смартфон Samsung Galaxy M51 128 ГБ черный',
    '6.7" Смартфон Samsung Galaxy A71 128 ГБ голубой',
    '6.7" Смартфон Samsung Galaxy A71 128 ГБ серебристый',
    '6.7" Смартфон Samsung Galaxy A71 128 ГБ черный',
    '4.7" Смартфон Apple iPhone 7 128 ГБ серебристый',
    '6.3" Смартфон Blackview BV9800 128 ГБ черный',
    '6.47" Смартфон Xiaomi Mi Note 10 Lite 128 ГБ белый',
    '6.47" Смартфон Xiaomi Mi Note 10 Lite 128 ГБ фиолетовый',
    '6.47" Смартфон Xiaomi Mi Note 10 Lite 128 ГБ черный',
    '6.53" Смартфон Honor 30 128 ГБ зеленый',
    '6.53" Смартфон Honor 30 128 ГБ черный',
    '6.5" Смартфон OPPO Reno 2 256 ГБ черный',
    '6.57" Смартфон realme X3 SuperZoom 256 ГБ белый',
    '6.57" Смартфон realme X3 SuperZoom 256 ГБ синий',
    '6.1" Смартфон Huawei P30 128 ГБ голубой',
    '6.1" Смартфон Huawei P30 128 ГБ синий',
    '6.3" Смартфон Doogee S95 Pro 128 ГБ черный',
    '6.53" Смартфон Honor 30 Premium 256 ГБ серебристый',
    '6.53" Смартфон Honor 30 Premium 256 ГБ черный',
    '4.7" Смартфон Apple iPhone 8 64 ГБ серый',
    '4.7" Смартфон Apple iPhone SE 2020 64 ГБ белый',
    '4.7" Смартфон Apple iPhone SE 2020 64 ГБ красный',
    '4.7" Смартфон Apple iPhone SE 2020 64 ГБ черный',
    '4.7" Смартфон Apple iPhone SE 2021 64 ГБ красный',
    '4.7" Смартфон Apple iPhone SE 2021 64 ГБ черный',
    '5.84" Смартфон Blackview BV9900 256 ГБ черный',
    '6.56" Смартфон Vivo X50 128 ГБ синий',
    '6.56" Смартфон Vivo X50 128 ГБ черный',
    '6.7" Смартфон Samsung Galaxy Note 10 Lite 128 ГБ белый',
    '6.7" Смартфон Samsung Galaxy Note 10 Lite 128 ГБ красный',
    '6.7" Смартфон Samsung Galaxy Note 10 Lite 128 ГБ черный',
    '4.7" Смартфон Apple iPhone 8 128 ГБ золотистый',
    '6.47" Смартфон Xiaomi Mi Note 10 128 ГБ белый',
    '6.47" Смартфон Xiaomi Mi Note 10 128 ГБ зеленый',
    '6.47" Смартфон Xiaomi Mi Note 10 128 ГБ черный',
    '6.53" Смартфон Huawei Mate 20 128 ГБ синий',
    '6.53" Смартфон Huawei Mate 20 128 ГБ фиолетовый',
    '6.3" Смартфон Blackview BV9800 Pro 128 ГБ черный',
    '4.7" Смартфон Apple iPhone SE 2020 128 ГБ белый',
    '4.7" Смартфон Apple iPhone SE 2020 128 ГБ красный',
    '4.7" Смартфон Apple iPhone SE 2020 128 ГБ черный',
    '6.1" Смартфон Huawei P40 128 ГБ серебристый',
    '6.1" Смартфон Huawei P40 128 ГБ черный',
    '5.5" Смартфон Apple iPhone 7 Plus 128 ГБ золотистый',
    '5.5" Смартфон Apple iPhone 7 Plus 128 Гб черный матовый',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ белый',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ зеленый',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ красный',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ оранжевый',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ розовый',
    '6.5" Смартфон Samsung Galaxy S20 FE 128 ГБ синий',
    '5.7" Смартфон ARCHOS Diamond Omega 128 ГБ синий',
    '5.84" Смартфон Blackview BV9900 Pro 128 ГБ черный',
    '6.47" Смартфон Xiaomi Mi Note 10 Pro 256 ГБ белый',
    '6.47" Смартфон Xiaomi Mi Note 10 Pro 256 ГБ черный',
    '6.7" Смартфон Samsung S10 Lite 128 ГБ белый',
    '6.7" Смартфон Samsung S10 Lite 128 ГБ синий',
    '6.7" Смартфон Samsung S10 Lite 128 ГБ черный',
    '5.8" Смартфон Apple iPhone X "Как новый" 256 ГБ серый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ белый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ желтый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ красный',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ оранжевый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ синий',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ черный',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ белый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ голубой',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ желтый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ коралловый',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ красный',
    '6.1" Смартфон Apple iPhone Xr 64 ГБ черный',
    '6.1" Смартфон Samsung Galaxy S10 128 ГБ белый',
    '6.1" Смартфон Samsung Galaxy S10 128 ГБ зеленый',
    '6.1" Смартфон Samsung Galaxy S10 128 ГБ красный',
    '6.1" Смартфон Samsung Galaxy S10 128 ГБ черный',
    '6.5" Смартфон Samsung Galaxy S20 FE 256 ГБ розовый',
    '6.5" Смартфон Samsung Galaxy S20 FE 256 ГБ синий',
    '6.57" Смартфон Honor 30 Pro+ 256 ГБ зеленый',
    '6.57" Смартфон Honor 30 Pro+ 256 ГБ серебристый',
    '6.57" Смартфон Honor 30 Pro+ 256 ГБ черный',
    '5.8" Смартфон Apple iPhone Xs "Как новый" 64 ГБ серый',
    '6.1" Смартфон Sony Xperia 5 128 ГБ синий',
    '6.3" Смартфон Samsung Galaxy Note 10 256 ГБ голубой',
    '6.3" Смартфон Samsung Galaxy Note 10 256 ГБ красный',
    '6.3" Смартфон Samsung Galaxy Note 10 256 ГБ черный',
    '6.47" Смартфон Huawei P30 Pro 256 ГБ голубой',
    '6.47" Смартфон Huawei P30 Pro 256 ГБ розовый',
    '6.47" Смартфон Huawei P30 Pro 256 ГБ синий',
    '6.47" Смартфон Huawei P30 Pro 256 ГБ черный',
    '6.81" Смартфон Nokia 8.3 128 ГБ синий',
    '4.7" Смартфон Apple iPhone SE 2020 256 ГБ белый',
    '4.7" Смартфон Apple iPhone SE 2020 256 ГБ красный',
    '4.7" Смартфон Apple iPhone SE 2020 256 ГБ черный',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ красный',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ синий',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ черный',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ белый',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ голубой',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ желтый',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ коралловый',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ красный',
    '6.1" Смартфон Apple iPhone Xr 128 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 64 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ желтый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ красный',
    '6.1" Смартфон Apple iPhone 11 64 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 64 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 64 ГБ черный',
    '6.5" Смартфон Apple iPhone Xs Max "Как новый" 64 ГБ серый',
    '6.53" Смартфон Huawei Mate 30 Pro 256 ГБ серебристый',
    '6.2" Смартфон Samsung Galaxy S20 128 ГБ голубой',
    '6.2" Смартфон Samsung Galaxy S20 128 ГБ красный',
    '6.2" Смартфон Samsung Galaxy S20 128 ГБ серый',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ белый',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ белый',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ зеленый',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ красный',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ черный',
    '6.4" Смартфон Samsung Galaxy S10+ 128 ГБ черный',
    '6.56" Смартфон Vivo X50 Pro 256 ГБ серый',
    '6.58" Смартфон Huawei P40 Pro 256 ГБ серебристый',
    '6.58" Смартфон Huawei P40 Pro 256 ГБ синий',
    '6.58" Смартфон Huawei P40 Pro 256 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 128 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ желтый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ красный',
    '6.1" Смартфон Apple iPhone 11 128 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 128 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 128 ГБ черный',
    '6.4" Смартфон Samsung Galaxy Note 9 128 ГБ черный',
    '5.4" Смартфон Apple iPhone 12 Mini 64 ГБ белый',
    '5.4" Смартфон Apple iPhone 12 Mini 64 ГБ зеленый',
    '5.4" Смартфон Apple iPhone 12 Mini 64 ГБ красный',
    '5.4" Смартфон Apple iPhone 12 Mini 64 ГБ синий',
    '6.1" Смартфон Apple iPhone Xr 256 ГБ белый',
    '6.1" Смартфон Apple iPhone Xr 256 ГБ голубой',
    '6.1" Смартфон Apple iPhone Xr 256 ГБ желтый',
    '6.1" Смартфон Apple iPhone Xr 256 ГБ коралловый',
    '6.1" Смартфон Apple iPhone Xr 256 ГБ красный',
    '6.5" Смартфон Apple iPhone Xs Max 64 ГБ серебристый',
    '6.5" Смартфон Apple iPhone Xs Max 64 ГБ серый',
    '5.8" Смартфон Apple iPhone Xs 256 ГБ серебристый',
    '5.8" Смартфон Apple iPhone Xs 256 ГБ серый',
    '6.4" Смартфон Samsung Galaxy Note 9 512 ГБ коричневый',
    '6.7" Смартфон Samsung Galaxy Note 20 256 ГБ зеленый',
    '6.7" Смартфон Samsung Galaxy Note 20 256 ГБ коричневый',
    '6.7" Смартфон Samsung Galaxy Note 20 256 ГБ серый',
    '6.7" Смартфон Samsung Galaxy S20+ 128 ГБ красный',
    '6.7" Смартфон Samsung Galaxy S20+ 128 ГБ серый',
    '6.7" Смартфон Samsung Galaxy S20+ 128 ГБ черный',
    '5.4" Смартфон Apple iPhone 12 Mini 128 ГБ белый',
    '5.4" Смартфон Apple iPhone 12 Mini 128 ГБ зеленый',
    '5.4" Смартфон Apple iPhone 12 Mini 128 ГБ красный',
    '5.4" Смартфон Apple iPhone 12 Mini 128 ГБ синий',
    '5.4" Смартфон Apple iPhone 12 Mini 128 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 256 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ белый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ желтый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ красный',
    '6.1" Смартфон Apple iPhone 11 256 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ фиолетовый',
    '6.1" Смартфон Apple iPhone 11 256 ГБ черный',
    '6.1" Смартфон Apple iPhone 11 256 ГБ черный',
    '6.1" Смартфон Sony Xperia 5 II 128 ГБ синий',
    '6.1" Смартфон Apple iPhone 12 64 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 12 64 ГБ красный',
    '6.1" Смартфон Apple iPhone 12 64 ГБ синий',
    '6.1" Смартфон Apple iPhone 12 64 ГБ черный',
    '6.5" Смартфон Apple iPhone Xs Max 512 ГБ серебристый',
    '6.1" Смартфон Apple iPhone 12 128 ГБ красный',
    '6.1" Смартфон Apple iPhone 12 128 ГБ синий',
    '6.1" Смартфон Apple iPhone 12 128 ГБ черный',
    '5.4" Смартфон Apple iPhone 12 Mini 256 ГБ белый',
    '5.4" Смартфон Apple iPhone 12 Mini 256 ГБ красный',
    '5.4" Смартфон Apple iPhone 12 Mini 256 ГБ синий',
    '5.4" Смартфон Apple iPhone 12 Mini 256 ГБ черный',
    '6.1" Смартфон Apple iPhone 12 128 ГБ белый',
    '5.8" Смартфон Apple iPhone 11 Pro 64 ГБ зеленый',
    '5.8" Смартфон Apple iPhone 11 Pro 64 ГБ золотистый',
    '5.8" Смартфон Apple iPhone 11 Pro 64 ГБ серебристый',
    '5.8" Смартфон Apple iPhone 11 Pro 64 ГБ серый',
    '5.8" Смартфон Apple iPhone Xs 512 ГБ золотистый',
    '5.8" Смартфон Apple iPhone Xs 512 ГБ серебристый',
    '5.8" Смартфон Apple iPhone Xs 512 ГБ серый',
    '6.59" Смартфон Asus ROG Phone 3 12Gb 512 ГБ черный',
    '6.7" Смартфон Samsung Galaxy S20+ BTS Edition 128 ГБ фиолетовый',
    '6.58" Смартфон Huawei P40 Pro+ 512 ГБ черный',
    '6.9" Смартфон Samsung Galaxy Note 20 Ultra 256 ГБ белый',
    '6.9" Смартфон Samsung Galaxy Note 20 Ultra 256 ГБ коричневый',
    '6.9" Смартфон Samsung Galaxy Note 20 Ultra 256 ГБ черный',
    '6.9" Смартфон Samsung Galaxy S20 Ultra 128 ГБ белый',
    '6.9" Смартфон Samsung Galaxy S20 Ultra 128 ГБ серый',
    '6.9" Смартфон Samsung Galaxy S20 Ultra 128 ГБ черный',
    '6.1" Смартфон Apple iPhone 12 256 ГБ зеленый',
    '6.1" Смартфон Apple iPhone 12 256 ГБ красный',
    '6.1" Смартфон Apple iPhone 12 256 ГБ синий',
    '6.1" Смартфон Apple iPhone 12 256 ГБ черный',
    '6.5" Смартфон Apple iPhone 11 Pro Max 64 ГБ зеленый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 64 ГБ золотистый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 64 ГБ серебристый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 64 ГБ серый',
    '5.8" Смартфон Apple iPhone 11 Pro 256 ГБ зеленый',
    '5.8" Смартфон Apple iPhone 11 Pro 256 ГБ золотистый',
    '5.8" Смартфон Apple iPhone 11 Pro 256 ГБ серебристый',
    '5.8" Смартфон Apple iPhone 11 Pro 256 ГБ серый',
    '6.7" Смартфон Samsung Galaxy Flip Z 256 ГБ фиолетовый',
    '6.9" Смартфон Samsung Galaxy Note 20 Ultra 512 ГБ коричневый',
    '6.9" Смартфон Samsung Galaxy Note 20 Ultra 512 ГБ черный',
    '6.5" Смартфон Apple iPhone 11 Pro Max 256 ГБ зеленый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 256 ГБ золотистый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 256 ГБ серый',
    '5.8" Смартфон Apple iPhone 11 Pro 512 ГБ зеленый',
    '5.8" Смартфон Apple iPhone 11 Pro 512 ГБ золотистый',
    '5.8" Смартфон Apple iPhone 11 Pro 512 ГБ серебристый',
    '5.8" Смартфон Apple iPhone 11 Pro 512 ГБ серый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 512 ГБ зеленый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 512 ГБ золотистый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 512 ГБ серебристый',
    '6.5" Смартфон Apple iPhone 11 Pro Max 512 ГБ серый',
    '7.6" Смартфон Samsung Galaxy Z Fold2 256 ГБ коричневый',
    '7.6" Смартфон Samsung Galaxy Z Fold2 256 ГБ черный',
)

models1 = ('4" Смартфон INOI 1 Lite 4 ГБ черный',
           '6.95" Смартфон Tecno Spark 5 Air 32 ГБ зеленый',
           '6.53" Смартфон Xiaomi Redmi 9C NFC 64 ГБ оранжевый',
           '6.5" Смартфон Samsung Galaxy A21s 32 ГБ красный',
           '7.6" Смартфон Samsung Galaxy Z Fold2 256 ГБ коричневый',
           '6.5" Смартфон realme 6 4/128 ГБ синий',
           '4.7" Смартфон Apple iPhone 7 32 Гб черный матовый',
           '6.18" Смартфон Pocophone F1 64 ГБ синий')

if __name__ == '__main__':
    time_start = time.time()

    import main
    main.load_exceptions_model_names()
    main.read_config()

    # for item in models1:
    #     print(dns_parse_model_name('', item))

    print(dns_parse_model_name("BQ", '5.45" Смартфон bright & quick BQ-5519G JEANS 16 ГБ зеленый'))

    # parser = DNSParse()
    # result = parser.run_catalog(
    #     "https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")

    # result = load_result_from_csv()
    # check = checker.Checker(result)
    # res1 = check.run()
    #
    # bot = bot.Bot()
    # bot.run(res1)
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

import time
import re
import csv
import datetime

import bs4
import selenium.common.exceptions as se
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.action_chains import ActionChains

import bd
import header as h

logger = h.logging.getLogger('mvideoparse')


# Парсинг названия модели (получить название модели, цвет и ROM)
def mvideo_parse_model_name(name):
    # Защита от неправильных названий
    if len(name.split()) < 5:
        return "error", "error", "error"
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = ' восст.' if (' восст.' in name) else ''
    name = name.replace(rebuilt, '')
    # Оборачивание скобками названия модели, если их не было
    last_word = name.split()[-1]
    if last_word.isupper() and \
            not ('(' in last_word) and \
            not (')' in last_word):
        name = name.replace(last_word, '({})'.format(last_word))
    # Понижение регистра
    name = str.lower(name)
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Получить размер ROM
    rom = re.findall(r'\d*\+*\d+(?:gb|tb)', name)
    rom = (rom[0]) if rom else ""
    # Получить 2 слова цвета
    color1, color2 = name.split()[-2:] if name.split()[-1] != rom \
        else name.split()[-3:-1]
    # Если первое слово цвета состоит только из букв и длиннее 2 символов - добавить к итоговому цвету
    color = color1 + " " + color2 if (color1.isalpha() and len(color1) > 2) else color2
    # Удалить первую часть часть
    name = name.replace('смартфон', '').replace(rom, '').replace('  ', ' ')
    # Получить название бренда
    brand_name = name.split()[0]
    # Убрать вторую часть лишних слов из названия
    name = name.replace(color, '').replace(brand_name, '').strip()

    return brand_name, (name + rebuilt), color


# Парсер МВидео
class MVideoParse:

    def __init__(self):
        options = Options()
        options.add_argument("window-size=1920,1080")
        # options.add_experimental_option('prefs', {'geolocation': True})
        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.driver.implicitly_wait(1.5)
        self.cur_page = 1
        self.result = []
        self.price_changes = []
        self.domain = "https://www.mvideo.ru"
        self.shop = "мвидео"
        self.db = bd.DataBase()

    # Обертка поиска элемента для обработки исключений
    def __wd_find_elem(self, by, value):
        try:
            result = self.driver.find_element(by, value)
            return result
        except se.NoSuchElementException:
            return None

    # Поиск одного элемента с таймаутом
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
        # TODO: доделать обертку try-except
        ActionChains(self.driver).move_to_element(elem).send_keys(keys).perform()
        return True

    # Обертка для клика по элементу через ActionChains
    def __wd_click_elem(self, elem):
        if not elem:
            return False

        # TODO: доделать обертку try-except
        ActionChains(self.driver).move_to_element(elem).click().perform()
        return True

    # Алгоритм выбора города для всех возможных ситуаций для страницы каталога
    def __wd_city_selection_catalog(self):
        city = self.__wd_find_elem_with_timeout(By.XPATH, "//button[@class='region-selection__select']")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (str.lower(h.CURRENT_CITY) in str.lower(city.text)):

            # Клик по городу
            if not self.__wd_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "city-list__item")
            if city_list:
                for item in city_list:
                    # if str.lower(item.text).find(str.lower(h.CURRENT_CITY)) != -1:
                    if str.lower(h.CURRENT_CITY) in str.lower(item.text):
                        time.sleep(1.5)
                        return self.__wd_click_elem(item)
            else:
                logger.warning("Нет списка городов, попробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.XPATH, "//input[@class='base-input find-input__input']")
            if not input_city:
                logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Ввод названия города по буквам
            for char in h.CURRENT_CITY:
                self.__wd_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//li[@class='city-list__item']/a")
            if not input_city_item:
                logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_click_elem(input_city_item):
                logger.error("Не могу нажать на выбранный город")
                return False

        return True

    # Алгоритм выбора города для всех возможных ситуаций для страницы продукта
    def __wd_city_selection_product(self):
        city = self.__wd_find_elem_with_timeout(By.ID, "header-city-selection-link")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (str.lower(h.CURRENT_CITY) in str.lower(city.text)):

            # Клик по городу
            if not self.__wd_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "city-selection-popup-results")
            if city_list:
                city_list = self.__wd_find_all_elems_with_timeout(By.XPATH, "//li")
                for item in city_list:
                    if str.lower(h.CURRENT_CITY) in str.lower(item.text):
                        time.sleep(1.5)
                        return self.__wd_click_elem(item)
            else:
                logger.warning("Нет списка городов, попробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.ID, "region-selection-form-city-input")
            if not input_city:
                logger.error("Не найдено поле, куда вводить новый город")
                return False

            self.__wd_click_elem(input_city)
            time.sleep(1.5)
            # Ввод названия города по буквам
            for char in h.CURRENT_CITY:
                self.__wd_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//a[@class='sel-droplist-cities']")
            if not input_city_item:
                logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_click_elem(input_city_item):
                logger.error("Не могу нажать на выбранный город")
                return False

        return True

    # Проверка по ключевым div-ам что страница каталога прогружена полностью
    def __wd_check_load_page_catalog(self):
        # Ожидание прогрузки пагинации
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "pagination__group"):
            return False

        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "price__actual-price"):
            return False

        # Ожидание прогрузки изображения товара
        if not self.__wd_find_elem_with_timeout(By.XPATH,
                                                "//img[@class='product-picture__picture product-picture__filler']"):
            return False

        # Ожидание прогрузки переключателя вида товара
        if not self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='listing-views__inner-area']"):
            return False

        print("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница товара прогружена полностью
    def __wd_check_load_page_product(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "fl-pdp-price__current"):
            return False

        # Ожидание прогрузки изображения товара
        if not self.__wd_find_elem_with_timeout(By.XPATH, "//img[@class='c-media-container__image']"):
            return False

        print("PAGE LOAD")
        return True

    # Переключение на отображение товаров в виде списка
    def __wd_mvideo_select_list_view(self):
        # Если есть этот тег в html коде, значит сейчас стоит табличный вид, переключаем на список
        if self.__wd_find_elem(By.XPATH, "//div[@class='listing-views__pointer listing-views__pointer--grid']"):
            # Переключение с табличного вида на список
            listing_views = self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='listing-views__inner-area']")
            if not listing_views:
                logger.error("Не могу найти listing views")
                return False

            # Клик
            if not self.__wd_click_elem(listing_views):
                logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

        # Но если нет и тега list (вид списка) - то ошибка
        elif not self.__wd_find_elem(By.XPATH,
                                     "//div[@class='listing-views__pointer listing-views__pointer--list']"):
            logger.error("Не вижу тегов для переключения вида товара")
            return False

        return True

    # Запуск браузера, загрузка начальной страницы каталога, выбор города
    def __wd_open_browser_catalog(self, url):
        self.driver.get(url)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (1)")
            return False

        # Выбор города (срабатывает не всегда с первого раза)
        if not self.__wd_city_selection_catalog():
            print("Не могу выбрать город")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        # Переключение на отображение товаров в виде списка
        if not self.__wd_mvideo_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (3)")
            return False

        return True

    # Запуск браузера, загрузка начальной страницы парсинга, выбор города
    def __wd_open_browser_product(self, url):
        self.driver.get(url)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_product():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (1)")
            return False

        # Выбор города
        if not self.__wd_city_selection_product():
            print("Не могу выбрать город")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_product():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        return True

    # Получить текущий код страницы
    def __wd_get_cur_page(self):
        return self.driver.page_source

    # Переход на заданную страницу num_page через клик (для имитации пользователя)
    def __wd_next_page(self):
        self.cur_page += 1

        # Поиск следующей кнопки страницы
        num_page_elem = self.__wd_find_elem(By.XPATH, f"//div[@class='pagination__group']/a[text()={self.cur_page}]")
        if not num_page_elem:
            logger.info("Достигнут конец каталога")
            return False

        # Клик - переход на следующую страницу
        if not self.__wd_click_elem(num_page_elem):
            logger.error("Не могу кликнуть на страницу в __wd_next_page")
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page")
            return False

        # Переключение на отображение товаров в виде списка
        if not self.__wd_mvideo_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        # Особенность МВидео - при переключении страницы, пока сайт ждет ответ от сервера,
        # оставляет старые данные с эффектом размытия. Ждем, пока они не исчезнут
        self.wait.until_not(ec.presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
            self.result[-1].url.replace(self.domain, '')))))
        # Тоже особенность МВидео - данные могут прогрузится, а цены нет, будут висеть 9999 с эффектом размытия.
        self.wait.until_not(ec.presence_of_element_located((By.CLASS_NAME,
                                                            "price-block with-blur product-list-card__price")))

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page / товар распродан (нет цен на всей странице)")
            return False

        # Специальная задержка между переключениями страниц для имитации юзера
        time.sleep(h.WAIT_BETWEEN_PAGES_SEC)
        return True

    # Завершение работы браузера
    def __wd_close_browser(self):
        logger.info("Завершение работы")
        self.driver.quit()

    # Метод для парсинга html страницы продукта
    def __parse_product_page(self, html, url):
        soup = bs4.BeautifulSoup(html, 'lxml')
        product_block = soup.select_one("div.main-holder")

        # Категория
        category = product_block.select_one('meta[itemprop="category"]')
        if not category:
            logger.error("No brand name")
            category = "error"
        else:
            category = category.get('content').strip()

        # Бренд
        brand_name = product_block.select_one('meta[itemprop="brand"]')
        if not brand_name:
            logger.error("No brand name")
            brand_name = "error"
        else:
            brand_name = brand_name.get('content').strip()

        # Название модели
        model_name = product_block.select_one('h1.e-h1.sel-product-title')
        if not model_name:
            logger.error("No model name")
            model_name = "error"
        else:
            model_name = model_name.text.strip()

        # Ссылка на изображение
        img_url = product_block.select_one('img.c-media-container__image')
        if not img_url:
            logger.error("No img url")
            img_url = "error"
        else:
            img_url = img_url.get('src')

        # RAM и ROM
        ram, rom = 0, 0
        specifications = product_block.select_one('table.c-specification__table')
        if not specifications:
            logger.error("No specifications")
        else:
            specifications = specifications.select('tr')
            for item in specifications:
                if "ram" in str.lower(item.text):
                    ram = int(re.findall(r'\d+', item.text)[0])
                if "rom" in str.lower(item.text):
                    rom = int(re.findall(r'\d+', item.text)[0])

        # Код продукта
        product_code = product_block.select_one('p.c-product-code')
        if not product_code:
            logger.error("No product code")
            product_code = "error"
        else:
            product_code = product_code.text.replace(' ', '')

        # Цена
        price = product_block.select_one('div.fl-pdp-price__current')
        if not price:
            logger.error("No price")
            price = 0
        else:
            price = re.findall(r'\d+', price.text)
            price = int(''.join(str(x) for x in price))

        # Рейтинг
        rating = product_block.select_one('span.c-star-rating__stars.c-star-rating__stars_active.font-icon.icon-star')
        if not rating:
            rating = 0
        else:
            rating = float(re.findall(r'\d+', rating.get('style'))[0])
            rating = (5.0 * rating / 100.0) if (rating and rating != 1) else 0

        # На основании скольки отзывов построен рейтинг
        num_rating = product_block.select_one('span.c-star-rating_reviews-qty')
        if not num_rating:
            num_rating = 0
        else:
            num_rating = int(re.findall(r'\d+', num_rating.text.replace(' ', ''))[0])

        brand_name, model_name, color = mvideo_parse_model_name(model_name) \
            if model_name != "error" \
            else ("error", "error", "error")

        # Добавление полученных результатов в коллекцию
        self.result.append(h.ParseResult(
            shop=self.shop,
            category=str.lower(category),
            brand_name=str.lower(brand_name),
            model_name=str.lower(model_name),
            color=str.lower(color),
            price=price,
            ram=ram,
            rom=rom,
            img_url=str.lower(img_url),
            url=str.lower(url),
            rating=rating,
            num_rating=num_rating,
            product_code=str.lower(product_code),
        ))

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
        container = soup.select('div.products-raw')
        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):
        # Название модели и URL
        model_name_url_block = block.select_one('a.product-title.product-title--clamp')
        if not model_name_url_block:
            logger.error("No model name and URL")
            model_name = "error"
            url = "error"
        else:
            url = self.domain + model_name_url_block.get('href')
            model_name = model_name_url_block.text.replace('\n', '').strip()

        # Ссылка на изображение товара
        img_url = block.select_one('img.product-picture__picture.product-picture__filler')
        if not img_url:
            logger.error("No img url")
            img_url = "error"
        else:
            img_url = img_url.get('src')

        # Рейтинг товара
        rating = block.select_one('span.star-rating__stars')
        if not rating:
            rating = 0
        else:
            rating = re.findall(r'\d+.\d+', rating.text)
            rating = rating[0] if rating else 0

        # На основании скольки отзывов построен рейтинг
        num_rating = block.select_one('span.star-rating__reviews')
        if not num_rating:
            num_rating = 0
        else:
            num_rating = re.findall(r'\d+', num_rating.text)
            num_rating = num_rating[0] if num_rating else 0

        # Парсинг значений RAM и ROM
        ram, rom = 0, 0
        specifications = block.select('div.product-feature-list__item')
        if not specifications:
            logger.error("No RAM and ROM")
        else:
            for item in specifications:
                if "ram" in str.lower(item.text):
                    ram = int(re.findall(r'\d+', item.text)[0])
                if "rom" in str.lower(item.text):
                    rom = int(re.findall(r'\d+', item.text)[0])

        # Парсинг цен
        promo_price = block.select_one('div.promo__price')
        # Если есть блок акции - берем цену с него
        if promo_price:
            price = int(re.findall(r'\d+', promo_price.text.replace(' ', ''))[0])
        else:
            price = block.select_one('div.price__actual-price')
            if not price:
                logger.error("No price")
                price = 0
            else:
                price = int(re.findall(r'\d+', price.text.replace(' ', ''))[0])

        # Код продукта
        product_code = url[-8:] if len(url) > 8 else "error"

        # Парсинг полученных данных
        brand_name, model_name, color = mvideo_parse_model_name(model_name) \
            if model_name != "error" \
            else ("error", "error", "error")

        # Добавление полученных результатов в коллекцию
        self.result.append(h.ParseResult(
            shop=self.shop,
            category=str.lower(self.category),
            brand_name=str.lower(brand_name),
            model_name=str.lower(model_name),
            color=str.lower(color),
            price=price,
            ram=ram,
            rom=rom,
            img_url=str.lower(img_url),
            url=str.lower(url),
            rating=rating,
            num_rating=num_rating,
            product_code=str.lower(product_code),
        ))

    # Сохранение всего результата в csv файл
    def __save_result(self):
        with open(h.CSV_PATH, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS)
            for item in self.result:
                writer.writerow(item)

    # Сохранение списка товаров, у которых изменились цены в csv
    def __save_price_changes(self):
        if not self.price_changes:
            logger.info("НЕТ ЗАПИСЕЙ С ИЗМЕНЕНИЕМ ЦЕН")
            return

        with open(h.PRICE_CHANGES_PATH, 'w', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(h.HEADERS_PRICE_CHANGES)
            for item in self.price_changes:
                writer.writerow(item)

    # Сохранение всех запарсенных данных в SQL
    def __save_result_in_db(self):
        for item in self.result:
            if not bd.check_item_on_errors(item):
                logger.error("Продукт {} {} с артиклом {} в магазине {} содержит 'error' или 0, SKIP".format(
                    item.brand_name, item.model_name, item.product_code, item.shop))
                continue

            # Сохранение данных в базу. Если цена изменилась - вернет предыдущую
            prev_price = self.db.add_product_to_bd(
                category_name=item.category,
                shop_name=item.shop,
                brand_name=item.brand_name,
                model_name=item.model_name,
                var_color=item.color,
                var_ram=item.ram,
                var_rom=item.rom,
                price=item.price,
                img_url=item.img_url,
                url=item.url,
                product_code=item.product_code,
                local_rating=item.rating,
                num_rating=item.num_rating)

            # Если выявлено изменение цены - записать в список
            if prev_price:
                self.price_changes.append(h.PriceChanges(
                    shop=item.shop,
                    category=item.category,
                    brand_name=item.brand_name,
                    model_name=item.model_name,
                    color=item.color,
                    ram=item.ram,
                    rom=item.rom,
                    img_url=item.img_url,
                    url=item.url,
                    rating=item.rating,
                    num_rating=item.num_rating,
                    product_code=item.product_code,
                    date_time=datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
                    cur_price=item.price,
                    prev_price=prev_price,
                    diff=item.price - prev_price,
                ))

    # Запуск работы парсера для каталога
    def run_catalog(self, url, cur_page=None):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        if not self.__wd_open_browser_catalog(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return

        if cur_page:
            self.cur_page = cur_page

        while True:
            html = self.__wd_get_cur_page()
            self.__parse_catalog_page(html)
            if not self.__wd_next_page():
                break

        self.__wd_close_browser()
        self.__save_result_in_db()
        self.__save_result()
        self.__save_price_changes()
        self.db.disconnect()

    # Запуск работы парсера для продукта
    def run_product(self, url):
        self.db.connect_or_create("parser", "postgres", "1990", "127.0.0.1", "5432")

        if not self.__wd_open_browser_product(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return

        html = self.__wd_get_cur_page()
        self.__parse_product_page(html, url)
        self.__wd_close_browser()
        print(self.result[0])
        self.__save_result()
        self.__save_result_in_db()
        self.db.disconnect()


models = ('Смартфон Samsung Galaxy S10 Оникс',
          'Смартфон Samsung Galaxy A20s Blue 32GB (SM-A207F/DS)',
          'Смартфон Huawei P40 Lite Crush Green (JNY-LX1)',
          'Смартфон Apple iPhone 11 128GB (PRODUCT)RED (MWM32RU/A )',
          'Смартфон Samsung Galaxy A50 (2019) 64GB Black (SM-A505FN)',
          'Смартфон Samsung Galaxy A20s Red 32GB (SM-A207F/DS)',
          'Смартфон Samsung Galaxy A50 (2019) 64GB Black ( SM-A505FN)',
          'Смартфон Honor 30i 128GB Phantom Blue (LRA-LX1)',
          'Смартфон Huawei Nova 5T Crush Blue (YAL-L21)',
          'Смартфон Apple iPhone 8 Plus 128GB Silver (MX252RU/A )',
          'Смартфон Apple iPhone 7 32Gb Rose Gold ( MN912RU/A )',
          'Смартфон Huawei P40 Lite Midnight Black (JNY-LX1)',
          'Смартфон Apple iPhone XS 64Gb Space Grey (FT9E2RU/A) восст.',
          'Смартфон Apple iPhone SE (2020) 64GB White MX9T2RU/A',
          'Смартфон Xiaomi Redmi 9C NFC 3+64GB Twilight Blue',
          'Смартфон Honor 30i 4+128GB Phantom Blue (LRA-LX1)',
          'Смартфон Xiaomi Redmi Note 8 Pro Mineral Grey 6+128GB (LKD-42)',
          'Смартфон Samsung Galaxy S10+ Ceramic 1TB (SM-G975F/DS)',)

if __name__ == '__main__':
    time_start = time.time()
    parser = MVideoParse()
    parser.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
    # parser.run_product("https://www.mvideo.ru/products/smartfon-zte-blade-l130-blue-30044612")
    print(f"Время выполнения: {time.time() - time_start} сек")

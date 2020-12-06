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
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import header as h

logger = h.logging.getLogger('mvideoparse')
MVIDEO_REBUILT_IPHONE = ' восст.'


# Парсинг названия модели (получить название модели, цвет и ROM)
def mvideo_parse_model_name(name):
    # Защита от неправильных названий
    if len(name.split()) < 5:
        return None, None, None
    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (MVIDEO_REBUILT_IPHONE in name.lower()) else ''
    name = name.replace(rebuilt, '')
    # Оборачивание скобками названия модели, если их не было
    last_word = name.split()[-1]
    if last_word.isupper() and \
            not ('(' in last_word) and \
            not (')' in last_word):
        name = name.replace(last_word, '({})'.format(last_word))
    # Понижение регистра
    name = str.lower(name)
    # Удалить nfc и 5g
    name = name.replace(' nfc ', '').replace(' 5g ', ' ')
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Получить размер ROM
    rom = re.findall(r'\d*\+*\d+(?:gb|tb)', name)
    rom = (rom[0]) if rom else ""
    # Получить ЦВЕТ
    # Получить 2 слова цвета
    color1, color2 = name.split()[-2:] if name.split()[-1] != rom \
        else name.split()[-3:-1]
    # Если первое слово цвета состоит только из букв и длиннее 2 символов и отсутствует в игнор-листе - добавить
    # к итоговому цвету
    color1 = color1 if (color1.isalpha() and len(color1) > 2 and not (color1.strip() in h.IGNORE_WORDS_FOR_COLOR)) else ""
    color = color1 + " " + color2 if (color1.isalpha() and len(color1) > 2) else color2

    # Удалить первую часть часть
    name = name.replace('смартфон', '').replace(rom, '').replace(year, '').replace('  ', ' ')
    # Получить название бренда
    brand_name = name.split()[0]
    # Убрать вторую часть лишних слов из названия
    name = name.replace(color, '').replace(brand_name, '').replace('  ', ' ').strip()

    return brand_name, (name + rebuilt), color


# Парсер МВидео
class MVideoParse:

    def __init__(self):
        options = Options()
        options.add_argument("window-size=1920,1080")
        options.add_argument("--disable-notifications")
        # options.add_experimental_option('prefs', {'geolocation': True})
        self.driver = webdriver.Chrome(executable_path=h.WD_PATH, options=options)
        self.driver.implicitly_wait(1.5)
        self.wait = WebDriverWait(self.driver, 15)
        self.cur_page = 1
        self.pr_result_list = []
        # Данные магазина
        self.domain = "https://www.mvideo.ru"
        self.shop = "мвидео"
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.current_city = self.config.defaults()['current_city']
        self.wait_between_pages_sec = int(self.config.defaults()['wait_between_pages_sec'])

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
        city = self.__wd_find_elem_with_timeout(By.XPATH, "//span[@class='location-text top-navbar-link']")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (str.lower(self.current_city) in str.lower(city.text)):
            logger.info("Неверный город")

            # Клик по городу
            if not self.__wd_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "location-select__location")
            if city_list:
                for item in city_list:
                    if str.lower(self.current_city) in str.lower(item.text):  #
                        time.sleep(1.5)
                        return self.__wd_click_elem(item)
            else:
                logger.warning("Нет списка городов, попробую вбить вручную")

            logger.warning("Не вижу нужный город в списке, пробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.CLASS_NAME, "location-select__input-wrap")
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
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//li[@data-index='0']")
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
        return True
        city = self.__wd_find_elem_with_timeout(By.ID, "header-city-selection-link")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if not (str.lower(self.current_city) in str.lower(city.text)):

            # Клик по городу
            if not self.__wd_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "city-selection-popup-results")
            if city_list:
                city_list = self.__wd_find_all_elems_with_timeout(By.XPATH, "//li")
                for item in city_list:
                    if str.lower(self.current_city) in str.lower(item.text):
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
            for char in self.current_city:
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
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "pagination"):
            return False

        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "price__main-value"):
            return False

        # Ожидание прогрузки изображения товара
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "product-picture__img"):
            return False

        # Ожидание прогрузки переключателя вида товара
        if not self.__wd_find_elem_with_timeout(By.XPATH, "//div[@class='listing-view-switcher__inner-area']"):
            return False

        logger.info("PAGE LOAD")
        return True

    # Проверка по ключевым div-ам что страница товара прогружена полностью
    def __wd_check_load_page_product(self):
        # Ожидание прогрузки цен
        if not self.__wd_find_elem_with_timeout(By.CLASS_NAME, "fl-pdp-price__current"):
            return False

        # Ожидание прогрузки изображения товара
        if not self.__wd_find_elem_with_timeout(By.XPATH, "//img[@class='c-media-container__image']"):
            return False

        logger.info("PAGE LOAD")
        return True

    # Переключение на отображение товаров в виде списка
    def __wd_mvideo_select_list_view(self):
        # Если есть этот тег в html коде, значит сейчас стоит табличный вид, переключаем на список
        if self.__wd_find_elem(By.XPATH,
                               "//div[@class='listing-view-switcher__pointer listing-view-switcher__pointer--grid']"):
            # Переключение с табличного вида на список
            listing_views = self.__wd_find_elem_with_timeout(By.XPATH,
                                                             "//div[@class='listing-view-switcher__inner-area']")
            if not listing_views:
                logger.error("Не могу найти listing views")
                return False

            # Клик
            if not self.__wd_click_elem(listing_views):
                logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

        # Но если нет и тега list (вид списка) - то ошибка
        elif not self.__wd_find_elem(By.XPATH,
                                     "//div[@class='listing-view-switcher__pointer listing-view-switcher__pointer--list']"):
            logger.error("Не вижу тегов для переключения вида товара")
            return False

        return True

    # Скролл вниз для прогрузки товаров на странице
    def __wd_mvideo_scroll_down(self):
        for i in range(13):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.3)

        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
            return False

        return True

    # Запуск браузера, загрузка начальной страницы каталога, выбор города
    def __wd_open_browser_catalog(self, url):
        self.driver.get(url)

        # Ждем, пока не прогрузится страница, даем 3 попытки, т.к. сайт при первом запуске часто выдает пустую страницу
        for i in range(3):
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_open_browser (1), пробую обновить")
                self.driver.refresh()
            else:
                break
        else:
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (1)")
            return False

        # Выбор города (срабатывает не всегда с первого раза)
        if not self.__wd_city_selection_catalog():
            logger.info("Не могу выбрать город")
            return False

        time.sleep(1)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        # Переключение на отображение товаров в виде списка
        if not self.__wd_mvideo_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        time.sleep(1)

        # Ждем, пока не прогрузится страница
        if not self.__wd_mvideo_scroll_down():
            logger.error("Не удалось прогрузить страницу после скролла в __wd_open_browser (3)")
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
            logger.info("Не могу выбрать город")
            return False

        time.sleep(1)

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
        num_page_elem = self.__wd_find_elem(By.XPATH, f"//li[@class='page-item number-item ng-star-inserted']/a[text()={self.cur_page}]")
        if not num_page_elem:
            logger.info("Достигнут конец каталога")
            return False

        # Клик - переход на следующую страницу
        if not self.__wd_click_elem(num_page_elem):
            logger.error("Не могу кликнуть на страницу в __wd_next_page")
            return False

        # Ждем, пока не прогрузится страница
        for i in range(3):
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (2) / товар распродан (нет цен на всей странице), обновляю")
                self.driver.refresh()
            else:
                break
        else:
            return False

        # Переключение на отображение товаров в виде списка
        if not self.__wd_mvideo_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        try:
            # Особенность МВидео - при переключении страницы, пока сайт ждет ответ от сервера,
            # оставляет старые данные с эффектом размытия. Ждем, пока они не исчезнут
            self.wait.until_not(ec.presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                self.pr_result_list[-1].url))))
            # Тоже особенность МВидео - данные могут прогрузится, а цены нет, будут висеть 9999 с эффектом размытия.
            # self.wait.until_not(ec.presence_of_element_located((By.CLASS_NAME,
            #                                                     "price-block with-blur product-list-card__price")))
        except se.TimeoutException:
            logger.error('Не пропадает телефон с прошлой страницы, не могу прогрузить текущую')
            return False

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_next_page / товар распродан (нет цен на всей странице)")
            return False

        # Скролл вниз и ожидание прогрузки страницы
        if not self.__wd_mvideo_scroll_down():
            logger.error("Не удалось прогрузить страницу после скролла в __wd_next_page (1)")
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
        self.pr_result_list.append(h.ParseResult(
            shop=self.shop,
            category=str.lower(category),
            brand_name=str.lower(brand_name),
            model_name=str.lower(model_name),
            color=str.lower(color),
            cur_price=price,
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
        container = soup.select('div.product-cards-layout__item')

        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):
        # Название модели и URL
        model_name_url_block = block.select_one('a.product-title__text')

        if 'pda' in model_name_url_block.text.lower():
            logger.warning("PDA detected")
            return

        if not model_name_url_block:
            logger.warning("No model name and URL")
            return
        else:
            url = model_name_url_block.get('href')
            model_name = model_name_url_block.text.replace('\n', '').strip()

        # Ссылка на изображение товара
        img_url = block.select_one('img.product-picture__img.product-picture__img--list')
        if not img_url:
            logger.warning("No img url")
            return
        else:
            img_url = img_url.get('src')
            if img_url.startswith("//"):
                img_url = "https:" + img_url

        # Рейтинг товара
        rating = block.select_one('span.stars-container')
        if not rating:
            rating = 0
        else:
            rating = re.findall(r'\d+.\d+', rating.text)
            rating = rating[0] if rating else 0

        # На основании скольки отзывов построен рейтинг
        num_rating = block.select_one('span.product-rating__feedback.product-rating__feedback--with-link')
        if not num_rating:
            num_rating = 0
        else:
            num_rating = re.findall(r'\d+', num_rating.text)
            num_rating = num_rating[0] if num_rating else 0

        # Парсинг значений RAM и ROM
        ram, rom = 0, 0
        specifications = block.select('li.product-feature-list__item.product-feature-list__item--undefined')
        if not specifications:
            logger.warning("No RAM and ROM")
        else:
            for item in specifications:
                if "ram" in str.lower(item.text):
                    ram = int(re.findall(r'\d+', item.text)[0])
                if "rom" in str.lower(item.text):
                    rom = int(re.findall(r'\d+', item.text)[0])

        # Парсинг цен
        promo_price = block.select_one('span.price__main-value.price__main-value--old')
        # Если есть блок акции - берем цену с него
        if promo_price:
            price = int(re.findall(r'\d+', promo_price.text.replace(u'\xa0', ''))[0])
        else:
            price = block.select_one('span.price__main-value')
            if not price:
                logger.warning("No price")
                return
            else:
                price = int(re.findall(r'\d+', price.text.replace(u'\xa0', ''))[0])

        # Код продукта
        if len(url) > 8:
            product_code = url[-8:]
        else:
            logger.warning("No product code")
            return

        # Парсинг полученных данных
        brand_name, model_name, color = mvideo_parse_model_name(model_name)
        if not brand_name or \
                not model_name or \
                not color:
            logger.warning("No brand name, model name or color")
            return

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
            img_url=img_url.lower(),
            url=url.lower(),
            rating=rating,
            num_rating=num_rating,
            product_code=product_code.lower(),
        ))

    # Сохранение всего результата в csv файл
    def __save_result(self):
        with open(h.CSV_PATH_RAW + "mvideo.csv", 'w', newline='') as f:
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
        if not self.__wd_open_browser_product(url):
            logger.error("Open browser fail")
            self.__wd_close_browser()
            return None

        html = self.__wd_get_cur_page()
        self.__parse_product_page(html, url)
        self.__wd_close_browser()
        self.__save_result()
        return self.pr_result_list


models = (
    'Смартфон Vertex Impress Luck 3G Gold',
    'Смартфон Vertex Impress Luck 3G Black',
    'Смартфон ZTE Blade L130 Blue',
    'Смартфон ZTE Blade L130 Black',
    'Смартфон Samsung Galaxy A01 Core Black (SM-A013F/DS)',
    'Смартфон Huawei Y5 Lite Amber Brown (DRA-LX5)',
    'Смартфон Samsung Galaxy A01 Core Red (SM-A013F/DS)',
    'Смартфон Huawei Y5 Lite Modern Black (DRA-LX5)',
    'Смартфон ZTE Blade A3 2020 NFC Dark Grey',
    'Смартфон ZTE Blade A3 2020 NFC Violet',
    'Смартфон Samsung Galaxy A01 Core Blue (SM-A013F/DS)',
    'Смартфон Nokia 1.3 16GB Charcoal (TA-1205)',
    'Смартфон Nokia 1.3 16GB Cyan (TA-1205)',
    'Смартфон Samsung Galaxy A01 Black (SM-A015F/DS)',
    'Смартфон Samsung Galaxy A01 Red (SM-A015F/DS)',
    'Смартфон Samsung Galaxy A01 Blue (SM-A015F/DS)',
    'Смартфон Honor 9S Black (DUA-LX9)',
    'Смартфон Honor 9S Red (DUA-LX9)',
    'Смартфон Honor 9S Blue (DUA-LX9)',
    'Смартфон Huawei Y5p Midnight Black (DRA-LX9)',
    'Смартфон Huawei Y5p Mint Green (DRA-LX9)',
    'Смартфон Huawei Y5p Phantom Blue (DRA-LX9)',
    'Смартфон Xiaomi Redmi 7A 32GB Gem Blue',
    'Смартфон Xiaomi Redmi 9A 32GB Granite Gray',
    'Смартфон Xiaomi Redmi 9A 32GB Peacock Green',
    'Смартфон Xiaomi Redmi 9A 32GB Sky Blue',
    'Смартфон vivo Y91C Черный океан (1820)',
    'Смартфон Samsung Galaxy A10 (2019) 32Gb Black (SM-A105F)',
    'Смартфон Samsung Galaxy A10 (2019) 32Gb Blue (SM-A105F)',
    'Смартфон vivo Y91C Красный закат (1820)',
    'Смартфон vivo Y1S Оливковый чёрный (2015)',
    'Смартфон Huawei Y6 2019 Classic Black (MRD-LX1F)',
    'Смартфон Huawei Y6 2019 (MRD-LX1F) Amber Brown',
    'Смартфон vivo Y1S Синяя волна (2015)',
    'Смартфон Huawei Y5 2019 Sapphire Blue (AMN-LX9)',
    'Смартфон Huawei Y5 2019 Classic Black (AMN-LX9)',
    'Смартфон Huawei Y5 2019 AmberBrown (AMN-LX9)',
    'Смартфон Realme C11 2+32GB Mint Green (RMX2185)',
    'Смартфон Realme C11 2+32GB Pepper Grey (RMX2185)',
    'Смартфон Nokia 2.3 Green (TA-1206)',
    'Смартфон ZTE Blade A5 2020 Black',
    'Смартфон ZTE Blade A7 2020 (2+32GB) Black',
    'Смартфон ZTE Blade A7 2020 (2+32GB) Blue',
    'Смартфон ZTE Blade A5 2020 Blue',
    'Смартфон ZTE Blade A5 2020 Aquamarine',
    'Смартфон Honor 7A Prime 32GB Emerald Green (DUA-L22)',
    'Смартфон Honor 7A Prime 32GB Midnight Black (DUA-L22)',
    'Смартфон Honor 7A Prime 32GB Navy Blue (DUA-L22)',
    'Смартфон vivo Y11 Синий аквамарин (1906)',
    'Смартфон vivo Y11 Красный агат (1906)',
    'Смартфон Huawei Y6s Starry Black (JAT-LX1)',
    'Смартфон Huawei Y6s Orchid Blue (JAT-LX1)',
    'Смартфон ZTE Blade A7 2020 (3+64GB) Black',
    'Смартфон Realme C3 3+32GB Volcano Grey (RMX2021)',
    'Смартфон OPPO A12 Black (CPH2083)',
    'Смартфон Realme C3 3+32GB Frozen Blue (RMX2021)',
    'Смартфон OPPO A12 Blue (CPH2083)',
    'Смартфон Highscreen Power Five Max 2 3+32GB Black',
    'Смартфон Highscreen Power Five Max 2 3+32GB Brown',
    'Смартфон Samsung Galaxy A11 32GB Black (SM-A115F/DSN)',
    'Смартфон Realme C3 3+64GB NFC Frozen Blue (RMX2020)',
    'Смартфон Realme C3 3+64GB NFC Volcano Grey (RMX2020)',
    'Смартфон Honor 8A Prime 64GB Navy Blue (JAT-LX1)',
    'Смартфон Samsung Galaxy A11 32GB Red (SM-A115F/DSN)',
    'Смартфон Samsung Galaxy A11 32GB White (SM-A115F/DSN)',
    'Смартфон Realme C3 3+64GB NFC Blazing Red (RMX2020)',
    'Смартфон Honor 8A Prime 64GB Emerald Green (JAT-LX1)',
    'Смартфон Doogee S40 3+32GB Fire Orange',
    'Смартфон Doogee S40 3+32GB Mineral Black',
    'Смартфон Vsmart Joy 3+ 4+64GB White Pearl (V430)',
    'Смартфон Vsmart Joy 3+ 4+64GB Black (V430)',
    'Смартфон Vsmart Joy 3+ 4+64GB Violet (V430)',
    'Смартфон Doogee Y9 Plus Dreamy Purple',
    'Смартфон Doogee Y9 Plus Jewelry Blue',
    'Смартфон Doogee Y9 Plus Sky Black',
    'Смартфон Huawei Y6p Emerald Green (MED-LX9N)',
    'Смартфон Huawei Y6p Midnight Black (MED-LX9N)',
    'Смартфон Honor 9A Midnight Black (MOA-LX9N)',
    'Смартфон vivo Y12 Красный бургунди (1904)',
    'Смартфон vivo Y12 Морская волна (1904)',
    'Смартфон Honor 9A Phantom Blue (MOA-LX9N)',
    'Смартфон Honor 9A Ice Green (MOA-LX9N)',
    'Смартфон Huawei Y7 2019 (DUB-LX1) Aurora Blue',
    'Смартфон Huawei Y7 2019 4+64GB Aurora Purple (DUB-LX1)',
    'Смартфон Nokia 2.4 3+64GB Grey (TA-1270)',
    'Смартфон Nokia 2.4 3+64GB Purple (TA-1270)',
    'Смартфон Motorola MOTO E7 Plus Orange (XT2081-2)',
    'Смартфон Highscreen Power Five Max 2 4+64GB Black',
    'Смартфон Huawei Y7 2019 (DUB-LX1) Midnight Black',
    'Смартфон Samsung Galaxy M11 32GB Black (SM-M115F)',
    'Смартфон Huawei P40 Lite E NFC Aurora Blue (ART-L29N)',
    'Смартфон Xiaomi Redmi 9 3+32GB Ocean Green',
    'Смартфон Huawei P40 Lite E NFC Midnight Black (ART-L29N)',
    'Смартфон Xiaomi Redmi 9 3+32GB Sunset Purple',
    'Смартфон OPPO A31 4+64GB Mystery Black (CPH2015)',
    'Смартфон OPPO A31 4+64GB Fantasy White (CPH2015)',
    'Смартфон Realme C15 4+64GB Seagull Silver (RMX2180)',
    'Смартфон OPPO A31 4+64GB Lake Green (CPH2015)',
    'Смартфон Motorola G9 PLay XT2083-3 Blue',
    'Смартфон vivo Y20 Синий туман (V2027)',
    'Смартфон vivo Y20 Чёрный агат (V2027)',
    'Смартфон Samsung Galaxy A20s Black 32GB (SM-A207F/DS)',
    'Смартфон Samsung Galaxy A20s Blue 32GB (SM-A207F/DS)',
    'Смартфон Honor 9C Aurora Blue (AKA-L29)',
    'Смартфон OPPO A5 2020 Mirror Black (CPH1931)',
    'Смартфон Samsung Galaxy A20s Red 32GB (SM-A207F/DS)',
    'Смартфон OPPO A5 2020 Dazzling White (CPH1931)',
    'Смартфон Honor 9C Midnight Black (AKA-L29)',
    'Смартфон Huawei P40 Lite E Aurora Blue (ART-L29)',
    'Смартфон OPPO A53 4+64GB Electric Black (CPH2127)',
    'Смартфон vivo Y30 Сияющий синий (1938)',
    'Смартфон vivo Y30 Изумрудный чёрный (1938)',
    'Смартфон Huawei P40 Lite E Midnight Black (ART-L29)',
    'Смартфон OPPO A53 4+64GB Fancy Blue (CPH2127)',
    'Смартфон Motorola G8 XT2045-2 Neon blue',
    'Смартфон OPPO A53 4+64GB Mint Cream (CPH2127)',
    'Смартфон Highscreen Max 3 Red',
    'Смартфон ZTE Blade 20 Smart Black Graphite',
    'Смартфон ZTE Blade 20 Smart Dark Emerald',
    'Смартфон ZTE Blade 20 Smart Dark Granat',
    'Смартфон Xiaomi Redmi 9 4+64GB Carbon Grey',
    'Смартфон Xiaomi Redmi 9 4+64GB Sunset Purple',
    'Смартфон Xiaomi Redmi 9 4+64GB Ocean Green',
    'Смартфон Realme 6i 4+128GB Green Tea (RMX2040)',
    'Смартфон vivo Y17 Mystic Purple (1902)',
    'Смартфон Realme 6i 4+128GB White Milk (RMX2040)',
    'Смартфон Honor 20e 4+64GB Phantom Blue (HRY-LX1T)',
    'Смартфон Huawei Y8p Breathing Crystal (AQM-LX1)',
    'Смартфон OPPO A52 4+64GB Twilight Black (CPH2069)',
    'Смартфон Honor 10I 128Gb Shimmering Red (HRY-LX1T)',
    'Смартфон Huawei Y8p Midnight Black (AQM-LX1)',
    'Смартфон OPPO A52 4+64GB Stream White (CPH2069)',
    'Смартфон Samsung Galaxy A21s 32GB Black (SM-A217F/DSN)',
    'Смартфон Nokia 5.3 3+64GB Cyan (TA-1234)',
    'Смартфон Nokia 5.3 3+64GB Charcoal (TA-1234)',
    'Смартфон Samsung Galaxy A21s 32GB Blue (SM-A217F/DSN)',
    'Смартфон Honor 9X Lite 4+128GB Emerald Green (JSN-L21)',
    'Смартфон Honor 9X Lite 4+128GB Midnight Black (JSN-L21)',
    'Смартфон Samsung Galaxy M21 64GB Black (SM-M215F/DSN)',
    'Смартфон Samsung Galaxy M21 64GB Blue (SM-M215F/DSN)',
    'Смартфон Honor 9X 4+128GB Sapphire Blue (STK-LX1)',
    'Смартфон Samsung Galaxy M21 64GB Turquoise (SM-M215F/DSN)',
    'Смартфон OPPO A9 2020 Marine Green (CPH1941)',
    'Смартфон Xiaomi Redmi Note 8T 64GB Starscape Blue',
    'Смартфон Honor 9X 4+128GB Midnight Black (STK-LX1)',
    'Смартфон Samsung Galaxy A21s 64GB Black (SM-A217F/DSN)',
    'Смартфон OPPO A9 2020 Space Purple (CPH1941)',
    'Смартфон Honor 9X 4+128GB Emerald Green (STK-LX1)',
    'Смартфон Samsung Galaxy A21s 64GB Blue (SM-A217F/DSN)',
    'Смартфон Nokia 5.3 4+64GB Cyan (TA-1234)',
    'Смартфон Samsung Galaxy A21s 64GB Red (SM-A217F/DSN)',
    'Смартфон Nokia 5.3 4+64GB Charcoal (TA-1234)',
    'Смартфон Doogee S58 Pro Mineral Black',
    'Смартфон Doogee S58 Pro Fire Orange',
    'Смартфон Doogee S58 Pro Army Green',
    'Смартфон Honor 10X Lite 4+128GB Midnight Black (DNN-LX9)',
    'Смартфон Honor 10X Lite 4+128GB Icelandic Frost (DNN-LX9)',
    'Смартфон Samsung Galaxy A31 64GB Black (SM-A315F)',
    'Смартфон Samsung Galaxy A31 64GB Red (SM-A315F)',
    'Смартфон Honor 20 Lite 4+128GB Sapphire Blue (MAR-LX1H)',
    'Смартфон Xiaomi Redmi Note 9 64GB Forest Green',
    'Смартфон Honor 20 Lite 4+128GB Peacock Blue (MAR-LX1H)',
    'Смартфон Xiaomi Redmi Note 9 64GB Midnight Grey',
    'Смартфон Samsung Galaxy A31 64GB White (SM-A315F)',
    'Смартфон Xiaomi Redmi Note 9 64GB Onyx Black',
    'Смартфон Honor 20 Lite 4+128GB Midnight Black (MAR-LX1H)',
    'Смартфон Realme 6 4+128GB Comet Blue (RMX2001)',
    'Смартфон Huawei P Smart Z Midnight Black (STK-LX1)',
    'Смартфон Huawei P Smart Z Sapphire Blue (STK-LX1)',
    'Смартфон Huawei P Smart Z Emerald Green (STK-LX1)',
    'Смартфон Realme 6 4+128GB Comet White (RMX2001)',
    'Смартфон Realme 6S 6+128GB Eclipse Black (RMX2002)',
    'Смартфон Xiaomi Redmi Note 9 64GB Polar White',
    'Смартфон Realme 6S 6+128GB Lunar White (RMX2002)',
    'Смартфон Huawei P40 Lite Midnight Black (JNY-LX1)',
    'Смартфон Huawei P40 Lite Crush Green (JNY-LX1)',
    'Смартфон Honor 30i 4+128GB Phantom Blue (LRA-LX1)',
    'Смартфон Honor 30i 4+128GB Icelandic Frost (LRA-LX1)',
    'Смартфон Xiaomi Mi 9 64GB Piano Black',
    'Смартфон Xiaomi Mi 9 64GB Ocean Blue',
    'Смартфон Honor 30i 4+128GB Midnight Black (LRA-LX1)',
    'Смартфон Honor 9X Premium 6+128GB Midnight Black (STK-LX1)',
    'Смартфон Xiaomi Mi 9 64Gb Lavender Violet',
    'Смартфон Xiaomi Redmi Note 9 128GB Forest Green',
    'Смартфон Xiaomi Redmi Note 9 128GB Midnight Grey',
    'Смартфон Samsung Galaxy A31 128GB Black (SM-A315F)',
    'Смартфон Samsung Galaxy A41 64GB Black (SM-A415F/DSM)',
    'Смартфон Realme 6 8+128GB Comet White (RMX2001)',
    'Смартфон Realme 6 8+128GB Comet Blue (RMX2001)',
    'Смартфон Xiaomi Redmi Note 9 128GB Polar White',
    'Смартфон Samsung Galaxy A31 128GB Red (SM-A315F)',
    'Смартфон Samsung Galaxy A31 128GB White (SM-A315F)',
    'Смартфон Samsung Galaxy A51 64GB Black (SM-A515F)',
    'Смартфон Samsung Galaxy M31 128GB Black (SM-M315F/DSN)',
    'Смартфон Samsung Galaxy A51 64GB White (SM-A515F)',
    'Смартфон Samsung Galaxy A51 64GB Red (SM-A515F)',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+64GB Forest Green',
    'Смартфон Samsung Galaxy M31 128GB Blue (SM-M315F/DSN)',
    'Смартфон Samsung Galaxy M31 128GB Red (SM-M315F/DSN)',
    'Смартфон vivo V17 Синий туман (1920)',
    'Смартфон vivo V17 Облачная лазурь (1920)',
    'Смартфон vivo V20SE Графитовый чёрный (V2023)',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+64GB Pearl White',
    'Смартфон vivo V20SE Ясное небо (V2023)',
    'Смартфон OPPO A72 4+128GB Aurora Purple (CPH2067)',
    'Смартфон OPPO A72 4+128GB Twilight Black (CPH2067)',
    'Смартфон Honor 20S 128GB Midnight Black (MAR-LX1H)',
    'Смартфон Realme 7 8+128GB Mist Blue (RMX2155)',
    'Смартфон Honor 20S 128GB Peacock Blue (MAR-LX1H)',
    'Смартфон Realme 7 8+128GB Mist White (RMX2155)',
    'Смартфон Samsung Galaxy A51 64GB Blue (SM-A515F)',
    'Смартфон Honor 20S 128GB Pearl White (MAR-LX1H)',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+64GB Coral Orange',
    'Смартфон OPPO A72 4+128GB Shining White (CPH2067)',
    'Смартфон Doogee S68 Pro Mineral Black',
    'Смартфон Doogee S68 Pro Fire Orange',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+128GB Mineral Grey',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+128GB Ocean Blue',
    'Смартфон Xiaomi Redmi Note 8 Pro 6+128GB Forest Green',
    'Смартфон Realme 6 Pro 8+128GB Lightning Blue (RMX2063)',
    'Смартфон Realme 6 Pro 8+128GB Lightning Red (RMX2063)',
    'Смартфон Huawei P30 Lite 256Gb Midnight Black (MAR-LX1B)',
    'Смартфон Samsung Galaxy A51 128GB Black (SM-A515F)',
    'Смартфон Samsung Galaxy A51 128GB White (SM-A515F)',
    'Смартфон Samsung Galaxy A51 128GB Red (SM-A515F)',
    'Смартфон Samsung Galaxy A51 128GB Blue (SM-A515F)',
    'Смартфон Xiaomi Mi 9 128Gb Lavender Violet',
    'Смартфон Xiaomi Redmi Note 9 Pro 128GB Grey',
    'Смартфон Xiaomi Redmi Note 9 Pro 128GB Green',
    'Смартфон Samsung Galaxy M31s 128GB Blue (SM-M317F/DSN)',
    'Смартфон Huawei Nova 5T Crush Blue (YAL-L21)',
    'Смартфон Huawei Nova 5T Midsummer Purple (YAL-L21)',
    'Смартфон OPPO Reno4 Lite 8+128GB Matte Black (CPH2125)',
    'Смартфон Honor 20 128Gb Midnight Black (YAL-L21)',
    'Смартфон OPPO Reno4 Lite 8+128GB Magic Blue (CPH2125)',
    'Смартфон Samsung Galaxy A70 (2019) 128Gb Blue (SM-A705FN)',
    'Смартфон Samsung Galaxy A70 (2019) 128Gb White (SM-A705FN)',
    'Смартфон Samsung Galaxy A70 (2019) 128Gb Black (SM-A705FN)',
    'Смартфон Apple iPhone 7 32Gb Black (MN8X2RU/A)',
    'Смартфон Apple iPhone 7 32Gb Rose Gold (MN912RU/A)',
    'Смартфон vivo V20 Таинственная полночь (V2025)',
    'Смартфон Apple iPhone 7 32Gb Gold (MN902RU/A)',
    'Смартфон vivo V20 Красочный закат (V2025)',
    'Смартфон Honor 30S 128GB Midnight Black (CDY-NX9A)',
    'Смартфон Honor 30S 128GB Neon Purple (CDY-NX9A)',
    'Смартфон Honor 30S 128GB Titanium Silver (CDY-NX9A)',
    'Смартфон Samsung Galaxy A71 Black(SM-A715F/DSM)',
    'Смартфон Samsung Galaxy A71 Silver (SM-A715F/DSM)',
    'Смартфон Samsung Galaxy A71 Blue (SM-A715F/DSM)',
    'Смартфон Realme X3 Super Zoom 8+128GB Glacier Blue (RMX2086)',
    'Смартфон OPPO Reno3 Auroral Blue (CPH2043)',
    'Смартфон OPPO Reno3 Sky White (CPH2043)',
    'Смартфон OPPO Reno3 Midnight Black (CPH2043)',
    'Смартфон Realme X3 Super Zoom 8+128GB Arctic White (RMX2086)',
    'Смартфон Samsung Galaxy M51 128GB White (SM-M515F/DSN)',
    'Смартфон Huawei P30 Breathing Crystal (ELE-L29)',
    'Смартфон Honor 30 128GB Midnight Black (BMH-AN10)',
    'Смартфон Honor 30 128GB Emerald Green (BMH-AN10)',
    'Смартфон Xiaomi Mi Note 10 Lite 128GB Glacier White',
    'Смартфон Xiaomi Mi Note 10 Lite 128GB Nebula Purple',
    'Смартфон Realme X3 Super Zoom 12+256GB Arctic White (RMX2086)',
    'Смартфон Realme X3 Super Zoom 12+256GB Glacier Blue (RMX2086)',
    'Смартфон Honor 30 Premium 256GB Titanium Silver (BMH-AN10)',
    'Смартфон Apple iPhone 8 64GB Silver (MQ6H2RU/A)',
    'Смартфон Honor 30 Premium 256GB Midnight Black (BMH-AN10)',
    'Смартфон Honor View 30 Pro 256GB Midnight Black (OXF-AN10)',
    'Смартфон Apple iPhone 8 128GB Space Grey (MX162RU/A )',
    'Смартфон Apple iPhone SE 2020 64GB Black (MX9R2RU/A)',
    'Смартфон Apple iPhone SE 2020 64GB White (MX9T2RU/A)',
    'Смартфон Apple iPhone SE 2020 64GB RED (MX9U2RU/A)',
    'Смартфон vivo X50 Чёрное зеркало (2004)',
    'Смартфон Samsung Galaxy Note10 Lite Aura (SM-N770F/DSM)',
    'Смартфон vivo X50 Небесно-голубой (2004)',
    'Смартфон Apple iPhone SE 2020 128GB Black (MXD02RU/A)',
    'Смартфон Samsung Galaxy S10E Оникс',
    'Смартфон Apple iPhone SE 2020 128GB White (MXD12RU/A)',
    'Смартфон Huawei P40 Silver Frost (ANA-NX9)',
    'Смартфон Apple iPhone SE 2020 128GB RED (MXD22RU/A)',
    'Смартфон Huawei P40 Black (ANA-NX9)',
    'Смартфон Xiaomi Mi Note 10 Pro 256GB Aurora Green',
    'Смартфон Apple iPhone 8 Plus 128GB Gold (MX262RU/A )',
    'Смартфон Apple iPhone XR 64GB Black (MRY42RU/A)',
    'Смартфон Apple iPhone XR 64GB White (MRY52RU/A)',
    'Смартфон Apple iPhone XR 64GB RED (MRY62RU/A)',
    'Смартфон Apple iPhone XR 64GB Black (MH6M3RU/A)',
    'Смартфон Apple iPhone XR 64GB Coral (MRY82RU/A)',
    'Смартфон Apple iPhone XR 64GB White (MH6N3RU/A)',
    'Смартфон Apple iPhone XS 64Gb Space Grey (FT9E2RU/A) восст.',
    'Смартфон Apple iPhone XR 64GB Blue (MRYA2RU/A)',
    'Смартфон Apple iPhone XR 64GB (PRODUCT)RED (MH6P3RU/A)',
    'Смартфон Apple iPhone XR 64GB Yellow (MRY72RU/A)',
    'Смартфон Apple iPhone XR 64GB Yellow (MH6Q3RU/A)',
    'Смартфон Apple iPhone XR 64GB Blue (MH6T3RU/A)',
    'Смартфон Apple iPhone XR 64GB Coral (MH6R3RU/A)',
    'Смартфон Huawei P30 Pro Aurora (VOG-L29)',
    'Смартфон Huawei P30 Pro Breathing Crystal (VOG-L29)',
    'Смартфон Samsung Galaxy S20 FE Blue (SM-G780F)',
    'Смартфон Huawei P30 Pro Black (VOG-L29)',
    'Смартфон OPPO Reno3 Pro Moonlight Black (CPH2009)',
    'Смартфон Samsung Galaxy Note10 Aura Glow (SM-N970F)',
    'Смартфон Samsung Galaxy S20 FE Violet (SM-G780F)',
    'Смартфон Samsung Galaxy S20 FE Green (SM-G780F)',
    'Смартфон Samsung Galaxy S20 FE White (SM-G780F)',
    'Смартфон Samsung Galaxy S20 FE Red (SM-G780F)',
    'Смартфон OPPO Reno3 Pro Auroral Blue (CPH2009)',
    'Смартфон Nokia 8.3 5G 128GB Blue (TA-1243)',
    'Смартфон Apple iPhone XR 128GB Black (MRY92RU/A)',
    'Смартфон Apple iPhone XR 128GB White (MRYD2RU/A)',
    'Смартфон Apple iPhone XR 128GB RED (MRYE2RU/A)',
    'Смартфон Apple iPhone XR 128GB Black (MH7L3RU/A)',
    'Смартфон Apple iPhone XR 128GB Blue (MRYH2RU/A)',
    'Смартфон Apple iPhone XR 128GB White (MH7M3RU/A)',
    'Смартфон Apple iPhone XR 128GB (PRODUCT)RED (MH7N3RU/A)',
    'Смартфон Apple iPhone XR 128GB Coral (MH7Q3RU/A)',
    'Смартфон Apple iPhone XR 128GB Yellow (MH7P3RU/A)',
    'Смартфон Apple iPhone XR 128GB Blue (MH7R3RU/A)',
    'Смартфон Apple iPhone SE 2020 256GB White (MXVU2RU/A)',
    'Смартфон Apple iPhone SE 2020 256GB RED (MXVV2RU/A)',
    'Смартфон Apple iPhone SE 2020 256GB Black (MXVT2RU/A)',
    'Смартфон Apple iPhone 11 64GB Black (MWLT2RU/A)',
    'Смартфон Apple iPhone 11 64GB White (MWLU2RU/A)',
    'Смартфон Apple iPhone 11 64GB Purple (MWLX2RU/A)',
    'Смартфон Apple iPhone 11 64GB (PRODUCT)RED (MWLV2RU/A)',
    'Смартфон Apple iPhone 11 64GB Green (MWLY2RU/A)',
    'Смартфон Apple iPhone 11 64GB Black (MHDA3RU/A)',
    'Смартфон Apple iPhone 11 64GB Purple (MHDF3RU/A)',
    'Смартфон Apple iPhone 11 64GB White (MHDC3RU/A)',
    'Смартфон Honor 30 Pro+ 256GB Midnight Black (EBG-AN10)',
    'Смартфон Apple iPhone 11 64GB Yellow (MWLW2RU/A)',
    'Смартфон Apple iPhone 11 64GB (PRODUCT)RED (MHDD3RU/A)',
    'Смартфон Honor 30 Pro+ 256GB Emerald Green (EBG-AN10)',
    'Смартфон Apple iPhone 11 64GB Green (MHDG3RU/A)',
    'Смартфон Samsung Galaxy S20 FE 256GB Cloud Lavender (SM-G780F)',
    'Смартфон Samsung Galaxy S20 FE 256GB Cloud Mint (SM-G780F)',
    'Смартфон Apple iPhone 11 128GB (PRODUCT)RED (MWM32RU/A)',
    'Смартфон Apple iPhone 11 128GB Black (MWM02RU/A)',
    'Смартфон Apple iPhone 11 128GB Black (MHDH3RU/A)',
    'Смартфон Apple iPhone 11 128GB Green (MWM62RU/A)',
    'Смартфон Apple iPhone 11 128GB Purple (MWM52RU/A)',
    'Смартфон Samsung Galaxy S10 Оникс',
    'Смартфон Apple iPhone 11 128GB White (MHDJ3RU/A)',
    'Смартфон Apple iPhone 11 128GB Purple (MHDM3RU/A)',
    'Смартфон Samsung Galaxy S10 Перламутр',
    'Смартфон Samsung Galaxy S10 Аквамарин',
    'Смартфон Apple iPhone 11 128GB Green (MHDN3RU/A)',
    'Смартфон vivo X50 Pro Серая сталь (2006)',
    'Смартфон Samsung Galaxy S10 128Gb гранат',
    'Смартфон Apple iPhone 11 128GB Yellow (MHDL3RU/A)',
    'Смартфон Apple iPhone XS Max 256Gb Space Grey (FT532RU/A) восст.',
    'Смартфон Sony Xperia 1 Black (J9110)',
    'Смартфон Apple iPhone XS Max 512Gb Space Grey (FT562RU/A) восст.',
    'Смартфон Apple iPhone 12 mini 64GB Black (MGDX3RU/A)',
    'Смартфон Apple iPhone 12 mini 64GB White (MGDY3RU/A)',
    'Смартфон Apple iPhone 12 mini 64GB Blue (MGE13RU/A)',
    'Смартфон Huawei P40 Pro Silver Frost (ELS-NX9)',
    'Смартфон Samsung Galaxy S10+ Оникс',
    'Смартфон Samsung Galaxy S20 Gray (SM-G980F/DS)',
    'Смартфон Samsung Galaxy S10+ Перламутр',
    'Смартфон Samsung Galaxy S20 Light Blue (SM-G980F/DS)',
    'Смартфон Apple iPhone 12 mini 64GB (PRODUCT)RED (MGE03RU/A)',
    'Смартфон Huawei P40 Pro Black (ELS-NX9)',
    'Смартфон Apple iPhone 11 256GB Black (MHDP3RU/A)',
    'Смартфон Apple iPhone 11 256GB Purple (MHDU3RU/A)',
    'Смартфон Samsung Galaxy S10+ Аквамарин',
    'Смартфон Samsung Galaxy S20 Red (SM-G980F/DS)',
    'Смартфон Apple iPhone 11 256GB White (MWM82RU/A)',
    'Смартфон Apple iPhone 11 256GB (PRODUCT)RED (MWM92RU/A)',
    'Смартфон Huawei P40 Pro Deep Sea Blue (ELS-NX9)',
    'Смартфон Apple iPhone 11 256GB White (MHDQ3RU/A)',
    'Смартфон Apple iPhone 12 mini 64GB Green (MGE23RU/A)',
    'Смартфон Samsung Galaxy S10+ 128GB White Ceramic (SM-G975F/DS)',
    'Смартфон Apple iPhone 11 256GB Green (MWMD2RU/A)',
    'Смартфон Apple iPhone 11 256GB Green (MHDV3RU/A)',
    'Смартфон Apple iPhone 12 mini 128GB Black (MGE33RU/A)',
    'Смартфон Apple iPhone 12 mini 128GB Blue (MGE63RU/A)',
    'Смартфон Apple iPhone 12 mini 128GB White (MGE43RU/A)',
    'Смартфон Apple iPhone 12 mini 128GB Green (MGE73RU/A)',
    'Смартфон Apple iPhone 12 mini 128GB (PRODUCT)RED (MGE53RU/A)',
    'Смартфон Apple iPhone 11 Pro 64GB Midnight Green (MWC62RU/A)',
    'Смартфон Apple iPhone 11 Pro 64GB Space Grey (MWC22RU/A)',
    'Смартфон Apple iPhone 12 64GB Black (MGJ53RU/A)',
    'Смартфон Apple iPhone 12 64GB Blue (MGJ83RU/A)',
    'Смартфон Apple iPhone 12 64GB White (MGJ63RU/A)',
    'Смартфон Apple iPhone 11 Pro 64GB Silver (MWC32RU/A)',
    'Смартфон Samsung Galaxy S20+ Black (SM-G985F/DS)',
    'Смартфон Apple iPhone 12 64GB (PRODUCT)RED (MGJ73RU/A)',
    'Смартфон Apple iPhone 12 64GB Green (MGJ93RU/A)',
    'Смартфон Apple iPhone 11 Pro 64GB Gold (MWC52RU/A)',
    'Смартфон Samsung Galaxy S20+ Gray (SM-G985F/DS)',
    'Смартфон Samsung Galaxy Note 20 256GB Bronze (SM-N980F/DS)',
    'Смартфон Samsung Galaxy S20+ Red (SM-G985F/DS)',
    'Смартфон Samsung Galaxy Note 20 256GB Green (SM-N980F/DS)',
    'Смартфон Samsung Galaxy Note 20 256GB Gray (SM-N980F/DS)',
    'Смартфон Apple iPhone 12 128GB Black (MGJA3RU/A)',
    'Смартфон Apple iPhone 12 128GB Blue (MGJE3RU/A)',
    'Смартфон Apple iPhone 12 128GB White (MGJC3RU/A)',
    'Смартфон Apple iPhone 12 128GB (PRODUCT)RED (MGJD3RU/A)',
    'Смартфон Apple iPhone 12 128GB Green (MGJF3RU/A)',
    'Смартфон Huawei Mate 40 Pro Mystic Silver (NOH-NX9)',
    'Смартфон Apple iPhone 12 256GB Black (MGJG3RU/A)',
    'Смартфон Apple iPhone 12 256GB White (MGJH3RU/A)',
    'Смартфон Apple iPhone 12 256GB (PRODUCT)RED (MGJJ3RU/A)',
    'Смартфон Apple iPhone 11 Pro 256GB Midnight Green (MWCC2RU/A)',
    'Смартфон Apple iPhone 11 Pro 256GB Space Grey (MWC72RU/A)',
    'Смартфон Apple iPhone 11 Pro 256GB Gold (MWC92RU/A)',
    'Смартфон Apple iPhone 11 Pro 256GB Silver (MWC82RU/A)',
    'Смартфон Apple iPhone 12 Pro 128GB Pacific Blue (MGMN3RU/A)',
    'Смартфон Apple iPhone 12 Pro 128GB Graphite (MGMK3RU/A)',
    'Смартфон Samsung Galaxy Note 20 Ultra 256GB Bronze (SM-N985F/DS)',
    'Смартфон Samsung Galaxy Note 20 Ultra 256GB Black (SM-N985F/DS)',
    'Смартфон Huawei P40 Pro+ Black Ceramic (ELS-N39)',
    'Смартфон Samsung Galaxy S20 Ultra Black (SM-G988B/DS)',
    'Смартфон Samsung Galaxy Note 20 Ultra 256GB White (SM-N985F/DS)',
    'Смартфон Samsung Galaxy S20 Ultra Gray (SM-G988B/DS)',
    'Смартфон Samsung Galaxy Z Flip Black (SM-F700F/DS)',
    'Смартфон Samsung Galaxy Z Flip Purple (SM-F700F/DS)',
    'Смартфон Apple iPhone 12 Pro 128GB Gold (MGMM3RU/A)',
    'Смартфон Apple iPhone 11 Pro Max 256GB Gold (MWHL2RU/A)',
    'Смартфон Apple iPhone 11 Pro 512GB Midnight Green (MWCG2RU/A)',
    'Смартфон Apple iPhone 11 Pro 512GB Gold (MWCF2RU/A)',
    'Смартфон Apple iPhone 12 Pro 256GB Pacific Blue (MGMT3RU/A)',
    'Смартфон Apple iPhone 12 Pro 256GB Gold (MGMR3RU/A)',
    'Смартфон Samsung Galaxy Note 20 Ultra 512GB Bronze (SM-N986B/DS)',
    'Смартфон Samsung Galaxy Note 20 Ultra 512GB White (SM-N986B/DS)',
    'Смартфон Apple iPhone 12 Pro 512GB Pacific Blue (MGMX3RU/A)',
    'Смартфон Apple iPhone 12 Pro 512GB Graphite (MGMU3RU/A)',
    'Смартфон Apple iPhone 12 Pro 512GB Gold (MGMW3RU/A)',
    'Смартфон Samsung Galaxy Fold Silver (SM-F900F)',
    'Смартфон Samsung Galaxy Fold Black (SM-F900F)',
    'Смартфон Samsung Galaxy Z Fold 2 256GB Black (SM-F916B)',
    'Смартфон Samsung Galaxy Z Fold2 256GB Bronze (SM-F916B)',
    'Смартфон Prestigio Muze B3 Duo Wine (PSP3512)',
    'Смартфон Digma Linx A452 3G Graphite',
    'Смартфон Sony Xperia XA1 Plus Black (G3412)',
    'Смартфон BQ mobile Strike Mini Gold Brushed (BQ-4072)',
    'Смартфон TP-Link Neffos X1 Lite 16Gb Sunrise Gold (TP904A)',
    'Смартфон ZTE Blade A3 Blue',
    'Смартфон ZTE Blade A3 Black',
    'Смартфон BQ mobile Velvet Gold (BQ-5035)',
    'Смартфон OPPO Reno Azure Ocean (CPH1917)',
    'Смартфон OPPO Reno Black Graphite (CPH1917)',
    'Смартфон ZTE Blade A5 Black',
    'Смартфон Samsung Galaxy J2 Prime Silver SM-G532F',
)

models1 = ('Смартфон Samsung Galaxy S10 Оникс',
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
           'Смартфон Samsung Galaxy S10+ Ceramic 1TB (SM-G975F/DS)',
           )

if __name__ == '__main__':
    time_start = time.time()

    import main
    main.load_exceptions_model_names()
    main.read_config()

    # for item in models:
    #     logger.info(h.find_and_replace_except_model_name(item))

    for item in models1:
        res = mvideo_parse_model_name(item)
        print('{},{},{}'.format(res[0], res[1], res[2]))
    # parser = MVideoParse()
    # result_list = parser.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
    # check = checker.Checker(result_list)
    # check.run()

    logger.info(f"Время выполнения: {time.time() - time_start} сек")

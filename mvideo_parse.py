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

from selenium.webdriver.common.proxy import Proxy, ProxyType

import header as h

logger = h.logging.getLogger('mvideoparse')
MVIDEO_REBUILT_IPHONE = ' восст.'


# Парсинг названия модели (получить название модели, цвет и ROM)
def mvideo_parse_model_name(name):
    # Защита от неправильных названий
    if len(name.split()) < 5:
        return None, None, None
    # Убираем неразрывные пробелы
    name = name.replace(u'\xc2\xa0', u' ')
    name = name.replace(u'\xa0', u' ')
    # Восстановленные телефоны (только для iphone). Если есть слово - удалить
    rebuilt = h.REBUILT_IPHONE_NAME if (MVIDEO_REBUILT_IPHONE in name.lower()) else ''
    name = name.replace(MVIDEO_REBUILT_IPHONE, '')
    # Оборачивание скобками названия модели, если их не было
    last_word = name.split()[-1]
    if last_word.isupper() and \
            not ('(' in last_word) and \
            not (')' in last_word):
        name = name.replace(last_word, '({})'.format(last_word))
    # Понижение регистра
    name = name.lower()
    # Удалить nfc и 5g
    name = name.replace(' nfc ', ' ').replace(' 5g ', ' ')
    # Удалить все скобки
    brackets = re.findall(r"\(.+?\)", name)
    for item in brackets:
        name = name.replace(item, '')
    # Удалить год, если есть
    year = re.findall(r' 20[1,2]\d ', name)
    year = year[0] if year else ''
    # Получить размер ROM
    rom = re.findall(r'\d*[gb]*\+*\d+(?:gb|tb)', name)
    rom = (rom[0]) if rom else ""
    # Получить ЦВЕТ
    # Получить 2 слова цвета
    color1, color2 = name.split()[-2:] if name.split()[-1] != rom \
        else name.split()[-3:-1]
    # Если первое слово цвета состоит только из букв и длиннее 2 символов и отсутствует в игнор-листе - добавить
    # к итоговому цвету
    color1 = color1 if (
                color1.isalpha() and len(color1) > 2 and not (color1.strip() in h.IGNORE_WORDS_FOR_COLOR)) else ""
    color = color1 + " " + color2 if (color1.isalpha() and len(color1) > 2) else color2
    # Удалить первую часть часть
    name = name.replace('смартфон', '').replace(rom, '').replace(year, '').replace('  ', ' ')
    # Убрать вторую часть лишних слов из названия
    name = name.replace(color, '').replace('  ', ' ').strip()
    name += rebuilt

    # Проверка названия в словаре исключений названий моделей
    name = h.find_and_replace_except_model_name(name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        h.save_undefined_model_name(name)
        return None, None, None

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color


# Парсер МВидео
class MVideoParse:

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
        # Данные магазина
        self.domain = "https://www.mvideo.ru"
        self.shop = "мвидео"
        # Конфиг
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
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

    # Поиск всех элементов без таймаута
    def __wd_find_all_elems(self, by, xpath):
        try:
            result = self.driver.find_elements(by, xpath)
            return result
        except se.NoSuchElementException:
            return None

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

    # Алгоритм выбора города для всех возможных ситуаций для страницы каталога
    def __wd_city_selection_catalog(self):
        city = self.__wd_find_elem_with_timeout(By.XPATH, "//span[@class='location-text top-navbar-link']")
        if not city:
            logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if self.current_city.lower() not in city.text.lower():
            logger.info("Неверный город")

            # Клик по городу
            if not self.__wd_ac_click_elem(city):
                logger.error("Не могу нажать на кнопку выбора города")
                return False

            logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self.__wd_find_all_elems_with_timeout(By.CLASS_NAME, "location-select__location")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self.__wd_ac_click_elem(item)
            else:
                logger.warning("Нет списка городов, попробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self.__wd_find_elem_with_timeout(By.CLASS_NAME, "location-select__input-wrap")
            if not input_city:
                logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            if not self.__wd_ac_click_elem(input_city):
                logger.error("Не могу нажать на форму ввода текста")
                return False

            # Ввод названия города по буквам
            for char in self.current_city:
                self.__wd_ac_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self.__wd_find_elem_with_timeout(By.XPATH, "//li[@data-index='0']")
            if not input_city_item:
                logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self.__wd_ac_click_elem(input_city_item):
                logger.error("Не могу нажать на выбранный город")
                return False

        return True

    # Алгоритм выбора города для всех возможных ситуаций для страницы продукта
    def __wd_city_selection_product(self):
        pass

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

        logger.info("Page loaded")
        return True

    # Проверка по ключевым div-ам что страница товара прогружена полностью
    def __wd_check_load_page_product(self):
        pass

    # Переключение на отображение товаров в виде списка
    def __wd_select_list_view(self):

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
            if not self.__wd_ac_click_elem(listing_views):
                logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

        # Но если нет и тега list (вид списка) - то ошибка
        elif not self.__wd_find_elem(By.XPATH,
                                     "//div[@class='listing-view-switcher__pointer listing-view-switcher__pointer--list']"):
            logger.error("Не вижу тегов для переключения вида товара")
            return False

        return True

    # Скролл вниз для прогрузки товаров на странице
    def __wd_scroll_down(self, num=35):
        for _ in range(num):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN).perform()
            time.sleep(0.2)

    # Запуск браузера, загрузка начальной страницы каталога, выбор города
    def __wd_open_browser_catalog(self, url):
        try:
            self.driver.get(url)
        except (se.TimeoutException, se.WebDriverException):
            print("Не смог загрузить страницу")
            logger.error("Не смог загрузить страницу")
            return False

        # Ждем, пока не прогрузится страница, даем 3 попытки, т.к. сайт при первом запуске часто выдает пустую страницу
        for _ in range(3):
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_open_browser, пробую обновить")
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
        if not self.__wd_select_list_view():
            logger.error("Не смог переключить отображение товара в виде списока")
            return False

        # Скролл
        self.__wd_scroll_down(13)

        # Найти кнопку выбора кол-ва товаров на странице
        but_show24 = self.__wd_find_elem_with_timeout(By.XPATH, "//span[contains(text(),'Показывать по 24')]")
        if but_show24:
            self.__wd_ac_click_elem(but_show24)
            item_show72 = self.__wd_find_elem_with_timeout(By.XPATH, "//div[contains(text(),'Показывать по 72')]")

            # Переключиться на 72 товара на странице
            if item_show72:
                self.__wd_ac_click_elem(item_show72)

        # Ждем, пока не прогрузится страница
        if not self.__wd_check_load_page_catalog():
            logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        # Скролл
        self.__wd_scroll_down()
        return True

    # Запуск браузера, загрузка начальной страницы парсинга, выбор города
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

            # Поиск следующей кнопки страницы
            num_page_elem = self.__wd_find_elem(By.XPATH, "//li[@class='page-item number-item ng-star-inserted']/"
                                                          "a[text()={}]".format(self.cur_page))
            if not num_page_elem:
                logger.info("Достигнут конец каталога")
                return False

            # Клик - переход на следующую страницу
            if not self.__wd_ac_click_elem(num_page_elem):
                logger.error("Не могу кликнуть на страницу в __wd_next_page")
                return False

            # Специальная задержка между переключениями страниц для имитации юзера
            time.sleep(self.wait_between_pages_sec)

            # Скролл вниз
            self.__wd_scroll_down()

            no_in_stock = self.__wd_find_all_elems(By.XPATH, '//div[contains(text(), "Нет в наличии")]')
            if no_in_stock and len(no_in_stock) == 72:
                logger.info("Вся страница неактуальна, выход")
                return False

            # Ждем, пока не прогрузится страница
            if not self.__wd_check_load_page_catalog():
                logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Особенность МВидео - при переключении страницы, пока сайт ждет ответ от сервера,
            # оставляет старые данные с эффектом размытия. Ждем, пока они не исчезнут
            try:
                self.wait.until_not(ec.presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                    self.pr_result_list[-5].url))))
            except se.TimeoutException:
                logger.error('Не пропадает телефон с прошлой страницы, не могу прогрузить текущую')
                self.driver.refresh()
                continue
            except IndexError:
                logger.error('По непонятной причине список pr_result_list[-5] оказался пуст, выход за границы списка')
                return False

            self.cur_page += 1
            return True
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

    # Метод для парсинга html страницы каталога
    def __parse_catalog_page(self, html):
        soup = bs4.BeautifulSoup(html, 'lxml')

        # Категория (из хлебных крошек)
        self.category = soup.select('li.breadcrumbs__item')
        if not self.category:
            logger.error("No category")
            self.category = "error"
        else:
            self.category = self.category[-1].text.replace(' ', '').replace('\n', '').strip().lower()

        # Контейнер с элементами
        container = soup.select('div.product-cards-layout__item')

        for block in container:
            self.__parse_catalog_block(block)
        del container

    # Метод для парсинга html страницы товара
    def __parse_catalog_block(self, block):
        # Название модели и URL
        model_name_url_block = block.select_one('a.product-title__text')

        # Проверка на баг мвидео - наличие в названии модели фразы PDA
        if model_name_url_block and ('pda' in model_name_url_block.text.lower()):
            logger.warning("PDA detected")
            return

        if not model_name_url_block:
            logger.warning("No model name and URL")
            return
        else:
            url = model_name_url_block.get('href')
            full_name = model_name_url_block.text.replace('\n', '').strip()

        # Чек
        if not [item.text for item in block.select('span') if ("В корзину" in item.text)]:
            logger.info("Нет кнопки 'В корзину', {} {}".format(full_name, url))
            return

        # Проверка на предзаказ
        if [item.text for item in block.select("span.button__label.ng-star-inserted") if item.text == "Предзаказ"]:
            logger.info("Товар '{}' по предзаказу, пропуск".format(full_name))
            return

        # Проверка на наличие
        if [item.text for item in block.select("div.product-notification") if "Нет в наличии" in item.text]:
            logger.info("Товара '{}' нет в наличии, пропуск".format(full_name))
            return

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
            return
        else:
            for item in specifications:
                if "ram" in item.text.lower():
                    ram = int(re.findall(r'\d+', item.text)[0])
                if "rom" in item.text.lower():
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

        # Парсинг названия модели
        brand_name, model_name, color = mvideo_parse_model_name(full_name)
        if not brand_name or not model_name or not color:
            logger.warning("No brand name, model name, color or not in the list of allowed")
            return

        if 'apple' in brand_name.lower():
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
            img_url=img_url.lower(),
            url=url.lower(),
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
        self.__save_result('mvideo.csv')

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

    parser = MVideoParse()
    parser.run_catalog('https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

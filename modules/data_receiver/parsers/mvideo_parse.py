import re
import time

import selenium.common.exceptions as se
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec

from modules.data_receiver.parsers.parse_base import ParseBase
import modules.common.helper as h
from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('mvideoparse')
MVIDEO_REBUILT_IPHONE = ' восст.'


def mvideo_parse_model_name(name):
    """
    Парсинг названия модели (получить название модели, цвет и ROM)
    """
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
    name = h.replace_value_from_dictionary(h.EXCEPT_MODEL_NAMES_DICT, name)

    # Проверка названия модели в словаре разрешенных моделей
    if not h.find_allowed_model_names(name):
        logger.info("Обнаружена новая модель, отсутствующая в базе = '{}'".format(name))
        FileWorker.list_data.save(h.UNDEFINED_MODEL_NAME_LIST_PATH, data=name, overwrite=False)
        return None, None, None

    # Получить название бренда
    brand_name = name.split()[0]
    model_name = name.replace(brand_name, '').strip()

    return brand_name, model_name, color


class MVideoParse(ParseBase):
    """
    РЕАЛИЗАЦИЯ ОДНОГО ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataReceiver
    Реализация базового класса ParseBase
    Парсит данные с магазина МВидео
    """
    def __init__(self):
        super().__init__(domain="https://www.mvideo.ru", shop="mvideo", logger=logger, category="смартфоны")
        self.container_css_selector = 'div.product-cards-layout__item'

    def _wd_city_selection_catalog(self):
        """
        Алгоритм выбора города для всех возможных ситуаций для страницы каталога
        """
        city = self._wd_find_elem_with_timeout(By.XPATH, "//span[@class='location-text top-navbar-link ng-tns-c147-1']")
        if not city:
            self.logger.error("Не найдено поле с названием города")
            return False

        # Если указан неверный город
        if self.current_city.lower() not in city.text.lower():
            self.logger.info("Неверный город")

            # Клик по городу
            if not self._wd_ac_click_elem(city):
                self.logger.error("Не могу нажать на кнопку выбора города")
                return False

            self.logger.info("Клик по городу")

            # Получить список всех городов и если есть нужный, кликнуть по нему
            city_list = self._wd_find_all_elems_with_timeout(By.CLASS_NAME, "location-select__location")
            if city_list:
                for item in city_list:
                    if self.current_city.lower() in item.text.lower():
                        time.sleep(1.5)
                        return self._wd_ac_click_elem(item)
            else:
                self.logger.warning("Нет списка городов, попробую вбить вручную")

            # Поиск поля для ввода города
            input_city = self._wd_find_elem_with_timeout(By.CLASS_NAME, "location-select__input-wrap")
            if not input_city:
                self.logger.error("Не найдено поле, куда вводить новый город")
                return False

            # Кликнуть на форму для ввода текста
            time.sleep(1)
            if not self._wd_ac_click_elem(input_city):
                self.logger.error("Не могу нажать на форму ввода текста")
                return False

            # Ввод названия города по буквам
            for char in self.current_city:
                self._wd_ac_send_keys(input_city, char)
                time.sleep(0.2)

            # Если не поставить задержку, окно закрывает, а город не применяет
            time.sleep(1.5)

            # Выбор города из сгенерированного списка городов
            input_city_item = self._wd_find_elem_with_timeout(By.XPATH, "//li[@databases-index='0']")
            if not input_city_item:
                self.logger.error("Не найдено элементов при вводе города")
                return False

            # Клик по нему
            if not self._wd_ac_click_elem(input_city_item):
                self.logger.error("Не могу нажать на выбранный город")
                return False

        return True

    def _wd_city_selection_product(self):
        """
        Алгоритм выбора города для всех возможных ситуаций для страницы продукта
        """
        pass

    def _wd_check_load_page_catalog(self):
        """
        Проверка по ключевым div-ам что страница каталога прогружена полностью
        """
        # Ожидание прогрузки пагинации
        if not self._wd_find_elem_with_timeout(By.CLASS_NAME, "pagination"):
            return False

        # Ожидание прогрузки цен
        if not self._wd_find_elem_with_timeout(By.CLASS_NAME, "price__main-value"):
            return False

        # Ожидание прогрузки изображения товара
        if not self._wd_find_elem_with_timeout(By.CLASS_NAME, "product-picture__img"):
            return False

        # Ожидание прогрузки переключателя вида товара
        if not self._wd_find_elem_with_timeout(By.XPATH, "//div[@class='listing-view-switcher__inner-area']"):
            return False

        self.logger.info("Page loaded")
        return True

    def _wd_check_load_page_product(self):
        """
        Проверка по ключевым div-ам что страница товара прогружена полностью
        """
        pass

    def __wd_select_list_view(self):
        """
        Переключение на отображение товаров в виде списка
        """
        # Если есть этот тег в html коде, значит сейчас стоит табличный вид, переключаем на список
        if self._wd_find_elem(By.XPATH,
                              "//div[@class='listing-view-switcher__pointer listing-view-switcher__pointer--grid']"):
            # Переключение с табличного вида на список
            listing_views = self._wd_find_elem_with_timeout(By.XPATH,
                                                            "//div[@class='listing-view-switcher__inner-area']")
            if not listing_views:
                self.logger.error("Не могу найти listing views")
                return False

            # Клик
            if not self._wd_ac_click_elem(listing_views):
                self.logger.error("Не могу нажать на кнопку в __select_list_view")
                return False

        # Но если нет и тега list (вид списка) - то ошибка
        elif not self._wd_find_elem(By.XPATH,
                                    "//div[@class='listing-view-switcher__pointer "
                                    "listing-view-switcher__pointer--list']"):
            self.logger.error("Не вижу тегов для переключения вида товара")
            return False

        return True

    def __wd_mvideo_switch_num_prod_in_catalog(self):
        """
        Метод только для мвидео. Переключает кол-во отображаемых товаров на
        странице каталога с 24 до 72
        """
        # Найти кнопку выбора кол-ва товаров на странице
        but_show24 = self._wd_find_elem_with_timeout(By.XPATH, "//span[contains(text(),'Показывать по 24')]")
        if but_show24:
            self._wd_ac_click_elem(but_show24)
            item_show72 = self._wd_find_elem_with_timeout(By.XPATH, "//div[contains(text(),'Показывать по 72')]")

            # Переключиться на 72 товара на странице
            if item_show72:
                self._wd_ac_click_elem(item_show72)

    def _wd_open_browser_catalog(self, url):
        """
        Запуск браузера, загрузка начальной страницы каталога, выбор города
        """
        if not super()._wd_open_browser_catalog(url):
            return False

        # Переключение на отображение товаров в виде списка
        if not self.__wd_select_list_view():
            self.logger.error("Не смог переключить отображение товара в виде списока")
            return False

        self._wd_scroll_down(count_press=13)
        self.__wd_mvideo_switch_num_prod_in_catalog()

        # Ждем, пока не прогрузится страница
        if not self._wd_check_load_page_catalog():
            self.logger.error("Не удалось прогрузить страницу в __wd_open_browser (2)")
            return False

        # Скролл
        self._wd_scroll_down(count_press=35)
        return True

    def _wd_open_browser_product(self, url):
        """
        Запуск браузера, загрузка начальной страницы парсинга, выбор города
        """
        pass

    def _wd_next_page(self):
        """
        Переход на заданную страницу num_page через клик (для имитации пользователя)
        """
        for num_try in range(3):

            if num_try and not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (1)")
                self.driver.refresh()
                continue

            # Поиск следующей кнопки страницы
            num_page_elem = self._wd_find_elem(By.XPATH, "//li[@class='page-item number-item ng-star-inserted']/"
                                                         "a[text()={}]".format(self.cur_page))
            if not num_page_elem:
                self.logger.info("Достигнут конец каталога")
                return False

            # Клик - переход на следующую страницу
            if not self._wd_ac_click_elem(num_page_elem):
                self.logger.error("Не могу кликнуть на страницу в __wd_next_page")
                return False

            # Специальная задержка между переключениями страниц для имитации юзера
            time.sleep(self.wait_between_pages_sec)

            # Скролл вниз
            self._wd_scroll_down(count_press=35)

            no_in_stock = self._wd_find_all_elems(By.XPATH, '//div[contains(text(), "Нет в наличии")]')
            if no_in_stock and len(no_in_stock) == 72:
                self.logger.info("Вся страница неактуальна, выход")
                return False

            # Ждем, пока не прогрузится страница
            if not self._wd_check_load_page_catalog():
                self.logger.error("Не удалось прогрузить страницу в __wd_next_page (2)")
                self.driver.refresh()
                continue

            # Особенность МВидео - при переключении страницы, пока сайт ждет ответ от сервера,
            # оставляет старые данные с эффектом размытия. Ждем, пока они не исчезнут
            try:
                self.wait.until_not(ec.presence_of_element_located((By.XPATH, "//a[@href='{}']".format(
                    self.pr_result_list[-5].url))))
            except se.TimeoutException:
                self.logger.error('Не пропадает телефон с прошлой страницы, не могу прогрузить текущую')
                self.driver.refresh()
                continue
            except IndexError:
                self.logger.error(
                    'По непонятной причине список pr_result_list[-5] оказался пуст, выход за границы списка')
                return False

            self.cur_page += 1
            return True
        else:
            self.logger.error("!! После 3 попыток не получилось переключить страницу #{} !!".format(self.cur_page))
            return False

    def _parse_product_page(self, html, url):
        """
        Метод для парсинга html страницы продукта
        """
        pass

    def _parse_catalog_block(self, block):
        """
        Метод для парсинга html страницы товара
        """
        # Название модели и URL
        model_name_url_block = block.select_one('a.product-title__text')

        # Проверка на баг мвидео - наличие в названии модели фразы PDA
        if model_name_url_block and ('pda' in model_name_url_block.text.lower()):
            self.logger.warning("PDA detected")
            return

        if not model_name_url_block:
            self.logger.warning("No model name and URL")
            return
        else:
            url = model_name_url_block.get('href')
            full_name = model_name_url_block.text.replace('\n', '').strip()

        # Чек
        if not [item.text for item in block.select('span') if ("В корзину" in item.text)]:
            self.logger.info("Нет кнопки 'В корзину', {} {}".format(full_name, url))
            return

        # Проверка на предзаказ
        if [item.text for item in block.select("span.button__label.ng-star-inserted") if item.text == "Предзаказ"]:
            self.logger.info("Товар '{}' по предзаказу, пропуск".format(full_name))
            return

        # Проверка на наличие
        if [item.text for item in block.select("div.product-notification") if "Нет в наличии" in item.text]:
            self.logger.info("Товара '{}' нет в наличии, пропуск".format(full_name))
            return

        # Ссылка на изображение товара
        img_url = block.select_one('img.product-picture__img.product-picture__img--list')
        if not img_url:
            self.logger.warning("No img url")
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
            self.logger.warning("No RAM and ROM")
            return
        else:
            for item in specifications:
                if "ram" in item.text.lower():
                    ram = int(re.findall(r'\d+', item.text)[0])
                if "rom" in item.text.lower():
                    rom = int(re.findall(r'\d+', item.text)[0])

        print("!!!!!{} {} {} {} {} {} {}!!!!!".format(full_name, ram, rom,
                                                      img_url, url, rating, num_rating))

        # Парсинг цен
        promo_price = block.select_one('p.price__main-value.price__main-value--old')
        # Если есть блок акции - берем цену с него
        if promo_price:
            price = int(re.findall(r'\d+', promo_price.text.replace(u'\xa0', ''))[0])
        else:
            price = block.select_one('p.price__main-value')
            if not price:
                self.logger.warning("No price")
                return
            else:
                price = int(re.findall(r'\d+', price.text.replace(u'\xa0', ''))[0])

        # Код продукта
        if len(url) > 8:
            product_code = url[-8:]
        else:
            self.logger.warning("No product code")
            return

        # Парсинг названия модели
        brand_name, model_name, color = mvideo_parse_model_name(full_name)
        if not brand_name or not model_name or not color:
            self.logger.warning("No brand name, model name, color or not in the list of allowed")
            return

        # Добавление полученных результатов в коллекцию
        self._add_to_pr_result_list(brand_name, model_name, color, price, ram, rom,
                                    img_url, url, rating, num_rating, product_code)


if __name__ == '__main__':
    import main

    time_start = time.time()
    # main.load_allowed_model_names_list_for_base()
    # main.load_exceptions_model_names()
    # main.read_config()

    parser = MVideoParse()
    parser.run_catalog('https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc')
    logger.info(f"Время выполнения: {time.time() - time_start} сек")

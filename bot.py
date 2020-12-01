import telebot
from telebot import types
import configparser
import header as h
import csv
import collections
import datetime
import requests
import time
from PIL import Image, ImageDraw

logger = h.logging.getLogger('bot')

SHOP_NAMES = [
    'М.видео',
    'Эльдорадо',
    'DNS',
    'DNS Технопоинт',
    'МТС',
    'Ситилинк',
    'RBT.ru',
    'Онлайнтрейд',
    'Связной',
    'ТехноСити',
    'Билайн',
    'МегаФон',
    'е2е4',
    'НОУ-ХАУ',
    're:Store',
    'Официальный интернет-магазин Samsung',
    'Официальный интернет-магазин Huawei',
    'Ozon',
    'Wildberries',
    'Sony Store',
    'Tmall',
]


def image_change(url):
    W, H = 640, 480
    # Загрузить изображение с url
    try:
        resp = requests.get(url, stream=True).raw
    except requests.exceptions.RequestException as e:
        logger.error("Can't get img from url :(")
        return None

    # Попытка открыть изображение средствами PIL
    try:
        img = Image.open(resp)
    except IOError:
        logger.error("Unable to open image")
        return None

    # Если высота не соответствует H - изменение размера изображения с учетом пропорций
    if img.height != H:
        width, height = img.size
        new_height = H
        new_width = int(new_height * width / height)
        img = img.resize((new_width, new_height), Image.ANTIALIAS)

    im = Image.new('RGB', (W, H), color='#FFFFFF')
    im.paste(img, (int((W - img.width) / 2), 0), 0)

    return im
    #img.save('sid.jpg', 'jpeg')


def wrap_in_tag(tag, text):
    return '<{}>{}</{}>'.format(tag, text, tag)


def del_duplicates_in_pc_prod_list(elements):
    result = []
    for item in elements:
        if not result.count(item):
            result.append(item)
    return result


def find_all_versions_in_pc_prod_list(elements, brand_name, model_name, ram, rom, cur_price):
    result = []
    for item in elements:
        if item.brand_name == brand_name and \
                item.model_name == model_name and \
                item.ram == ram and \
                item.rom == rom and \
                item.cur_price == cur_price:
            result.append(item)

    return result


def find_all_shops_in_pc_prod_list(elements, shop):
    result = []
    for item in elements:
        if item.shop == shop:
            result.append(item)

    return result


class Bot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.chat_id = self.config['bot']['chat_id']
        self.ignore_brands = self.config['bot-ignore']['brands'].lower().split('\n')
        self.bot = telebot.TeleBot(self.config['bot']['token'])
        self.one_star_per = int(self.config['bot-stars']['one_star_per'])
        self.two_star_per = int(self.config['bot-stars']['two_star_per'])
        self.three_star_per = int(self.config['bot-stars']['three_star_per'])
        self.four_star_per = int(self.config['bot-stars']['four_star_per'])
        self.five_star_per = int(self.config['bot-stars']['five_star_per'])
        self.pc_product_list = []

    # Подготовка текста для поста
    def __format_text(self, version_list):
        product = version_list[0]
        # НАЗВАНИЕ МОДЕЛИ
        text = '<b>{} {} {}</b>\n'.format(
            product.category[0:-1].title(), product.brand_name.title(), product.model_name.title())

        # КОМПЛЕКТАЦИЯ
        text += '<b>{}/{} GB</b>\n\n'.format(product.ram, product.rom)

        # ОГОНЬКИ
        per = 100 - product.cur_price / product.avg_actual_price * 100
        if per <= self.one_star_per:
            star = 1
        elif per <= self.two_star_per:
            star = 2
        elif per <= self.three_star_per:
            star = 3
        elif per <= self.four_star_per:
            star = 4
        elif per <= self.five_star_per:
            star = 5
        else:
            star = 6

        logger.info("{} ЗВЕЗД".format(star))
        text += '🔥' * star
        text += '\n'

        # ЦЕНА
        # text += '⭐⭐⭐\n'
        # text += '🍪🍪🍪\n'
        # text += '👑👑👑\n'
        # text += '💎💎💎\n'
        # text += '💥💥💥\n'
        # text += '🌞🌞🌞\n'
        # text += '🔴🔴🔴\n'
        # text += '🚩🚩🚩\n'
        s_price = '{0:,}'.format(product.cur_price).replace(',', ' ')
        text += 'Выгодная цена: <b><i>{}</i></b> ₽\n'.format(s_price)
        s_price = '{0:,}'.format(int(product.avg_actual_price - product.cur_price))
        text += '<i>(Дешевле на {}</i> ₽<i>)</i>\n\n'.format(s_price).replace(',', ' ')

        # ИСТОРИЧЕСКИЙ МИНИМУМ
        if product.cur_price <= product.hist_min_price:
            text += '<i>Данная цена является самой низкой за всё время</i>\n'
        else:
            date_time = datetime.datetime.strptime(str(product.hist_min_date), '%Y-%m-%d %H:%M:%S.%f').strftime('%d.%m.%Y')
            s_price = '{0:,}'.format(product.hist_min_price).replace(',', ' ')
            text += '<i>Минимальная цена {}</i> ₽ <i>была {} в {}</i>\n'.format(
                s_price, SHOP_NAMES[product.hist_min_shop - 1], date_time)

        # СПИСОК ССЫЛОК ДЛЯ ПОКУПКИ
        shops_set = list(set(item.shop for item in version_list))

        # Группировка позиций по магазину и создание списка ссылок на разные магазины с разными цветами
        hashtag_shops = ''
        links_shop_list = []
        for shop in shops_set:
            # Генерация тегов магазинов
            hashtag_shops += '#' + h.SHOPS_NAME_LIST[shop - 1][0] + ' '

            # Генерация ссылок
            urls = ''
            for product in version_list:
                if product.shop == shop:
                    urls += '<a href="{}">› {}</a>\n'.format(product.url, product.color.title())  # → ► ● ○ • ›
            links_shop_list.append(urls)

        # Генерация ссылок
        indx = 0
        for link_set in links_shop_list:
            text += '\nКупить в <b><u>{}</u></b>:\n'.format(SHOP_NAMES[shops_set[indx] - 1])
            text += link_set
            indx += 1

        # ХЭШТЕГИ
        text += '\n' + '#' + product.brand_name + ' ' + hashtag_shops

        return text

    # Открывает csv файл и, с учетом фильтра, выбирает позиции
    def prepare_data_to_send(self):
        pass

    def get_data(self):
        with open(h.PRICE_CHANGES_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.pc_product_list.append(h.PriceChanges(
                    shop=int(row['Магазин']),
                    category=row['Категория'],
                    brand_name=row['Бренд'],
                    model_name=row['Модель'],
                    color=row['Цвет'],
                    ram=int(row['RAM']),
                    rom=int(row['ROM']),
                    img_url=row['Ссылка на изображение'],
                    url=row['Ссылка'],
                    date_time=row['Дата и время'],
                    cur_price=int(row['Текущая цена']),
                    avg_actual_price=float(row['Средняя цена']),
                    hist_min_price=int(row['Историческая мин. цена']),
                    hist_min_shop=int(row['Исторический мин. магазин']),
                    hist_min_date=row['Исторический мин. дата'],
                    diff_cur_avg=int(row['Разница цены от средней']),
                ))

        logger.info(self.pc_product_list)
        logger.info('-' * 100)

    # Фильтрация входных данных - удаление дубликатов и применение игнор-листа
    def filtering_data(self):
        # Удалить дубликаты, если имеются
        self.pc_product_list = del_duplicates_in_pc_prod_list(self.pc_product_list)

        # Удалить товары, если его бренд имеется в игнор-листе
        result = []
        for item in self.pc_product_list:
            if not self.ignore_brands.count(item.brand_name):
                result.append(item)

        self.pc_product_list = result

    def post_all(self):

        # Проход по всему списку, группировка элементов по версии и цвету, пост группы
        while self.pc_product_list:
            # Взятие группы комплектации с разными цветами
            item = self.pc_product_list[0]
            version_list = find_all_versions_in_pc_prod_list(self.pc_product_list, item.brand_name, item.model_name,
                                                             item.ram, item.rom, item.cur_price)

            self.send_post(version_list)
            time.sleep(1)

            # Удаление из основного списка взятой группы version_list
            for item in version_list:
                self.pc_product_list.remove(item)

    def send_post(self, version_list):
        item = version_list[0]
        text = self.__format_text(version_list)
        img = image_change(item.img_url)
        # Отправка поста в обертке
        for i in range(3):
            try:
                self.bot.send_photo(chat_id=self.chat_id, photo=img, caption=text, parse_mode='Html')
                break
            except telebot.apihelper.ApiException:
                logger.warning("Слишком много постов в телеграм, ожидаем 40 сек, ({})".format(i + 1))
                time.sleep(20)

    # Запуск бота
    def run(self, pc_product_list):
        if not pc_product_list:
            logger.info("НЕТ ДАННЫХ ДЛЯ TELEGRAM")
            return
        # self.get_data()
        self.pc_product_list = pc_product_list
        self.filtering_data()
        self.post_all()

# @bot.message_handler(commands=['start'])
# def start_handler(message):
#     bot.send_message(message.from_user.id, start_mess)

# bot.polling(none_stop=True, interval=0)

# def send_post(text):
#     urls = types.InlineKeyboardMarkup(row_width=1)
#     url_1 = types.InlineKeyboardButton(text='Черный', url='yandex.ru')
#     url_2 = types.InlineKeyboardButton(text='Красный', url='yandex.ru')
#     url_3 = types.InlineKeyboardButton(text='Белый', url='yandex.ru')
#     urls.add(url_1, url_2, url_3)
#     bot.send_photo(chat_id=CHAT_ID, photo='https://c.dns-shop.ru/thumb/st4/fit/200/200/03fbdbd83838fd1e6774a7efeee109a9/a05ad1ff1f69afcfc2b83579e8775712ae86aa15d428d0285637bd7a859bcbfd.jpg', caption=text1, parse_mode='Html', reply_markup=urls)

# bot.send_message(chat_id=CHAT_ID, text=text, reply_markup=urls, parse_mode='Html')
# bot.send_message(chat_id=CHAT_ID, text=text2, parse_mode='Markdown')


# def start():
#     key = types.InlineKeyboardMarkup()
#     key_1 = types.InlineKeyboardButton(text='123', callback_data='123')
#     key_2 = types.InlineKeyboardButton(text='yandex', url='yandex.ru')
#     key.add(key_1)
#     key.add(key_2)
#     bot.send_message(CHAT_ID, 'test text', reply_markup=key)
#
#
# @bot.callback_query_handler(func=lambda call: True)
# def callback_inline(call):
#     if call.data == '123':
#         print('нажали 123 в канале')


# def fun():
#     text = 'CI Test Message'
#     markup = types.InlineKeyboardMarkup()
#     itembtn1 = types.InlineKeyboardButton('a')
#     itembtn2 = types.InlineKeyboardButton('v')
#     itembtn3 = types.InlineKeyboardButton('d')
#     markup.add(itembtn1, itembtn2, itembtn3)
#     bot.send_message(CHAT_ID, "Choose one letter:", reply_markup=markup)
#     # ret_msg = bot.send_message(chat_id=CHAT_ID, text=markdown, reply_markup=markup)


# bot.send_message(chat_id=CHAT_ID, text=markdown, parse_mode="Markdown")

# send_post(text1)

# bot.polling(none_stop=True, interval=0)
# https://api.telegram.org/bot1210851644:AAH4hHnJVtzdCSoT6qOBkXjgtLssysqQnPE/sendMessage?chat_id=-1001227686108&text=123
# {"ok":true,"result":{"message_id":8,"chat":{"id":-1001227686108,"title":"\u041f\u0440\u043e\u0434\u0430\u0432\u0430\u0447","username":"adfrews","type":"channel"},"date":1604056040,"text":"123"}}


# config1 = configparser.ConfigParser() # empty_lines_in_values=False
# config1.read("conf.ini")

# print(config1["bot-ignore"]["brand"])

#
#
# bot = Bot()
# bot.send_post("samsung", "note 10 ultra", 59999, "dns",
#               "https://c.dns-shop.ru/thumb/st4/fit/200/200/03fbdbd83838fd1e6774a7efeee109a9/a05ad1ff1f69afcfc2b83579e8775712ae86aa15d428d0285637bd7a859bcbfd.jpg")


# image_change('https://img.mvideo.ru/pdb/small_pic/480/30045359b.jpg')
# image_change('https://c.dns-shop.ru/thumb/st1/fit/200/200/6894029a9c81f3cf3257d2d2483935ec/5301b91d8e758695b85d0ee1a20f7b46cd56cbecc7dd1628b76f45630190b242.jpg')

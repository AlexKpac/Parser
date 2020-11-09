import telebot
from telebot import types
import configparser
import header as h
import csv
import collections

logger = h.logging.getLogger('bot')


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


class Bot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.chat_id = self.config['bot']['chat_id']
        self.ignore_brands = self.config['bot-ignore']['brands'].lower().split('\n')
        print(self.ignore_brands)
        self.bot = telebot.TeleBot(self.config['bot']['token'])
        self.pc_product_list = []

    # Обертка строки в html теги

    # Подготовка текста для поста
    def __format_text(self, version_list):
        # Ссылки

        list_one_shop = []
        while version_list:
            shop
        urls = ''
        for item in version_list:
            urls += '<a href="{}">{}</a>\n'.format(item.url, item.color.title())

        item = version_list[0]

        # Заголовок
        full_name = item.brand_name.title() + ' ' + item.model_name.title()
        text = wrap_in_tag('b', full_name) + '\n\n'
        # Цена
        s_price = '{0:,}'.format(item.cur_price).replace(',', ' ')
        text += 'Цена: ' + wrap_in_tag('i', s_price) + ' ₽' + '\n\n'

        sshop = h.SHOPS_NAME_LIST[item.shop-1][0]

        # Теги
        text += '#' + item.shop + '\n#' + item.brand_name

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

        print(self.pc_product_list)
        print('-' * 100)

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

            # Удаление из основного списка взятой группы version_list
            for item in version_list:
                self.pc_product_list.remove(item)

    def send_post(self, version_list):

        item = version_list[0]

        text = self.__format_text(version_list)
        print(text)
        self.bot.send_photo(chat_id=self.chat_id, photo=item.img_url, caption=text, parse_mode='Html') #, reply_markup=urls)

    # Запуск бота
    def run(self):
        self.get_data()
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

import re
import csv
import configparser
import time
from datetime import datetime

# from telethon.sync import TelegramClient, events
# import header as h

from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler

SHOP_NAME_LIST = ['мвидео',
                  'эльдорадо',
                  'dns',
                  'технопоинт',
                  'мтс',
                  'ситилинк',
                  'rbt',
                  'онлайнтрейд',
                  'связной',
                  'техносити',
                  'билайн',
                  'мегафон',
                  'e2e4',
                  'ноу-хау', ]


# ---------------------- СТАТИСТИКА ---------------------- #

# Сгенерировать статистику на основе списка с названиями
def gen_prod_stats(model_name_list):
    stat_dict = {}
    for item in model_name_list:
        name = item.lower()
        if name in stat_dict:
            stat_dict[name] += 1
        else:
            stat_dict[name] = 1

    print("STAT PROD DICT:")
    for key, value in stat_dict.items():
        print('[{}] -> [{}]'.format(key, value))


def gen_shop_and_brand_stats(shops_and_brand_list):
    stat_shop_dict = {}
    stat_brand_dict = {}

    for item in shops_and_brand_list:
        name = item.lower()

        if 'актуально' in name:
            continue

        if name in SHOP_NAME_LIST:
            if name in stat_shop_dict:
                stat_shop_dict[name] += 1
            else:
                stat_shop_dict[name] = 1
        else:
            if name in stat_brand_dict:
                stat_brand_dict[name] += 1
            else:
                stat_brand_dict[name] = 1

    print('-' * 100)
    print("STAT SHOP DICT:")
    for key, value in stat_shop_dict.items():
        print('[{}] -> [{}]'.format(key, value))

    print('-' * 100)
    print("STAT BRAND DICT:")
    for key, value in stat_brand_dict.items():
        print('[{}] -> [{}]'.format(key, value))


# Получить историю всех сообщений в канале
async def get_history(app, channel_name):
    model_name_list = []
    shop_and_brand_list = []
    for msg_id in range(800, 1000):
        res = await app.get_messages(channel_name, msg_id)
        if not res.empty and res.caption and res.caption.startswith('Смартфон'):
            model_name_list.append(res.caption[:res.caption.index('\n')].replace('Смартфон ', ''))
            shop_and_brand_list.extend([w.replace('#', '') for w in res.caption.split() if w.startswith('#')])

        # ПОЛУЧЕНИЕ ЦЕНЫ ПОСТА
        # caption = res.caption
        # if caption and 'Выгодная цена' in caption:
        #     price = re.findall(r'Выгодная цена: ([\d ]+) ₽', caption)
        #     print(price)

        # ПОЛУЧЕНИЕ ССЫЛОК ПОСТА
        # if res.caption_entities:
        #     for it1em in res.caption_entities:
        #         if 'text_link' in it1em.type:
        #             print(it1em.url)

    gen_prod_stats(model_name_list)
    gen_shop_and_brand_stats(shop_and_brand_list)


# Получить статистику встречаемости всех моделей телефонов в канале
def get_product_stats(channel_name):
    with Client("my_account") as app:
        app.loop.run_until_complete(get_history(app, channel_name))


####################################################################

# Преобразовать текст бота в набор ссылок
def get_deeplinks_from_resp(text):
    if not text:
        return None

    deeplink_list = []
    paragraph_list = text.split('For link: ')
    for paragraph in paragraph_list:
        orig_link = re.findall(r'https:\/\/www[\w\/.-]+', paragraph)
        deep_link = re.findall(r'https:\/\/lite[\w\/.-]+', paragraph)

        if not orig_link:
            continue

        deep_link = deep_link[0] if deep_link else orig_link[0]
        deeplink_list.append(deep_link)

    return deeplink_list


class UserBot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.time_wait_resp_from_bot_sec = 30
        # self.api_id = int(self.config['userbot']['api_id'])
        # self.api_hash = self.config['userbot']['api_hash']

    async def __get_resp_from_bot(self, app, url_list):
        urls = ' '.join(url_list)

        # Отправка ссылок боту и получение id сообщения-ответа
        res = await app.send_message("@admitad_bot", text=urls)
        message_id = res.message_id + 1

        # Ожидание ответа бота
        print("Жду ответа от пользователя @admitad_bot")
        time_start = time.time()

        while True:
            res = await app.get_messages("@admitad_bot", message_id)
            if not res.empty:
                print("Ответ от @admitad_bot получен, время ожидания: {} сек".format(time.time() - time_start))
                return res.text

            if (time.time() - time_start) > self.time_wait_resp_from_bot_sec:
                print("Ответа не было {} сек, выход".format(self.time_wait_resp_from_bot_sec))
                return None

            time.sleep(0.5)

    def get_deeplinks(self, url_list):

        with Client("my_account") as app:
            text = app.loop.run_until_complete(self.__get_resp_from_bot(app, url_list))
            deeplink_list = get_deeplinks_from_resp(text)

        for item in deeplink_list:
            print(item)


########################################################################################################


list_url = ['https://www.mvideo.ru/products/smartfon-apple-iphone-11-64gb-product-red-mwlv2ru-a-30045359',
            'https://www.mvideo.ru/products/smartfon-apple-iphone-xs-max-512gb-silver-mt572ru-a-30040030',
            'https://www.dns-shop.ru/product/0c003137a5613332/657-smartfon-realme-x3-superzoom-128-gb-belyj/',
            'https://www.mvideo.ru/products/smartfon-apple-iphone-11-128gb-green-mwm62ru-a-30045428',
            'https://www.dns-shop.ru/product/f5c05c4fd6323332/584-smartfon-blackview-bv9900e-128-gb-seryj/']

# bot = UserBot()
# bot.get_history()
# bot.get_deeplinks(list_url)

# get_product_stats('prodavach_nsk')

listr = ['Смартфон Samsung Galaxy Note20',
         'Смартфон Honor 10X Lite',
         'Смартфон Samsung Galaxy Note20 Ultra',
         'Смартфон Honor 9C',
         'Смартфон Honor 30 Premium',
         'Смартфон Honor 30',
         'Смартфон Samsung Galaxy S20 FE',
         'Смартфон Honor 30i',
         'Смартфон Honor 30i',
         'Смартфон Honor 9C',
         'Смартфон Honor 9A',
         'Смартфон Samsung Galaxy S20 FE',
         'Смартфон Samsung Galaxy S10',
         'Смартфон Samsung Galaxy S10',
         'Смартфон Samsung Galaxy M11',
         'Смартфон Honor 9X Premium',
         'Смартфон Samsung Galaxy M51',
         'Смартфон Samsung Galaxy S10',
         'Смартфон Samsung Galaxy S10',
         'Смартфон Samsung Galaxy S10+',
         'Смартфон Samsung Galaxy Z Flip',
         'Смартфон realme 6s',
         'Смартфон Samsung Galaxy A41',
         'Смартфон Samsung Galaxy S10+',
         'Смартфон realme X3 SuperZoom',
         'Смартфон realme X3 SuperZoom',
         'Смартфон Huawei P40 Pro',
         'Смартфон Samsung Galaxy Z Flip',
         'Смартфон Samsung Galaxy Note20',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Samsung Galaxy S20',
         'Смартфон Samsung Galaxy Note20 Ultra',
         'Смартфон Apple iPhone 8',
         'Смартфон Apple iPhone 11 Pro',
         'Смартфон Samsung Galaxy S10+',
         'Смартфон Samsung Galaxy S20',
         'Смартфон Samsung Galaxy Note20',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Apple iPhone XR',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Huawei P40 lite',
         'Смартфон OPPO Reno3',
         'Смартфон Huawei P40 lite',
         'Смартфон Samsung Galaxy A41',
         'Смартфон OPPO Reno4 Lite',
         'Смартфон realme X3 SuperZoom',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Honor 10i',
         'Смартфон vivo Y11',
         'Смартфон vivo Y20',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Nokia 5.3',
         'Смартфон Honor 20e',
         'Смартфон Samsung Galaxy A41',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Samsung Galaxy A71',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Samsung Galaxy A51',
         'Смартфон Nokia 5.3',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy Note10 Lite',
         'Смартфон Samsung Galaxy Note20',
         'Смартфон Samsung Galaxy Note20 Ultra',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy M51',
         'Смартфон Apple iPhone 8',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy A21s',
         'Смартфон Samsung Galaxy A41',
         'Смартфон Vsmart Joy 4',
         'Смартфон Xiaomi Redmi 9A',
         'Смартфон Xiaomi Redmi 9C',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Samsung Galaxy Note20',
         'Смартфон Samsung Galaxy Note20 Ultra',
         'Смартфон realme 6 Pro',
         'Смартфон Honor 20 Lite',
         'Смартфон Samsung Galaxy A41',
         'Смартфон Samsung Galaxy Note10 Lite',
         'Смартфон Xiaomi Redmi Note 9',
         'Смартфон Xiaomi Redmi Note 8 Pro']

text1 = """For link: https://www.mvideo.ru/products/smartfon-apple-iphone-6-16gb-gold-mg492ru-a-30020955
Admitad Lite program: Mvideo RU
Deeplink: https://lite.al/FeZxI

For link: https://www.mvideo.ru/products/smartfon-apple-iphone-xs-max-512gb-silver-mt572ru-a-30040030
Admitad Lite program: Mvideo RU
Deeplink: https://lite.al/pkOXi

For link: https://www.mvideo.ru/products/smartfon-apple-iphone-xs-256gb-silver-mt9j2ru-a-30040018
Admitad Lite program: Mvideo RU
Deeplink: https://lite.bz/rzEp1

For link: https://www.dns-shop.ru/product/ae361d5feb6e3332/644-smartfon-vivo-v20-128-gb-sinij/
No affiliate program for this link found on Admitad
"""

# def get_deeplink(self, url):
#     with TelegramClient('name', self.api_id, self.api_hash) as client:
#
#         @client.on(events.NewMessage())
#         async def handler(event):
#
#             # print(event.text)
#             deeplink = re.findall(r'https:\/\/lite[\w\/.]+', event.text)
#             print(deeplink)
#             await client.disconnected()
#             return "!!!!!!!!!!"
#
#
#         # client.add_event_handler(handler, events.NewMessage)
#
#         # client.send_message('@admitad_bot', url)
#
#         print(*client.iter_messages("@admitad_bot"))
#
#
#         # for message in client.iter_messages("@admitad_bot"):
#         #     print(message.sender_id, ':', message.text)
#
#         # res = client.run_until_disconnected()
#         # print(res)
#
# def get_deeplinks(self, list_url):
#     pass

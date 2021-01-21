import re
import csv
import configparser
import time
from datetime import datetime

# from telethon.sync import TelegramClient, events
# import header as h

from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler


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

bot = UserBot()
bot.get_deeplinks(list_url)


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

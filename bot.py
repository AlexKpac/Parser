import telebot
from telebot import types
import configparser


class Bot:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('conf.ini', encoding="utf-8")
        self.chat_id = self.config['bot']['chat_id']
        self.bot = telebot.TeleBot(self.config['bot']['token'])

    # Обертка строки в html теги
    def __wrap_in_tag(self, tag, text):
        return '<{}>{}</{}>'.format(tag, text, tag)

    # Подготовка текста для поста
    def __format_text(self, brand_name, model_name, cur_price, shop):
        # Заголовок
        full_name = brand_name.title() + ' ' + model_name.title()
        text = self.__wrap_in_tag('b', full_name) + '\n\n'
        # Цена
        s_price = '{0:,}'.format(cur_price).replace(',', ' ')
        text += 'Цена: ' + self.__wrap_in_tag('i', s_price) + ' ₽' + '\n\n'
        # Теги
        text += '#' + shop + '\n#' + brand_name

        return text

    # Открывает csv файл и, с учетом фильтра, выбирает позиции
    def prepare_data_to_send(self):
        pass

    # Отправка поста
    def send_post(self, brand_name, model_name, cur_price, shop, img_url):
        text = self.__format_text(brand_name, model_name, cur_price, shop)
        self.bot.send_photo(chat_id=self.chat_id, photo=img_url, caption=text, parse_mode='Html')  # reply_markup=urls)


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

bot = Bot()
bot.send_post("samsung", "note 10 ultra", 59999, "dns",
              "https://c.dns-shop.ru/thumb/st4/fit/200/200/03fbdbd83838fd1e6774a7efeee109a9/a05ad1ff1f69afcfc2b83579e8775712ae86aa15d428d0285637bd7a859bcbfd.jpg")

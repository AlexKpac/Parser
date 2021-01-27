import time
import telebot
import threading
import os
import header as h

TOKEN = '1511696373:AAFr9Ys56bgn2EKPEGBG9_H0OhsVHZyCgiE'
CHAT_ID = -1001336090621

TEXT_MODEL_NAME = "<b>{}</b>"
TEXT_IT_NEED_TO_APPROVE = "<b>УТВЕРДИТЬ</b> название название модели <b>'{}'</b>?"
TEXT_IT_NEED_TO_CHANGE = "<b>ИЗМЕНИТЬ</b> название модели <b>'{}'</b>?"
TEXT_APPROVED = "Название модели <b>'{}'</b> <i><b>утверждено</b></i>"
TEXT_ENTER_TRUE_NAME = "Введите правильное название для модели: '{}'"
TEXT_CHANGED = "Название модели <b>'{}'</b> <i><b>изменено</b></i> на <b>'{}'</b>"

PATH = 'C:/Py_Projects/ParserOnlineShop/'
PATH_UNDEFINED_MODEL_NAME_LIST = PATH + 'data/undefined_model_name.dat'
PATH_LIST_MODEL_NAMES_BASE = PATH + 'data/list_model_names_base.dat'
PATH_EXCEPT_MODEL_NAMES = PATH + 'dictionaries/except_model_names.dic'
PATH_EXCEPT_MODEL_NAMES_TELEGRAM = PATH + 'dictionaries/except_model_names_telegram.dic'
PATH_MODEL_NAME_MSG_IN_TELEGRAM = 'msg_in_telegram.dat'

LINE_BEFORE_INSERT = '[Iphone] -> [iPhone]'
BRAND_NAME_LIST = ['iphone', 'realme', 'vivo', 'oppo', 'zte']

is_running = False
is_waiting_approve = False

bot = telebot.TeleBot(TOKEN)


# Клавиатура для первоначального выбора ДА или НЕТ
def get_keyboard_yes_no(model_name):
    yes_no_keys = telebot.types.InlineKeyboardMarkup(row_width=2)
    yes_no_keys.add(telebot.types.InlineKeyboardButton('Утвердить', callback_data='Yes' + model_name),
                    telebot.types.InlineKeyboardButton('Изменить', callback_data='No' + model_name))

    return yes_no_keys


# Клавиатура с подвтерждением выбора
def get_keyboard_approve_back(model_name, who):
    approve_back_keys = telebot.types.InlineKeyboardMarkup(row_width=2)
    approve_back_keys.add(telebot.types.InlineKeyboardButton('Да', callback_data='Approve' + who + model_name),
                          telebot.types.InlineKeyboardButton('Отмена', callback_data='Back' + model_name))

    return approve_back_keys


# Сохранить утвержденное название (в список разрешенных)
def save_approved_model_name(model_name):
    with open(PATH_LIST_MODEL_NAMES_BASE, 'a', encoding='UTF-8') as f:
        f.write(model_name.lower() + '\n')


# Сохранить измененное название (в словарь)
def save_changed_model_name(prev_model_name, new_model_name):
    with open(PATH_EXCEPT_MODEL_NAMES, 'a', encoding='UTF-8') as f:
        f.write('[{}] -> [{}]\n'.format(prev_model_name.lower(), new_model_name.lower()))


# Сохранить в словарь телеграма
def save_true_letter_case_from_telegram(prev_model_name, new_model_name):

    for item in BRAND_NAME_LIST:
        # Если в названии предыдущей модели есть слово из списка брендов
        if item in prev_model_name.lower():

            indx = prev_model_name.lower().index(item) + len(item)
            if prev_model_name[indx:] == new_model_name[indx:]:
                print('Названия отличаются только по бренду, выход: "{}"="{}"'.format(prev_model_name, new_model_name))
                return

            print('Названия отличаются не только по бренду - добавляем в файл')
            break

    # Чтение всего файла одной строкой
    with open(PATH_EXCEPT_MODEL_NAMES_TELEGRAM, 'r', encoding='UTF-8') as f:
        data_in_file = f.read()

    # Проверка на дубликат
    new_line = '[{}] -> [{}]\n'.format(prev_model_name.lower().title(), new_model_name)
    if new_line in data_in_file:
        print('Такая запись уже есть, выход')
        return

    # Запись новой строчки в файл
    indx = data_in_file.index(LINE_BEFORE_INSERT)
    with open(PATH_EXCEPT_MODEL_NAMES_TELEGRAM, 'w', encoding='UTF-8') as f:
        f.write(data_in_file[:indx] + new_line + data_in_file[indx:])


@bot.message_handler(content_types=['text'])
def text_messages(message):
    global is_running, is_waiting_approve
    if not is_running or is_waiting_approve:
        print("Удаляю лишние сообщения = '{}'".format(message.text))
        bot.delete_message(message.chat.id, message.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('Yes'))
def yes_callback(query):
    global is_running, is_waiting_approve
    bot.answer_callback_query(callback_query_id=query.id, text='Незаконченное действие' if is_running else None)

    if not is_running:
        is_running = True
        is_waiting_approve = True

        model_name = query.data[3:]
        bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.id,
                              text=TEXT_IT_NEED_TO_APPROVE.format(model_name), parse_mode='html',
                              reply_markup=get_keyboard_approve_back(model_name, 'Yes'))
    else:
        print('Yes_call: is_running is True, skip')


@bot.callback_query_handler(func=lambda call: call.data.startswith('ApproveYes'))
def approve_yes_callback(query):
    global is_running, is_waiting_approve
    bot.answer_callback_query(query.id)

    model_name = query.data[10:]
    bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.id,
                          text=TEXT_APPROVED.format(model_name), parse_mode='html')

    save_approved_model_name(model_name)
    is_waiting_approve = False
    is_running = False


@bot.callback_query_handler(func=lambda call: call.data.startswith('ApproveNo'))
def approve_no_callback(query):
    global is_running, is_waiting_approve
    bot.answer_callback_query(query.id)

    model_name = query.data[9:]
    bot.delete_message(query.message.chat.id, query.message.id)
    msg = bot.send_message(query.message.chat.id, TEXT_ENTER_TRUE_NAME.format(model_name))
    bot.register_next_step_handler(msg, no_answer_get_true_name, (msg.id, model_name))
    is_waiting_approve = False


@bot.callback_query_handler(func=lambda call: call.data.startswith('Back'))
def back_callback(query):
    global is_running, is_waiting_approve
    bot.answer_callback_query(query.id)

    model_name = query.data[4:]
    bot.edit_message_text(TEXT_MODEL_NAME.format(model_name), query.message.chat.id, query.message.id,
                          parse_mode='html', reply_markup=get_keyboard_yes_no(model_name))

    is_running = False
    is_waiting_approve = False


@bot.callback_query_handler(func=lambda call: call.data.startswith('No'))
def no_callback(query):
    global is_running, is_waiting_approve
    bot.answer_callback_query(callback_query_id=query.id, text='Незаконченное действие' if is_running else None)

    if not is_running:
        is_running = True
        is_waiting_approve = True

        model_name = query.data[2:]
        bot.edit_message_text(chat_id=query.message.chat.id, message_id=query.message.id,
                              text=TEXT_IT_NEED_TO_CHANGE.format(model_name), parse_mode='html',
                              reply_markup=get_keyboard_approve_back(model_name, 'No'))
    else:
        print('Yes_call: is_running is True, skip')


# Второй шаг изменения названия
def no_answer_get_true_name(message, args):
    global is_running
    id_msg_post = args[0]
    prev_model_name = args[1]
    new_model_name = message.text
    # Фильтрация названия
    new_model_name = new_model_name.replace("'", '').replace('"', '').replace('  ', ' ').strip()
    text = TEXT_CHANGED.format(prev_model_name, new_model_name)

    # Если слова равны без учета регистра
    if new_model_name.lower() == prev_model_name.lower():
        text = TEXT_APPROVED.format(new_model_name)
    else:
        save_changed_model_name(prev_model_name, new_model_name)

    # Проверка нового названия: автоматический регистр равен ли регистру, который ввел пользователь
    text_as_from_base = new_model_name.lower().title()
    if text_as_from_base != new_model_name:
        text = TEXT_CHANGED.format(prev_model_name, new_model_name)
        save_true_letter_case_from_telegram(text_as_from_base, new_model_name)

    # Удаление поста юзера
    bot.delete_message(message.chat.id, message.id)
    # Изменение поста бота
    bot.edit_message_text(text, message.chat.id, id_msg_post, parse_mode='html')

    # Сохранение результата в файл
    save_approved_model_name(new_model_name)
    is_running = False


def offer_model_for_user(chat_id, model_name):
    try:
        bot.send_message(chat_id, TEXT_MODEL_NAME.format(model_name), parse_mode='html',
                         reply_markup=get_keyboard_yes_no(model_name))

        with open(PATH_MODEL_NAME_MSG_IN_TELEGRAM, 'a', encoding='UTF-8') as f:
            f.write(model_name.lower() + '\n')

    except telebot.apihelper.ApiTelegramException as e:
        print('offer_model_for_user except: {}'.format(e))
        if e.result_json.get('parameters', None):
            time_sleep_sec = int(e.result_json.get('parameters').get('retry_after', 0))
            time.sleep(time_sleep_sec)


# Удалить дубликаты в файле, если имеются
def check_model_name_in_msg(models_list):
    with open(PATH_MODEL_NAME_MSG_IN_TELEGRAM, 'r', encoding='UTF-8') as f:
        model_name_list_in_telegram = f.read().splitlines()

    result = []
    for item in models_list:
        if not model_name_list_in_telegram.count(item.lower()):
            result.append(item)

    return result


def check_new_data_in_file():
    while True:

        # Если есть лок-файл, ждем и повторяем проверку
        if os.path.isfile(h.PATH_UNDEFINED_MODEL_NAME_LIST_LOCK):
            time.sleep(3)
            continue

        print("НОВЫЙ ЦИКЛ")

        # Считывание новых значений с файла
        with open(PATH_UNDEFINED_MODEL_NAME_LIST, 'r', encoding='UTF-8') as f:
            models_list = f.read().splitlines()

        if models_list:
            models_list = [item.lower().title() for item in models_list]
            models_list = list(set(models_list))
            models_list = check_model_name_in_msg(models_list)

            # Очистка файла
            with open(PATH_UNDEFINED_MODEL_NAME_LIST, 'w') as f:
                pass

            for item in models_list:
                offer_model_for_user(CHAT_ID, item)

        time.sleep(300)



if __name__ == '__main__':
    print("Start")
    # time_start = time.time()
    # save_true_letter_case_from_telegram('Iphone Xr восст.', 'iPhone Xr восст')
    # print(f"Время выполнения: {time.time() - time_start} сек")
    # stre = 'Oppo A1K'
    # item = 'oppo'
    # indx = stre.lower().index(item) + len(item)
    # prev = stre[indx:]
    # print(prev)
    check_data_thread = threading.Thread(target=check_new_data_in_file)
    check_data_thread.start()
    bot.polling(none_stop=True, interval=0)

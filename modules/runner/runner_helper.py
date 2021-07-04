import os
import requests
import configparser

import modules.common.helper as h
from modules.common.file_worker import FileWorker

logger = h.logging.getLogger('Runner')


BOT_TOKEN = ''
BOT_CHAT_ID = 0
COUNT_CRASH = 0
MAX_COUNT_CRASH_FOR_ALARM = 3


def load_result_from_csv(name):
    """
    Загрузить данные с csv, чтобы не парсить сайт
    """
    return FileWorker.csv_data.load(h.CSV_PATH_RAW + name, namedtuple_type=h.ParseResult)


def read_config():
    """
    Чтение данных с config.ini
    """
    global BOT_TOKEN, BOT_CHAT_ID

    config = configparser.ConfigParser()
    config.read('config.ini', encoding="utf-8")
    h.REBUILT_IPHONE_NAME = ' ' + config.defaults()['rebuilt_iphone_name']
    h.IGNORE_WORDS_FOR_COLOR = config['parser']['color_ignore'].lower().split('\n')

    h.REF_LINK_MVIDEO = config['admitad']['ref_link_mvideo']
    h.REF_LINK_MTS = config['admitad']['ref_link_mts']
    h.REF_LINK_ELDORADO = config['admitad']['ref_link_eldorado']
    h.REF_LINK_CITILINK = config['admitad']['ref_link_citilink']

    BOT_TOKEN = config['bot-test']['token']
    BOT_CHAT_ID = int(config['bot-test']['chat_id'])


def load_data():
    """
    Чтение всей конфигурации проекта перед запуском runner.run
    """
    global COUNT_CRASH

    # Чтение словаря исключений названий моделей
    h.EXCEPT_MODEL_NAMES_DICT = FileWorker.dict_data.load(h.EXCEPT_MODEL_NAMES_PATH)

    # Чтение списка разрешенных названий моделей для добавления в БД
    h.ALLOWED_MODEL_NAMES_LIST_FOR_BASE = FileWorker.list_data.load(h.LIST_MODEL_NAMES_BASE_PATH)

    # Чтение значения кол-ва раз подряд, когда система падала
    COUNT_CRASH = FileWorker.list_data_int.load(h.CRASH_DATA_PATH)
    COUNT_CRASH = COUNT_CRASH[0] \
        if COUNT_CRASH and len(COUNT_CRASH) == 1 else 0

    # Чтение данных с config.ini
    read_config()


def create_lock_file():
    """
    Создать лок файл, запрещающий сервисному боту читать файл с исключениями
    """
    delete_lock_file()
    with open(h.UNDEFINED_MODEL_NAME_LIST_LOCK_PATH, 'w') as f:
        pass


def delete_lock_file():
    """
    Удалить лок-файл
    """
    if os.path.isfile(h.UNDEFINED_MODEL_NAME_LIST_LOCK_PATH):
        os.remove(h.UNDEFINED_MODEL_NAME_LIST_LOCK_PATH)


def send_alarm_in_telegram(msg):
    """
    Отправка сообщения в телеграм при переполнении счетчика COUNT_CRASH
    """
    method = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage'
    r = requests.post(method, data={
        'chat_id': BOT_CHAT_ID,
        'text': msg,
    })

    if r.status_code != 200:
        logger.error("НЕ МОГУ ОТПРАВИТЬ СООБЩЕНИЕ В ТЕЛЕГРАМ")


def inc_count_crash(shop_name):
    """
    Увеличение счетчика падений системы
    """
    global COUNT_CRASH

    logger.error("Упал {}, Count Crash = {}".format(shop_name, COUNT_CRASH))
    COUNT_CRASH += 1

    if COUNT_CRASH == MAX_COUNT_CRASH_FOR_ALARM:
        # send_alarm_in_telegram("Почини меня")
        print("!ПОЧИНИ МЕНЯ!")
        return

    FileWorker.list_data.save(h.CRASH_DATA_PATH, data=COUNT_CRASH)


def clear_count_crash():
    """
    Сброс счетчика падений системы
    """
    global COUNT_CRASH
    COUNT_CRASH = 0
    FileWorker.list_data.save(h.CRASH_DATA_PATH, data=COUNT_CRASH)

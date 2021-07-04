import time
import configparser

from pyrogram import Client
from pyrogram.types import InputMediaPhoto
import pyrogram.errors.exceptions as ex

import modules.common.helper as h

logger = h.logging.getLogger('TelegramSender')


class TelegramSender:
    """
    Базовая реализация Sender-а для Telegram
    """
    def __init__(self):
        self.app = None
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding="utf-8")
        self.chat_id = int(self.config['bot']['chat_id'])

    def __enter__(self):
        logger.info("Запуск бота")
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Остановка бота")
        self.stop()

    def start(self):
        """
        Запуск бота
        """
        self.app = Client(h.BOT_ACCOUNT_PATH)
        print(h.BOT_ACCOUNT_PATH)
        self.app.start()

    def stop(self):
        """
        Остановка бота
        """
        self.app.stop()
        self.app = None

    async def send_photo_message(self, img_path, caption, dis_notify):
        """
        Отправить сообщение с изображением
        :param img_path: полный путь к изображению на диске
        :param caption: описание к изображению (текст поста)
        :param dis_notify: (bool) выключить звук уведомлений
        """
        try:
            resp = await self.app.send_photo(self.chat_id, img_path, caption, 'html', disable_notification=dis_notify)
            logger.info("Создан новый пост, id={}".format(resp.message_id))
            return resp.message_id

        except ex.bad_request_400.MessageNotModified:
            logger.warning("Слишком много постов в телеграм, ожидаем 30 сек...")
            time.sleep(30)

        return None

    async def edit_photo_message(self, msg_id, img_path, caption):
        """
        Редактирование сообщения с изображением
        :param msg_id: id сообщения, которое необходимо отредактировать
        :param img_path: полный путь к изображению на диске
        :param caption: описание к изображению (текст поста)
        """
        try:
            await self.app.edit_message_media(self.chat_id, msg_id, InputMediaPhoto(img_path, caption, 'html'))
            logger.info("edit_message_media УСПЕШНО")
            return True

        except ex.bad_request_400.MessageNotModified as e:
            logger.error("Не удалось отредактировать пост - edit_message_media: {}".format(e))

    async def edit_photo_message_caption(self, msg_id, caption):
        """
        Изменить описание у поста с картинкой
        :param msg_id: id сообщения, которое необходимо отредактировать
        :param caption: описание к изображению (текст поста)
        """
        try:
            await self.app.edit_message_caption(self.chat_id, msg_id, caption, 'html')
            logger.info("edit_message_caption УСПЕШНО")
            time.sleep(1)
            return True

        except ex.bad_request_400.MessageNotModified as e:
            logger.error("Не удалось отредактировать пост - edit_message_caption: {}".format(e))
            return False

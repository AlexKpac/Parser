import requests
from PIL import Image
import modules.common.helper as h

logger = h.logging.getLogger('post_image')
STAMP_PATH = h.ROOT_PATH + 'data/img/stamp.png'
BLACKOUT_PATH = h.ROOT_PATH + 'data/img/blackout.png'
HIGHLIGHTING_PATH = h.ROOT_PATH + 'data/img/white.png'


class ImageCreator:
    """
    ВСПОМОГАТЕЛЬНЫЙ НЕОСНОВНОЙ КЛАСС (отсутствует в базовых модулях)
    Создает изображение из URL заданных размеров.

    :method open: Открыть изображение с диска
    :method __creation: Генерация картинки нужного размера из url
    :method check: Проверка наличия изображения
    :method get_img: Получить изображение
    :method save_as_png: Сохранение изображения на диск как png
    :method save_as_jpg: Сохранение изображения на диск как jpg
    """
    def __init__(self, url='', width=640, height=480):
        self.W = width
        self.H = height
        self.img = None

        if url:
            self.__creation(url)

    def open(self, path):
        """
        Открыть изображение с диска
        """
        self.img = Image.open(path).convert('RGBA')

    def __creation(self, url):
        """
        Генерация картинки нужного размера из url
        """
        # Проверка URL
        if not ("http" in url):
            logger.warning("Дефектный URL изображения: {}".format(url))
            return None

        # Загрузить изображение с url
        try:
            resp = requests.get(url, stream=True).raw
        except requests.exceptions.RequestException as e:
            logger.error("Can't get img from url, url={}\ne = {}".format(url, e))
            return None

        # Попытка открыть изображение средствами PIL
        try:
            raw_img = Image.open(resp)
        except IOError:
            logger.error("Unable to open image")
            return None

        # Если высота не соответствует H - изменение размера изображения с учетом пропорций
        if raw_img.height != self.H:
            width, height = raw_img.size
            new_width = int(self.H * width / height)
            raw_img = raw_img.resize((new_width, self.H), Image.LANCZOS)

        self.img = Image.new('RGBA', (self.W, self.H), color='#FFFFFF')
        self.img.paste(raw_img, (int((self.W - raw_img.width) / 2), 0), 0)

    def check(self):
        """
        Проверка наличия изображения
        """
        return bool(self.img)

    def get_img(self):
        """
        Получить изображение
        """
        return self.img

    def save_as_png(self, path, name):
        """
        Сохранение изображения на диск как png
        """
        # img_png = self.img.convert('RGBA')
        self.img.save("{}/{}.png".format(path, name), "png")

    def save_as_jpg(self, path, name):
        """
        Сохранение изображения на диск как jpg
        """
        if path and path[-1] in ['/', '\\']:
            path = path[:-1]

        if name and '.jpg' in name:
            name = name.replace('.jpg', '')

        img_jpg = self.img.convert('RGB')
        img_jpg.save("{}/{}.jpg".format(path, name), "jpeg")

    def draw_stamp(self):
        """
        Отрисовка штампа на изображении
        """
        if not self.img:
            logger.error('no img in draw_stamp')
            return self

        logger.info("draw stamp on image")
        stamp = Image.open(STAMP_PATH).convert("RGBA")
        self.img.paste(stamp, (int((self.W - stamp.width) / 2), int((self.H - stamp.height) / 2)), stamp)
        # self.img.paste(stamp, (int(self.W - stamp.width), 0), stamp)

        return self

    def darken(self):
        """
        Затемнение изображения
        """
        logger.info("darken image")

        blackout = Image.open(BLACKOUT_PATH).convert("RGBA")
        self.img.paste(blackout, (0, 0), blackout)

        return self

    def lighten(self):
        """
        Высветление изображения
        """
        logger.info("lighten image")

        white = Image.open(HIGHLIGHTING_PATH).convert("RGBA")
        self.img.paste(white, (0, 0), white)

        return self

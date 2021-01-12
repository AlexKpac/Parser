import requests
from PIL import Image
import header as h

logger = h.logging.getLogger('post_image')
STAMP_PATH = 'img/stamp.png'
BLACKOUT_PATH = 'img/blackout.png'
HIGHLIGHTING_PATH = 'img/white.png'


class PostImage:
    def __init__(self, url):
        self.W = 640
        self.H = 480
        self.img = None

        self.__creation(url)

    # Генерация картинки нужного размера из url
    def __creation(self, url):

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

    # Проверка картинки
    def check(self):
        return bool(self.img)

    # Получить картинку
    def get_img(self):
        return self.img

    # Отрисовка штампа на изображении
    def draw_stamp(self):
        logger.info("draw stamp on image")
        stamp = Image.open(STAMP_PATH).convert("RGBA")
        self.img.paste(stamp, (int((self.W - stamp.width) / 2), int((self.H - stamp.height) / 2)), stamp)

        return self.img

    # Затемнение изображения
    def darken(self):
        logger.info("darken image")

        blackout = Image.open(BLACKOUT_PATH).convert("RGBA")
        self.img.paste(blackout, (0, 0), blackout)

        return self.img

    # Высветление изображения
    def lighten(self):
        logger.info("lighten image")

        white = Image.open(HIGHLIGHTING_PATH).convert("RGBA")
        self.img.paste(white, (0, 0), white)

        return self.img

    # Сохранение изображения на диск
    def save(self, path, name):
        self.img.save("{}/{}.jpg".format(path, name), "jpeg")

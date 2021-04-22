import requests
from PIL import Image, ImageDraw
import common.general_helper as h

logger = h.logging.getLogger('post_image')
STAMP_PATH = '../data/img/stamp.png'
BLACKOUT_PATH = '../data/img/blackout.png'
HIGHLIGHTING_PATH = '../data/img/white.png'


class PostImage:
    def __init__(self, url=''):
        self.W = 640
        self.H = 480
        self.img = None

        if url:
            self.__creation(url)

    def open(self, path):
        self.img = Image.open(path).convert('RGBA')

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
        if not self.img:
            logger.error('no img in draw_stamp')
            return self

        logger.info("draw stamp on image")
        stamp = Image.open(STAMP_PATH).convert("RGBA")
        self.img.paste(stamp, (int((self.W - stamp.width) / 2), int((self.H - stamp.height) / 2)), stamp)
        # self.img.paste(stamp, (int(self.W - stamp.width), 0), stamp)

        return self

    # Затемнение изображения
    def darken(self):
        logger.info("darken image")

        blackout = Image.open(BLACKOUT_PATH).convert("RGBA")
        self.img.paste(blackout, (0, 0), blackout)

        return self

    # Высветление изображения
    def lighten(self):
        logger.info("lighten image")

        white = Image.open(HIGHLIGHTING_PATH).convert("RGBA")
        self.img.paste(white, (0, 0), white)

        return self

    # Зашифровать текст в картинку
    def steganography_encrypt(self, text):
        logger.info("steganography_encrypt")
        draw = ImageDraw.Draw(self.img)
        pix = self.img.load()

        indx = 0
        for elem in ([ord(elem) for elem in text]):
            for x in '{:08b}'.format(elem):
                r, g, b, a = pix[indx, 0]
                if not int(x):
                    draw.point((indx, 0), (r, g, (b & 254), a))
                else:
                    draw.point((indx, 0), (r, g, (b | 1), a))
                indx += 1

        return self

    # Изменить байты изображения для фильтра изображений телеграм
    def change_bytes_img(self):
        logger.info("change_bytes_img")
        draw = ImageDraw.Draw(self.img)
        pix = self.img.load()
        width, height = self.img.size

        for i in range(width):
            for j in range(height):
                cur_pix = pix[i, j]

                # if cur_pix[0] > 250 and cur_pix[1] > 250 and cur_pix[2] > 250:
                #     draw.point((i, j), (cur_pix[0] ^ 0x07, cur_pix[1] ^ 0x07, cur_pix[2] ^ 0x07))
                # else:
                #     draw.point((i, j), (cur_pix[0] ^ 0x03, cur_pix[1] ^ 0x01, cur_pix[2] ^ 0x07))

                # Менять только НЕ белые пиксели (белые для фона, там градиент)
                if cur_pix[0] < 250 or cur_pix[1] < 250 or cur_pix[2] < 250:
                    draw.point((i, j), (cur_pix[0] ^ 0x03, cur_pix[1] ^ 0x03, cur_pix[2] ^ 0x07))

        return self

    # Расшифровать стенографию, зашифрованную в каждой картинке
    def steganography_decrypt(self, len_text):
        logger.info("steganography_decrypt")
        pix = self.img.load()  # создаём объект изображения
        cipher_text = ""

        for i in range(len_text):
            one_char = 0
            print(pix[i, 0])
            for j in range(8):
                cur_bit = pix[(i * 8) + j, 0][2] & 1
                one_char += cur_bit << (7 - j)
            cipher_text += chr(one_char)

        return cipher_text

    # Сохранение изображения на диск
    def save_as_png(self, path, name):
        # img_png = self.img.convert('RGBA')
        self.img.save("{}/{}.png".format(path, name), "png")

    # Сохранение изображения на диск
    def save_as_jpg(self, path, name):
        img_jpg = self.img.convert('RGB')
        img_jpg.save("{}/{}.jpg".format(path, name), "jpeg")
import csv
from time import time

from dns_parse import DNSParse
from mvideo_parse import MVideoParse
from mts_parse import MTSParse
from checker import Checker
from bot import Bot
import header as h


# Сохранение всего результата в csv файл
def save_result_list(elements):
    with open(h.CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(h.HEADERS)
        for item in elements:
            writer.writerow(item)


# Загрузить данные с csv, чтобы не парсить сайт
def load_result_from_csv(name):
    pr_result_list = []
    with open(h.CSV_PATH_RAW + name, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pr_result_list.append(h.ParseResult(
                shop=row['Магазин'],
                category=row['Категория'],
                brand_name=row['Бренд'],
                model_name=row['Модель'],
                color=row['Цвет'],
                price=int(row['Цена']),
                ram=int(row['RAM']),
                rom=int(row['ROM']),
                img_url=row['Ссылка на изображение'],
                url=row['Ссылка'],
                rating=float(row['Рейтинг']),
                num_rating=int(row['Кол-во отзывов']),
                product_code=row['Код продукта'],
            ))

    return pr_result_list


if __name__ == '__main__':
    time_start = time()
    result_list = []

    parser = DNSParse()
    result = parser.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
    # result = load_result_from_csv("dns.csv")
    result_list.extend(result)

    parser = MVideoParse()
    result = parser.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
    # result = load_result_from_csv("mvideo.csv")
    result_list.extend(result)

    parser = MTSParse()
    result = parser.run_catalog("https://shop.mts.ru/catalog/smartfony/?id=62427_233815 ")
    # result = load_result_from_csv("mts.csv")
    result_list.extend(result)

    save_result_list(result_list)

    check = Checker(result_list)
    check.run()

    bot = Bot()
    bot.run()
    print(f"Время выполнения: {time() - time_start} сек")
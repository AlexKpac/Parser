import modules.common.helper as h

logger = h.logging.getLogger('DataValidator')


class DataValidator:
    """
    ОДИН ИЗ ОСНОВНЫХ МОДУЛЕЙ ПРОЕКТА - DataValidator
    Получает данные после DataReceiver и фильтрует их, после чего возвращает результат
    """

    def __init__(self, data_receiver_result_list):
        self.data_for_validation_list = data_receiver_result_list
        pass

    @staticmethod
    def validation_item(item):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Основа DataValidator - проверка одного элемента. Сделан статичным, чтобы можно было вызывать в других модулях,
        дабы не гонять один и тот же список (спарсенных данных, например) по несколько раз (по разу в каждом модуле).

        Вызывая этот метод, например, в DBInserter - можно не запускать DataValidator отдельно (через run), а значит
        экономим один полный проход по списку входных данных.
        Если этот список состоит из тысячи элементов - экономия оказывается ощутимой.
        """
        if item.category and item.shop and item.brand_name and item.model_name and \
                item.color and item.img_url and item.product_code and item.rom and item.price:
            return True

        return False

    def __validation_list(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Валидация списка данных - проверка на пустые ключевые поля
        """
        result = []
        for item in self.data_for_validation_list:
            if DataValidator.validation_item(item):
                result.append(item)

        return result

    def run(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД
        Запуск DataValidator
        """
        return self.__validation_list()

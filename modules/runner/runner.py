from time import time

import modules.runner.runner_helper as rh
import modules.common.helper as h
from modules.common.file_worker import FileWorker
from modules.data_receiver.parsers.dns_parse import DNSParse
from modules.data_receiver.parsers.mvideo_parse import MVideoParse
from modules.data_receiver.parsers.mts_parse import MTSParse
from modules.data_receiver.parsers.eldorado_parse import EldoradoParse
from modules.data_receiver.parsers.citilink_parse import CitilinkParse
from modules.data_validator.data_validator import DataValidator
from modules.data_checker.data_checker import DataChecker
from modules.db_inserter.db_inserter import DbInserter
from modules.data_sender.telegram.bot import Bot as DataSender

logger = h.logging.getLogger('Runner')


class Runner:
    def __init__(self):
        self.data_receiver_result_list = []
        self.data_validator_result_list = []
        self.db_inserter_result_list = []
        self.data_checker_result_list = []

        self.setup()

    @staticmethod
    def setup():
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Конфигурация проекта
        """
        h.del_old_logs()
        rh.load_data()

    def __run_one_parser(self, parser_class, url, name=""):
        """
        Запустить один парсер
        """
        parser = parser_class()
        result = parser.run_catalog(url=url)
        # result = rh.load_result_from_csv("mts.csv")
        if not result:
            rh.inc_count_crash(name)
            return

        self.data_receiver_result_list.extend(result)

    def receiver_stage(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Этап 1: Получение сырых данных
        """
        rh.create_lock_file()

        self.__run_one_parser(MVideoParse, name="Мвидео",
                              url="https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")

        # self.__run_one_parser(MTSParse, name="МТС",
        #                       url="https://shop.mts.ru/catalog/smartfony/")
        #
        # self.__run_one_parser(DNSParse, name="ДНС",
        #                       url="https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
        #
        # self.__run_one_parser(CitilinkParse, name="Ситилинк",
        #                       url="https://www.citilink.ru/catalog/mobile/smartfony/")
        #
        # self.__run_one_parser(EldoradoParse, name="Эльдорадо",
        #                       url="https://www.eldorado.ru/c/smartfony/")

        rh.delete_lock_file()
        rh.clear_count_crash()
        FileWorker.csv_data.save(h.CSV_PATH, data=self.data_receiver_result_list, namedtuple_type=h.ParseResult)

    def validator_stage(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Этап 2: Валидация сырых данных
        """
        validator = DataValidator(self.data_receiver_result_list)
        self.data_validator_result_list = validator.run()

    def inserter_stage(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Этап 3: Добавление валидных данных в БД и выборка по определенным критериям
        """
        inserter = DbInserter(self.data_validator_result_list)
        self.db_inserter_result_list = inserter.run()

    def checker_stage(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Этап 4: Выборка данных для отправки после выборки с БД
        """
        checker = DataChecker(self.db_inserter_result_list, self.data_validator_result_list)
        self.data_checker_result_list = checker.run()

    def sender_stage(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Этап 5: Отправка данных
        """
        with DataSender() as bot:
            bot.checking_irrelevant_posts(self.data_validator_result_list)
            bot.send_posts(self.data_checker_result_list)

    def run(self):
        """
        ОБЯЗАТЕЛЬНЫЙ МЕТОД.
        Запуск всего проекта
        """
        # result_list = load_result_from_csv("goods2.csv")
        time_start = time()

        # Этап 1: Получение сырых данных
        self.receiver_stage()

        # Этап 2: Валидация сырых данных
        self.validator_stage()

        # Этап 3: Добавление валидных данных в БД и выборка по определенным критериям
        self.inserter_stage()

        # Этап 4: Выборка данных для отправки после выборки с БД
        self.checker_stage()

        # Этап 5: Отправка данных
        self.sender_stage()

        logger.info(f"Время выполнения: {time() - time_start} сек")

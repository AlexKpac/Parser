import modules.common.helper as h
from modules.runner.runner import Runner


logger = h.logging.getLogger('Main')

# def worker1():
#     parser1 = MVideoParse()
#     parser1.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
#
#
# def worker2():
#     parser2 = DNSParse()
#     parser2.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
#
#
# def worker3():
#     parser3 = MTSParse()
#     parser3.run_catalog("https://shop.mts.ru/catalog/smartfony/")
#
#
# def worker4():
#     parser4 = EldoradoParse()
#     parser4.run_catalog("https://www.eldorado.ru/c/smartfony/")

if __name__ == '__main__':
    # import multiprocessing
    #
    # time_start = time()
    # load_allowed_model_names_list_for_base()
    # load_exceptions_model_names()
    # read_config()
    #
    # for item in h.ALLOWED_MODEL_NAMES_LIST_FOR_BASE:
    #     print(item)
    #
    # time_start = time()
    # p1 = multiprocessing.Process(target=worker1)
    # p2 = multiprocessing.Process(target=worker2)
    # p3 = multiprocessing.Process(target=worker3)
    # p4 = multiprocessing.Process(target=worker4)
    # p1.start()
    # p2.start()
    # p3.start()
    # p4.start()
    # print("КОНЕЦ СТАРТОВ")
    # p1.join()
    # p2.join()
    # p3.join()
    # p4.join()
    # print("КОНЕЦ ДЖОИНОВ")
    # logger.info(f"Время выполнения: {time() - time_start} сек")
    # https://docs-python.ru/standart-library/paket-multiprocessing-python/
    #
    #
    #################################################
    # time_start = time()
    # h.del_old_logs()
    # load_data()
    #
    # # Этап 1: Получение сырых данных
    # create_lock_file()
    # data_receiver_result_list = []
    #
    # parser = MVideoParse()
    # result = parser.run_catalog("https://www.mvideo.ru/smartfony-i-svyaz-10/smartfony-205?sort=price_asc")
    # # result = load_result_from_csv("mvideo.csv")
    # if not result:
    #     inc_count_crash("Мвидео")
    # data_receiver_result_list.extend(result)
    #
    # parser = MTSParse()
    # result = parser.run_catalog("https://shop.mts.ru/catalog/smartfony/")
    # # result = load_result_from_csv("mts.csv")
    # if not result:
    #     inc_count_crash("МТС")
    # data_receiver_result_list.extend(result)
    #
    # parser = DNSParse()
    # result = parser.run_catalog("https://www.dns-shop.ru/catalog/17a8a01d16404e77/smartfony/")
    # # result = load_result_from_csv("dns.csv")
    # if not result:
    #     inc_count_crash("ДНС")
    # data_receiver_result_list.extend(result)
    #
    # parser = CitilinkParse()
    # result = parser.run_catalog("https://www.citilink.ru/catalog/mobile/smartfony/")
    # # result = load_result_from_csv("citilink.csv")
    # if not result:
    #     inc_count_crash("Ситилинк")
    # data_receiver_result_list.extend(result)
    #
    # parser = EldoradoParse()
    # result = parser.run_catalog("https://www.eldorado.ru/c/smartfony/")
    # # result = load_result_from_csv("eldorado.csv")
    # if not result:
    #     inc_count_crash("Эльдорадо")
    # data_receiver_result_list.extend(result)
    #
    # delete_lock_file()
    # clear_count_crash()
    # save_result_list(data_receiver_result_list)
    #
    # # Этап 2: Валидация сырых данных
    # # result_list = load_result_from_csv("goods2.csv")
    # validator = DataValidator(data_receiver_result_list)
    # data_validator_result_list = validator.run()
    #
    # # Этап 3: Добавление валидных данных в БД и выборка по определенным критериям
    # inserter = DbInserter(data_validator_result_list)
    # db_inserter_result_list = inserter.run()
    #
    # # Этап 4: Выборка данных для отправки после выборки с БД
    # checker = DataChecker(db_inserter_result_list, data_validator_result_list)
    # data_checker_result_list = checker.run()
    #
    # # Этап 5: Отправка данных
    # with DataSender() as bot:
    #     bot.checking_irrelevant_posts(data_validator_result_list)
    #     bot.send_posts(data_checker_result_list)
    #
    # logger.info(f"Время выполнения: {time() - time_start} сек")
    #############################################
    runner = Runner()
    runner.run()


"""
Консервация проекта 10.05.21
Весь код проекта полностью отредактирован - полный рефакторинк и изменение структуры. Ничего не протестировано.
Доделки:
 - Все парсеры кроме МВидео вышли из строя. 
 - Есть вопросы к модулю добавления данных в БД. 
 - Также перепроверить код telegram_sender.py на функции async, сравнить со старыми версиями. Много варнингов в консоли. 
 - Проверить чтение словарей существующих моделей, ощущение, будто бы половину не видит.
 - Путь ROOT_PATH задан вручную для отладки.
"""
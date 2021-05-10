import re
import csv
from enum import Enum, auto
from typing import Union
from collections import namedtuple
import modules.common.helper as h

logger = h.logging.getLogger('FileWorker')


def convert_column_name(name):
    """
    Конвертирование название заголовка в csv в формат поля namedtuple.
    Разрешается в заголовке использовать:
        - сколько угодно пробелов до и после названия столбца
        - разделять слова пробелами
        - использовать любой регистр
    """
    return name.strip().replace('  ', '_').replace(' ', '_').lower()


def convert_namedtuple_fields_name(name):
    """
    Конвертирование названия поля у namedtuple в название столбца.
    Разрешается в заголовке использовать:
        - сколько угодно пробелов до и после названия столбца
        - разделять слова пробелами
        - использовать любой регистр
    """
    return name.replace('_', ' ').title()


class FileWorker(Enum):
    """
    Класс, работающий с данными, которые впоследствии сохраняются в файлы. Имеет разные типы и, соответственно, разные
    методы для сохранения и загрузки данных с файлов.

    @list_data: обычный строковый список, никаких спецсимволов, элементы разделены \n
    @csv_data: namedtuple, который сохраняется в csv файл. Исключение: в save() и load() появляется доп. параметр
    @dict_data: словарь вида [key]->[value] (в файле). Может быть нескольких видов, перечисленных ниже или можно
        использовать эту краткую форму (по-умолчанию str_str).
    @dict_data_int_int: надстройка над @dict_data, key:int, value:int
    @dict_data_str_str: надстройка над @dict_data, key:str, value:str (можно исп. краткую форму dict_data)
    @dict_data_str_int: надстройка над @dict_data, key:str, value:int
    @dict_data_int_str: надстройка над @dict_data, key:int, value:str
    """

    list_data = auto()
    list_data_int = auto()
    list_data_str = auto()
    csv_data = auto()
    dict_data = auto()
    dict_data_int_int = auto()
    dict_data_str_str = auto()
    dict_data_str_int = auto()
    dict_data_int_str = auto()

    def save(self, path, data, overwrite=True, namedtuple_type=None):
        """
        Сохранение файла на диск. В зависимости от типа файла выбирается определенный метод сохранения и
        подбираются определенные параметры.

        :param path: (str) полный путь к файлу, включая имя и расширение
        :param data: (any) данные, которые необходимо сохранить
        :param overwrite: (bool) флаг полной перезаписи файла, при False - дозаписывается в конец
        :param namedtuple_type: (type namedtuple) только для csv - тип namedtuple
        """

        if not data:
            logger.error("Не могу сохранить данные, т.к. данных нет. Path = {}".format(path))
            return

        if self is FileWorker.dict_data:
            if namedtuple_type is not None:
                raise AttributeError("Param 'namedtuple_type' is not used for type @dict_data")
            self.__save_dict(data, path, overwrite)

        elif self is FileWorker.list_data:
            if namedtuple_type is not None:
                raise AttributeError("Param 'namedtuple_type' is not used for type @list_data")
            self.__save_list(data, path, overwrite)

        elif self is FileWorker.csv_data:
            if namedtuple_type is None:
                raise AttributeError("For type @csv_data, param 'namedtuple_type' is required")
            self.__save_csv(data, path, overwrite, namedtuple_type)

    def load(self, path, namedtuple_type=None):
        """
        Чтение данных с файла. В зависимости от типа файла выбирается определенный метод чтения и
        подбираются определенные параметры.

        :param path: (str) полный путь к файлу, включая имя и расширение
        :param namedtuple_type: (type namedtuple) только для csv - тип namedtuple
        :return: данные, прочитанные с файла
        """

        if self in [FileWorker.dict_data, FileWorker.dict_data_str_str, FileWorker.dict_data_str_int,
                    FileWorker.dict_data_int_str, FileWorker.dict_data_int_int]:
            if namedtuple_type is not None:
                raise AttributeError("Param 'namedtuple_type' is not used for type @dict_data")
            return self.__load_dict(path, self)

        elif self in [FileWorker.list_data, FileWorker.list_data_int, FileWorker.list_data_str]:
            if namedtuple_type is not None:
                raise AttributeError("Param 'namedtuple_type' is not used for type @list_data")
            return self.__load_list(path, self)

        elif self is FileWorker.csv_data:
            if namedtuple_type is None:
                raise AttributeError("For type @csv_data, param 'namedtuple_type' is required")
            return self.__load_csv(path, namedtuple_type)

    @staticmethod
    def __save_dict(data: dict, path, overwrite):
        """ Сохраняет словарь @data в файл @path.

        :param data (dict): данные, которые сохраняем в файл
        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :param overwrite (bool): флаг, выбирающий режим записи - перезапись или дозаписать в конец файла """

        mode = 'w' if overwrite else 'a'
        with open(path, mode, encoding='UTF-8') as f:
            for key, val in data.items():
                f.write('[{}] -> [{}]\n'.format(key, val))

    @staticmethod
    def __load_dict(path, type_dict):
        """
        Прочитать словарь @data из файла @path

        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :return (dict): словарь, распарсенный из файла
        """

        data = dict()
        try:
            with open(path, 'r', encoding='UTF-8') as f:
                for line in f:
                    res = re.findall(r"\[.+?]", line)
                    # Отсечь кривые записи
                    if len(res) != 2:
                        continue

                    key = res[0].replace('[', '').replace(']', '')
                    value = res[1].replace('[', '').replace(']', '')

                    # В зависимости от типа словаря конвертировать значения
                    if type_dict is FileWorker.dict_data_int_int:
                        if not key.isdigit() or not value.isdigit():
                            continue
                        key = int(key)
                        value = int(value)

                    if type_dict is FileWorker.dict_data_str_int:
                        if not value.isdigit():
                            continue
                        value = int(value)

                    if type_dict is FileWorker.dict_data_int_str:
                        if not key.isdigit():
                            continue
                        key = int(key)

                    data[key] = value

        except Exception as e:
            logger.error("Произошла ошибка при попытке открыть файл в __load_dict, path = {}, e = {}".format(path, e))

        return data

    @staticmethod
    def __save_list(data: Union[list, str, int], path, overwrite):
        """ Сохраняет список или строку @data в файл @path.

        :param data (list|str): данные, которые сохраняем в файл
        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :param overwrite (bool): флаг, выбирающий режим записи - перезапись или дозаписать в конец файла """

        if not data or not path:
            return

        mode = 'w' if overwrite else 'a'
        with open(path, mode, encoding='UTF-8') as f:
            if isinstance(data, str) or isinstance(data, int):
                f.write(str(data) + '\n')

            if isinstance(data, list):
                for item in data:
                    f.write(str(item) + '\n')

    @staticmethod
    def __load_list(path, type_list):
        """
        Чтение списка @data из файла @path

        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :return (list): список данных, распарсенный из файла
        """
        data = list()

        try:
            with open(path, 'r', encoding='UTF-8') as f:
                for line in f:
                    line = line.replace('\n', '').replace('\r', '')
                    if not line:
                        continue

                    if type_list is FileWorker.list_data_int:
                        res = re.findall(r"\d+", line)
                        if res:
                            res = ''.join(res)
                            line = int(res)
                        else:
                            continue

                    if type_list in [FileWorker.list_data, FileWorker.list_data_str]:
                        pass

                    data.append(line)

        except Exception as e:
            logger.error("Произошла ошибка при попытке открыть файл в __load_list, path = {}, e = {}".format(path, e))

        return data

    @staticmethod
    def __save_csv(data, path, overwrite, namedtuple_type):
        """
        Сохраняет @data (список namedtuple или одиночный namedtuple) типа @namedtuple_type в файл @path.

        :param data (list|namedtuple_type): данные, которые сохраняем в файл
        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :param overwrite (bool): флаг, выбирающий режим записи - перезапись или дозаписать в конец файла
        :param namedtuple_type (type): тип namedtuple
        """

        # Проверка корректности типов данных
        if isinstance(data, list):
            if not isinstance(data[0], namedtuple_type):
                return
        elif not isinstance(data, namedtuple_type):
            return

        mode = 'w' if overwrite else 'a'
        with open(path, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            if overwrite:
                columns_name = [convert_namedtuple_fields_name(column) for column in namedtuple_type._fields]
                writer.writerow(columns_name)

            if isinstance(data, namedtuple_type):
                try:
                    writer.writerow(data)
                except Exception as e:
                    logger.error("Ошибка при попытке сохранения csv!\nitem={}\nerror={}\n".format(data, e))

            if isinstance(data, list):
                for item in data:
                    try:
                        writer.writerow(item)
                    except Exception as e:
                        logger.error("Ошибка при попытке сохранения csv!\nitem={}\nerror={}\n".format(item, e))

    @staticmethod
    def __load_csv(path, namedtuple_type):
        """
        Чтение csv в список @result именнованных кортежей @namedtuple_type из файла @path

        :param namedtuple_type (type namedtuple): тип данных namedtuple, не объект
        :param path (str): полный путь файла для сохранения, включая имя и расширение
        :return (list): список данных, распарсенный из файла
        """

        result = []

        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                # Проверка совместимости namedtuple и csv
                columns_in_csv = [convert_column_name(column) for column in reader.fieldnames]
                for field in namedtuple_type._fields:
                    if field not in columns_in_csv:
                        print("Несоответствие поля {}, словари не совместимы".format(field))
                        return None

                # Заполнение списка данными из файла
                for row in reader:
                    value_list = []
                    for itt in namedtuple_type._fields:
                        # Поиск названия столбца, который равен названию полю namedtuple (без учета пробелов и регистра)
                        need_column_name = [column for column in reader.fieldnames
                                            if convert_column_name(column) == itt][0]
                        value_list.append(row[need_column_name])

                    result.append(namedtuple_type._make(value_list))

        except Exception as e:
            logger.error("Произошла ошибка при попытке открыть файл в __load_csv, path = {}, e = {}".format(path, e))

        return result

"""
Использование FileDataType

1. res = FileDataType.csv_data.load("data/cache/s1.csv", namedtuple_type=ParseResult)

2. var = FileDataType.csv_data
   res = var.load("data/cache/s1.csv", namedtuple_type=ParseResult)
"""


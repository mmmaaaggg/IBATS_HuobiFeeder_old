# -*- coding: utf-8 -*-
"""
Created on 2017/6/9
@author: MG
"""
import logging
from logging.handlers import RotatingFileHandler


class ConfigBase:
    # 配置环境变量
    DATETIME_FORMAT_STR = '%Y-%m-%d %H:%M:%S'
    DATE_FORMAT_STR = '%Y-%m-%d'
    TIME_FORMAT_STR = '%H:%M:%S'
    DATE_FORMAT_STR_CTP = '%Y%m%d'
    TIME_FORMAT_STR_CTP = '%H%M%S'
    # api configuration
    EXCHANGE_ACCESS_KEY = ""
    EXCHANGE_SECRET_KEY = ""

    # mysql db info
    DB_SCHEMA_MD = 'bc_md'
    DB_URL_DIC = {
        DB_SCHEMA_MD: 'mysqldb://mg:****@10.0.3.66/' + DB_SCHEMA_MD
    }

    # redis info
    REDIS_INFO_DIC = {'REDIS_HOST': '192.168.239.131',
                      'REDIS_PORT': '6379',
                      }

    # evn configuration
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(filename)s.%(funcName)s:%(lineno)d|%(message)s'

    def __init__(self):
        """
        初始化一些基本配置信息
        """
        # 设置rest调用日志输出级别
        logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)
        logging.getLogger('md_min1_bc').setLevel(logging.INFO)
        logging.getLogger('md_min1_tick_bc').setLevel(logging.INFO)


class ConfigTest(ConfigBase):
    EXCHANGE_ACCESS_KEY = 'aaa1d1b8-acfed9be-56679582-3ff79'
    EXCHANGE_SECRET_KEY = 'b6d59b43-3013d530-89874d7e-c0bf4'

    # DB_URL_DIC = {
    #     ConfigBase.DB_SCHEMA_MD: 'mysql://mg:****@10.0.3.66/bc_md'
    # }


# 测试配置（测试行情库）
Config = ConfigTest()
# 生产配置
# Config = ConfigProduct()

# 设定默认日志格式
logging.basicConfig(level=logging.DEBUG, format=Config.LOG_FORMAT)
# logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)
# logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)


# 配置文件日至
handler = RotatingFileHandler('log.log', maxBytes=10 * 1024 * 1024, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter(Config.LOG_FORMAT)
handler.setFormatter(formatter)
logging.getLogger('').addHandler(handler)


if __name__ == "__main__":
    pass

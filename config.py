# -*- coding: utf-8 -*-
"""
Created on 2017/6/9
@author: MG
"""
import logging
from logging.handlers import RotatingFileHandler


class ConfigBase:

    # 交易所名称
    MARKET_NAME = 'huobi'

    # api configuration
    EXCHANGE_ACCESS_KEY = ""
    EXCHANGE_SECRET_KEY = ""

    # mysql db info
    ENABLE_DB_HANDLER = True
    DB_SCHEMA_MD = 'bc_md'
    DB_URL_DIC = {
        DB_SCHEMA_MD: 'mysql://mg:****@localhost/' + DB_SCHEMA_MD
    }

    # redis info
    ENABLE_REDIS_HANDLER = True
    REDIS_INFO_DIC = {'REDIS_HOST': 'localhost',
                      'REDIS_PORT': '6379',
                      }

    # evn configuration
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(filename)s.%(funcName)s:%(lineno)d|%(message)s'

    def __init__(self):
        """
        初始化一些基本配置信息
        """
        pass


class ConfigTest(ConfigBase):
    EXCHANGE_ACCESS_KEY = '***'
    EXCHANGE_SECRET_KEY = '***'

    DB_URL_DIC = {
        ConfigBase.DB_SCHEMA_MD: 'mysql://mg:***@10.0.3.66/' + ConfigBase.DB_SCHEMA_MD
    }


# 测试配置（测试行情库）
Config = ConfigTest()
# 生产配置
# Config = ConfigProduct()

# 设定默认日志格式
logging.basicConfig(level=logging.DEBUG, format=Config.LOG_FORMAT)
# 设置rest调用日志输出级别
# logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger('DBHandler->md_min1_tick_bc').setLevel(logging.INFO)
logging.getLogger('DBHandler->md_min1_bc').setLevel(logging.INFO)
logging.getLogger('DBHandler->md_min60_bc').setLevel(logging.INFO)
logging.getLogger('DBHandler->md_daily_bc').setLevel(logging.INFO)
logging.getLogger('MDFeeder').setLevel(logging.INFO)
# logging.getLogger('md_min1_bc').setLevel(logging.INFO)
# logging.getLogger('md_min1_tick_bc').setLevel(logging.INFO)

# 配置文件日至
# handler = RotatingFileHandler('log.log', maxBytes=10 * 1024 * 1024, backupCount=5)
# handler.setLevel(logging.INFO)
# formatter = logging.Formatter(Config.LOG_FORMAT)
# handler.setFormatter(formatter)
# logging.getLogger('').addHandler(handler)


if __name__ == "__main__":
    pass

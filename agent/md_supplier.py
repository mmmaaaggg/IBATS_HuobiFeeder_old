#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/12 20:52
@File    : md_supplier.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
import logging
from huobitrade.service import HBWebsocket, HBRestAPI
from huobitrade import setKey
from config import Config
from backend import engine_md
from utils.db_utils import with_db_session
from backend.orm import SymbolPair
import time
from threading import Thread
from backend.orm import MDTick, MDMin1
from backend.handler import DBHandler, PublishHandler
logger = logging.getLogger()
# 设置秘钥
setKey(Config.EXCHANGE_ACCESS_KEY, Config.EXCHANGE_SECRET_KEY)


class MDSupplier(Thread):
    """接受订阅数据想redis发送数据"""

    def __init__(self):
        super().__init__(name='huobi websocket', daemon=True)
        self.hb = HBWebsocket()
        self.api = HBRestAPI()
        self.init_symbols = False

    def init(self):

        if self.init_symbols:
            # 获取有效的交易对信息保存（更新）数据库
            ret = self.api.get_symbols()
            key_mapping = {
                'base-currency': 'base_currency',
                'quote-currency': 'quote_currency',
                'price-precision': 'price_precision',
                'amount-precision': 'amount_precision',
                'symbol-partition': 'symbol_partition',
            }
            # 获取支持的交易对
            data_dic_list = []
            for d in ret['data']:
                d['market'] = 'huobi'
                data_dic_list.append({key_mapping.setdefault(k, k): v for k, v in d.items()})

            with with_db_session(engine_md) as session:
                session.execute(SymbolPair.__table__.insert(on_duplicate_key_update=True), data_dic_list)

            available_pairs = [d['base_currency']+d['quote_currency']
                               for d in data_dic_list if d['symbol_partition'] == 'main']

            # 通过 on_open 方式进行订阅总是无法成功
            for pair in available_pairs:
                self.hb.sub_dict[pair] = {'id': '', 'topic': f'market.{pair}.kline.1min'}
        else:
            self.hb.sub_dict['ethbtc'] = {'id': '', 'topic': 'market.ethbtc.kline.1min'}
            self.hb.sub_dict['ethusdt'] = {'id': '', 'topic': 'market.ethusdt.kline.1min'}

        # handler = SimpleHandler('simple handler')
        handler = DBHandler(db_model=MDTick)
        self.hb.register_handler(handler)
        time.sleep(1)
        handler = DBHandler(db_model=MDMin1)
        self.hb.register_handler(handler)
        handler = PublishHandler(market=Config.MARKET_NAME)
        self.hb.register_handler(handler)
        logger.info("api.get_timestamp %s", self.api.get_timestamp())

    def run(self):
        self.hb.run()
        logger.info('启动')
        while True:
            time.sleep(1)

    def fill_history(self):
        """
        根据数据库中的支持 symbol 补充历史数据
        :return:
        """
        with with_db_session(engine_md) as session:
            sql_str = """"""
            session.execute()


def start_supplier() -> MDSupplier:
    supplier = MDSupplier()
    supplier.init()
    supplier.start()
    return supplier

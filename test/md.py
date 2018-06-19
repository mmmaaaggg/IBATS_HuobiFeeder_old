#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/12 15:01
@File    : md.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
import logging
from huobitrade.service import HBWebsocket, HBRestAPI
from huobitrade.handler import baseHandler
from huobitrade import setKey
from config import Config
from backend import engine_md
from utils.db_utils import with_db_session
from backend.orm import SymbolPair
import time
logger = logging.getLogger()
setKey(Config.EXCHANGE_ACCESS_KEY, Config.EXCHANGE_SECRET_KEY)


class SimpleHandler(baseHandler):
    def handle(self, msg):
        logger.debug(msg)


hb = HBWebsocket()
hb.sub_dict['ethbtc'] = {'id': '', 'topic': 'market.ethbtc.kline.1min'}
handler = SimpleHandler('simple handler')
hb.register_handler(handler)
hb.run()

time.sleep(3)  # run之后连接需要一丢丢时间，sleep一下再订阅
# hb.sub_kline('ethbtc', '1min')

# @hb.register_handle_func('market.ethbtc.kline.1min')
# def handle(msg):
#     print('handle:', msg)

# api = HBRestAPI()
# print(api.get_timestamp())
#
# # 获取有效的交易对信息保存（更新）数据库
# ret = api.get_symbols()
# key_mapping = {
#     'base-currency': 'base_currency',
#     'quote-currency': 'quote_currency',
#     'price-precision': 'price_precision',
#     'amount-precision': 'amount_precision',
#     'symbol-partition': 'symbol_partition',
# }
# data_dic_list = []
# for d in ret['data']:
#     d['market'] = 'huobi'
#     data_dic_list.append({key_mapping.setdefault(k, k): v for k, v in d.items()})
#
# with with_db_session(engine_md) as session:
#     session.execute(SymbolPair.__table__.insert(on_duplicate_key_update=True), data_dic_list)

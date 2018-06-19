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
from huobitrade.handler import baseHandler
from huobitrade import setKey
from prodconpattern import ProducerConsumer
from config import Config
from backend import engine_md
from utils.db_utils import with_db_session
from utils.fh_utils import datetime_2_str, STR_FORMAT_DATETIME2
from backend.orm import SymbolPair
import time
from datetime import datetime
from threading import Thread
from sqlalchemy import Table, MetaData
from sqlalchemy.orm import sessionmaker
from backend.orm import MDTick, MDMin1
from backend.redis import get_redis
import json
logger = logging.getLogger()
# 设置秘钥
setKey(Config.EXCHANGE_ACCESS_KEY, Config.EXCHANGE_SECRET_KEY)


class SimpleHandler(baseHandler):

    def handle(self, msg):
        if 'ch' in msg:
            # logging.info("msg:%s", msg)
            topic = msg.get('ch')
            _, pair, _, period = topic.split('.')
            if period == '1min':
                data = msg.get('tick')
                # 调整相关属性
                data['ts_start'] = datetime.fromtimestamp(data.pop('id'))
                data['market'] = 'huobi'
                data['ts_curr'] = datetime.fromtimestamp(msg['ts']/1000)
                logging.info("data:%s", data)
            else:
                logger.info(msg)

        elif 'rep' in msg:
            topic = msg.get('rep')
            data = msg.get('data')
            logger.info(msg)
        else:
            logger.warning(msg)


class DBHandler(baseHandler):

    def __init__(self, db_model=None, table_name=None):
        if db_model is not None:
            self.table_name = db_model.__tablename__
            self.md_orm_table = db_model.__table__
        elif table_name is not None:
            self.table_name = table_name
            self.md_orm_table = Table(table_name, MetaData(engine_md), autoload=True)
        baseHandler.__init__(self, 'DB[%s]' % self.table_name)
        self.session_maker = sessionmaker(bind=engine_md)
        self.session = None

        self.logger = logging.getLogger(self.table_name)
        self.md_orm_table_insert = self.md_orm_table.insert(on_duplicate_key_update=True)

    def handle(self, msg):
        if 'ch' in msg:
            topic = msg.get('ch')
            _, pair, _, period = topic.split('.')
            if period == '1min':
                data = msg.get('tick')
                # 调整相关属性
                data['ts_start'] = datetime.fromtimestamp(data.pop('id'))
                data['market'] = 'huobi'
                data['ts_curr'] = datetime.fromtimestamp(msg['ts'] / 1000)
                data['pair'] = pair
                self.save_md(data)
                self.logger.debug('invoke save_md %s', data)
            else:
                self.logger.info(msg)

        elif 'rep' in msg:
            topic = msg.get('rep')
            data = msg.get('data')
            self.logger.info(msg)
        else:
            self.logger.warning(msg)

    @ProducerConsumer(threshold=1000, interval=20, pass_arg_list=True, is_class_method=True)
    def save_md(self, data_dic_list):
        """
        保存md数据到数据库及文件
        :param data_dic_list:
        :param session:
        :return:
        """

        if data_dic_list is None or len(data_dic_list) == 0:
            self.logger.warning("data_dic_list 为空")
            return

        md_count = len(data_dic_list)
        # 保存到数据库
        if self.session is None:
            self.session = self.session_maker()
        try:
            self.session.execute(self.md_orm_table_insert, data_dic_list)
            self.logger.info('%d 条数据保存到 %s 完成', md_count, self.table_name)
        except:
            self.logger.exception('%d 条数据保存到 %s 失败', md_count, self.table_name)


class PublishHandler(baseHandler):

    def __init__(self, market='huobi'):
        baseHandler.__init__(self, name=self.__class__.__name__)
        self.market = market
        self.logger = logging.getLogger(self.__class__.__name__)
        self.r = get_redis()
        # 记录上一个tick的 st_start 用于判断是否开始分钟切换
        self.last_ts_start_pair_tick = {}
        self.last_tick_pair_tick = {}

    def handle(self, msg):
        """
        收到数据后，tick数据直接发送，
        channel：md.market.tick.pair
        channel：md.market.min1.pair 每个分钟时点切换时，发送一次分钟线数据
        例如：
        md.huobi.tick.ethusdt
        md.huobi.1min.ethusdt
        通过 redis-cli 可以 PUBSUB CHANNELS 查阅活跃的频道
        PSUBSCRIBE pattern [pattern ...]  查看频道内容
        SUBSCRIBE channel [channel ...]  查看频道内容
        :param msg:
        :return:
        """
        if 'ch' in msg:
            topic = msg.get('ch')
            _, pair, _, period = topic.split('.')
            if period == '1min':
                data = msg.get('tick')
                # 调整相关属性
                ts_start = datetime.fromtimestamp(data.pop('id'))
                # TODO: 需要转换一下 ts 到 str
                data['ts_start'] = datetime_2_str(ts_start, format=STR_FORMAT_DATETIME2)
                data['market'] = 'huobi'
                data['ts_curr'] = datetime_2_str(datetime.fromtimestamp(msg['ts'] / 1000), format=STR_FORMAT_DATETIME2)
                data['pair'] = pair
                # Json
                md_str = json.dumps(data)
                # 先发送Tick数据
                channel = f'md.{self.market}.tick.{pair}'
                self.r.publish(channel, md_str)
                # 分钟线切换时发送分钟线数据
                ts_start_last = self.last_ts_start_pair_tick.setdefault(pair, None)
                if ts_start_last is not None and ts_start_last != ts_start:
                    md_str_last = self.last_tick_pair_tick
                    channel_min1 = f'md.{self.market}.1min.{pair}'
                    self.r.publish(channel_min1, md_str_last)

                self.last_ts_start_pair_tick[pair] = ts_start
                self.last_tick_pair_tick = md_str
            else:
                self.logger.info(msg)

        elif 'rep' in msg:
            # topic = msg.get('rep')
            # data = msg.get('data')
            self.logger.info(msg)
        else:
            self.logger.warning(msg)


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
        handler = PublishHandler(market='huobi')
        self.hb.register_handler(handler)
        logger.info("api.get_timestamp %s", self.api.get_timestamp())

    def run(self):
        self.hb.run()
        logger.info('启动')
        while True:
            time.sleep(1)


def start_supplier() -> MDSupplier:
    supplier = MDSupplier()
    supplier.init()
    supplier.start()
    return supplier

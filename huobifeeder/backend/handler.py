#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/19 10:47
@File    : handler.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
import logging
from abat.common import PeriodType
from huobitrade.handler import baseHandler
from prodconpattern import ProducerConsumer
from huobifeeder.utils.fh_utils import datetime_2_str, STR_FORMAT_DATETIME2
from datetime import datetime
from sqlalchemy import Table, MetaData
from sqlalchemy.orm import sessionmaker
from huobifeeder.utils.redis import get_redis, get_channel
import json
from config import Config
from huobifeeder.backend import engine_md
logger = logging.getLogger()


class SimpleHandler(baseHandler):

    def handle(self, msg):
        if 'ch' in msg:
            # logging.info("msg:%s", msg)
            topic = msg.get('ch')
            _, symbol, _, period = topic.split('.')
            if period == '1min':
                data = msg.get('tick')
                # 调整相关属性
                data['ts_start'] = datetime.fromtimestamp(data.pop('id'))
                data['market'] = Config.MARKET_NAME  # 'huobi'
                data['ts_curr'] = datetime.fromtimestamp(msg['ts']/1000)
                logger.info("data:%s", data)
            else:
                logger.info(msg)

        elif 'rep' in msg:
            topic = msg.get('rep')
            data = msg.get('data')
            logger.info(msg)
        else:
            logger.warning(msg)


class DBHandler(baseHandler):

    def __init__(self, period, db_model=None, table_name=None, save_tick=False):
        """
        接收数据，并插入到对应数据库
        :param period: 周期
        :param db_model: 模型
        :param table_name: 表名
        """
        self.period = period
        self.save_tick = save_tick
        if db_model is not None:
            self.table_name = db_model.__tablename__
            self.md_orm_table = db_model.__table__
        elif table_name is not None:
            self.table_name = table_name
            self.md_orm_table = Table(table_name, MetaData(engine_md), autoload=True)
        baseHandler.__init__(self, 'DB[%s]' % self.table_name)
        self.session_maker = sessionmaker(bind=engine_md)
        self.session = None

        self.logger = logging.getLogger(f'DBHandler->{self.table_name}')
        self.md_orm_table_insert = self.md_orm_table.insert(on_duplicate_key_update=True)
        self.last_tick, self.ts_start_last_tick = {}, {}

    def handle(self, msg):
        if 'ch' in msg:
            topic = msg.get('ch')
            _, symbol, _, period = topic.split('.')
            if period == self.period:
                data = msg.get('tick')
                ts_start = datetime.fromtimestamp(data.pop('id'))
                data['ts_start'] = ts_start
                # 为了提高运行效率
                # 1）降低不必要的对 data 字典的操作
                # 2）降低不必要的数据库重复数据插入请求，保存前进行一次重复检查
                if self.save_tick or symbol not in self.ts_start_last_tick:
                    # 调整相关属性
                    data['market'] = Config.MARKET_NAME
                    data['ts_curr'] = datetime.fromtimestamp(msg['ts'] / 1000)
                    data['symbol'] = symbol
                    self.save_md(data)
                    self.logger.debug('invoke save_md %s', data)
                else:
                    # self.logger.info('ts_start: %s ts_start_last_tick[pair]:%s',
                    #                  ts_start, self.ts_start_last_tick[pair])
                    if ts_start != self.ts_start_last_tick[symbol]:
                        # self.logger.info('different')
                        data_last_tick, ts_last_tick = self.last_tick[symbol]
                        # 调整相关属性
                        data_last_tick['market'] = Config.MARKET_NAME
                        data_last_tick['ts_curr'] = datetime.fromtimestamp(ts_last_tick / 1000)
                        data_last_tick['symbol'] = symbol
                        self.save_md(data_last_tick)
                        self.logger.debug('invoke save_md last_tick %s', data_last_tick)

                self.last_tick[symbol] = (data, msg['ts'])
                self.ts_start_last_tick[symbol] = ts_start
            # else:
            #     self.logger.info(msg)

        elif 'rep' in msg:
            topic = msg.get('rep')
            data = msg.get('data')
            self.logger.info(msg)
        else:
            self.logger.warning(msg)

    @ProducerConsumer(threshold=2000, interval=60, pass_arg_list=True, is_class_method=True)
    def save_md(self, data_dic_list):
        """
        保存md数据到数据库及文件
        :param data_dic_list:
        :param session:
        :return:
        """
        # 仅调试使用
        # if self.table_name == 'md_min60_bc':
        # self.logger.info('%d data will be save to %s', len(data_dic_list), self.table_name)

        if data_dic_list is None or len(data_dic_list) == 0:
            self.logger.warning("data_dic_list 为空")
            return

        md_count = len(data_dic_list)
        # 保存到数据库
        if self.session is None:
            self.session = self.session_maker()
        try:
            self.session.execute(self.md_orm_table_insert, data_dic_list)
            self.session.commit()
            self.logger.info('%d 条实时行情 -> %s 完成', md_count, self.table_name)
        except:
            self.logger.exception('%d 条实时行情 -> %s 失败', md_count, self.table_name)


class PublishHandler(baseHandler):

    def __init__(self, market=Config.MARKET_NAME):
        baseHandler.__init__(self, name=self.__class__.__name__)
        self.market = market
        self.logger = logging.getLogger(self.__class__.__name__)
        self.r = get_redis()
        # 记录上一个tick的 st_start 用于判断是否开始分钟切换，key 是 (period, pair)
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
        # TODO: 设定一个定期检查机制，只发送订阅的品种，降低网络负载
        if 'ch' in msg:
            topic = msg.get('ch')
            _, symbol, _, period_str = topic.split('.')
            data = msg.get('tick')
            # 调整相关属性
            ts_start = datetime.fromtimestamp(data.pop('id'))
            data['ts_start'] = datetime_2_str(ts_start, format=STR_FORMAT_DATETIME2)
            data['market'] = Config.MARKET_NAME  # 'huobi'
            data['ts_curr'] = datetime_2_str(datetime.fromtimestamp(msg['ts'] / 1000), format=STR_FORMAT_DATETIME2)
            data['symbol'] = symbol
            # Json
            md_str = json.dumps(data)

            # 先发送Tick数据
            if period_str == '1min':
                # channel = f'md.{self.market}.tick.{symbol}'
                channel = get_channel(self.market, PeriodType.Tick, symbol)
                self.r.publish(channel, md_str)

            # period_str 1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year
            if period_str == '1min':
                period = PeriodType.Min1
            elif period_str == '5min':
                period = PeriodType.Min5
            elif period_str == '15min':
                period = PeriodType.Min15
            elif period_str == '30min':
                period = PeriodType.Min30
            elif period_str == '60min':
                period = PeriodType.Hour1
            elif period_str == '1day':
                period = PeriodType.Day1
            elif period_str == '1mon':
                period = PeriodType.Mon1
            elif period_str == '1week':
                period = PeriodType.Week1
            elif period_str == '1year':
                period = PeriodType.Year1

            # 分钟线切换时发送分钟线数据
            ts_start_last = self.last_ts_start_pair_tick.setdefault((period_str, symbol), None)
            if ts_start_last is not None and ts_start_last != ts_start:
                md_str_last = self.last_tick_pair_tick[(period_str, symbol)]
                # channel_min1 = f'md.{self.market}.{period}.{pair}'
                channel_min1 = get_channel(self.market, period, symbol)
                self.r.publish(channel_min1, md_str_last)

            self.last_ts_start_pair_tick[(period_str, symbol)] = ts_start
            self.last_tick_pair_tick[(period_str, symbol)] = md_str

        elif 'rep' in msg:
            # topic = msg.get('rep')
            # data = msg.get('data')
            self.logger.info(msg)
        else:
            self.logger.warning(msg)


class FileHandler(baseHandler):

    def __init__(self, market=Config.MARKET_NAME):
        baseHandler.__init__(self, name=self.__class__.__name__)
        self.market = market
        self.logger = logging.getLogger(self.__class__.__name__)
        self.r = get_redis()
        # 记录上一个tick的 st_start 用于判断是否开始分钟切换，key 是 (period, pair)
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
        # TODO: 设定一个定期检查机制，只发送订阅的品种，降低网络负载
        if 'ch' in msg:
            topic = msg.get('ch')
            _, symbol, _, period_str = topic.split('.')
            data = msg.get('tick')
            # 调整相关属性
            ts_start = datetime.fromtimestamp(data.pop('id'))
            data['ts_start'] = datetime_2_str(ts_start, format=STR_FORMAT_DATETIME2)
            data['market'] = Config.MARKET_NAME  # 'huobi'
            data['ts_curr'] = datetime_2_str(datetime.fromtimestamp(msg['ts'] / 1000), format=STR_FORMAT_DATETIME2)
            data['symbol'] = symbol
            # Json
            md_str = json.dumps(data)

            # 先发送Tick数据
            if period_str == '1min':
                # channel = f'md.{self.market}.tick.{symbol}'
                channel = get_channel(self.market, PeriodType.Tick, symbol)
                self.r.publish(channel, md_str)

            # period_str 1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year
            if period_str == '1min':
                period = PeriodType.Min1
            elif period_str == '5min':
                period = PeriodType.Min5
            elif period_str == '15min':
                period = PeriodType.Min15
            elif period_str == '30min':
                period = PeriodType.Min30
            elif period_str == '60min':
                period = PeriodType.Hour1
            elif period_str == '1day':
                period = PeriodType.Day1
            elif period_str == '1mon':
                period = PeriodType.Mon1
            elif period_str == '1week':
                period = PeriodType.Week1
            elif period_str == '1year':
                period = PeriodType.Year1

            # 分钟线切换时发送分钟线数据
            ts_start_last = self.last_ts_start_pair_tick.setdefault((period_str, symbol), None)
            if ts_start_last is not None and ts_start_last != ts_start:
                md_str_last = self.last_tick_pair_tick[(period_str, symbol)]
                # channel_min1 = f'md.{self.market}.{period}.{pair}'
                channel_min1 = get_channel(self.market, period, symbol)
                self.r.publish(channel_min1, md_str_last)

            self.last_ts_start_pair_tick[(period_str, symbol)] = ts_start
            self.last_tick_pair_tick[(period_str, symbol)] = md_str

        elif 'rep' in msg:
            # topic = msg.get('rep')
            # data = msg.get('data')
            self.logger.info(msg)
        else:
            self.logger.warning(msg)


class HeartBeatHandler(baseHandler):

    def __init__(self):
        baseHandler.__init__(self, name=self.__class__.__name__)
        self.time = datetime.now()

    def handle(self, msg):
        if 'ch' in msg:
            # logging.info("msg:%s", msg)
            self.time = datetime.now()

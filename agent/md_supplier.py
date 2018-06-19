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
from datetime import datetime, timedelta
import itertools
from huobitrade.service import HBWebsocket, HBRestAPI
from huobitrade import setKey
from config import Config
from backend import engine_md
from utils.db_utils import with_db_session
from backend.orm import SymbolPair
import time
from threading import Thread
from backend.orm import MDTick, MDMin1, MDMin1Temp, MDMin60, MDMin60Temp, MDMinDaily, MDMinDailyTemp
from backend.handler import DBHandler, PublishHandler
from sqlalchemy import func
from sqlalchemy.orm import aliased


logger = logging.getLogger()
# 设置秘钥
setKey(Config.EXCHANGE_ACCESS_KEY, Config.EXCHANGE_SECRET_KEY)


class MDSupplier(Thread):
    """接受订阅数据想redis发送数据"""

    def __init__(self, do_fill_history=False):
        super().__init__(name='huobi websocket', daemon=True)
        self.hb = HBWebsocket()
        self.api = HBRestAPI()
        self.init_symbols = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.do_fill_history = do_fill_history

        # 加载数据库表模型（已经废弃，因为需要支持多周期到不同的数据库表）
        # self.table_name = MDMin1Temp.__tablename__
        # self.md_orm_table = MDMin1Temp.__table__
        # self.md_orm_table_insert = self.md_orm_table.insert(on_duplicate_key_update=True)

    def init(self, periods=['1min', '60min', '1day'], init_symbols=False):

        if init_symbols or self.init_symbols:
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

            available_pairs = [d['base_currency'] + d['quote_currency']
                               for d in data_dic_list if d['symbol_partition'] == 'main']

            # 通过 on_open 方式进行订阅总是无法成功
            for pair, period in itertools.product(available_pairs, periods):
                self.hb.sub_dict[pair+period] = {'id': '', 'topic': f'market.{pair}.kline.{period}'}
        else:
            self.hb.sub_dict['ethbtc'] = {'id': '', 'topic': 'market.ethbtc.kline.1min'}
            self.hb.sub_dict['ethusdt'] = {'id': '', 'topic': 'market.ethusdt.kline.1min'}
            self.hb.sub_dict['ethusdt60'] = {'id': '', 'topic': 'market.ethusdt.kline.60min'}

        # handler = SimpleHandler('simple handler')
        # Tick 数据插入
        handler = DBHandler(period='1min', db_model=MDTick)
        self.hb.register_handler(handler)
        time.sleep(1)
        # 其他周期数据插入
        for period in periods:
            if period == '1min':
                db_model = MDMin1
            elif period == '60min':
                db_model = MDMin60
            elif period == '1day':
                db_model = MDMinDaily
            else:
                self.logger.warning(f'{period} 不是有效的周期')
                continue
            handler = DBHandler(period=period, db_model=db_model)
            self.hb.register_handler(handler)
            time.sleep(1)

        # 数据redis广播
        handler = PublishHandler(market=Config.MARKET_NAME)
        self.hb.register_handler(handler)
        logger.info("api.get_timestamp %s", self.api.get_timestamp())

    def run(self):
        self.hb.run()
        self.logger.info('启动')
        # 补充历史数据
        if self.fill_history:
            self.logger.info('开始补充历史数据')
            self.fill_history()
        while True:
            time.sleep(1)

    def fill_history(self, periods=['1min', '60min', '1day']):
        for period in periods:
            if period == '1min':
                model_tot, model_tmp = MDMin1, MDMin1Temp
            elif period == '60min':
                model_tot, model_tmp = MDMin60, MDMin60Temp
            elif period == '1day':
                model_tot, model_tmp = MDMinDaily, MDMinDailyTemp
            else:
                self.logger.warning(f'{period} 不是有效的周期')

            self.fill_history_period(model_tot, model_tmp)

    def fill_history_period(self, model_tot, model_tmp):
        """
        根据数据库中的支持 symbol 补充历史数据
        :param model_tot:
        :param model_tmp:
        :return:
        """
        with with_db_session(engine_md) as session:
            data = session.query(SymbolPair).filter(
                SymbolPair.market == Config.MARKET_NAME, SymbolPair.symbol_partition == 'main').all()
            pair_datetime_latest_dic = dict(
                session.query(
                    model_tmp.pair, func.max(model_tmp.ts_start)
                ).filter(model_tmp.market == Config.MARKET_NAME).group_by(model_tmp.pair).all()
            )

        # 循环获取每一个交易对的历史数据
        for symbol_info in data:
            pair = f'{symbol_info.base_currency}{symbol_info.quote_currency}'
            if pair in pair_datetime_latest_dic:
                datetime_latest = pair_datetime_latest_dic[pair]
                size = min([2000, int((datetime.now() - datetime_latest).seconds / 60 * 2)])
            else:
                size = 2000
            ret = self.api.get_kline(pair, '1min', size=size)
            if ret['status'] == 'ok':
                data_list = ret['data']
                data_dic_list = []
                for data in data_list:
                    ts_start = datetime.fromtimestamp(data.pop('id'))
                    data['ts_start'] = ts_start
                    data['market'] = Config.MARKET_NAME
                    data['ts_curr'] = ts_start + timedelta(seconds=59)  # , microseconds=999999
                    data['pair'] = pair
                    data_dic_list.append(data)
                self._save_md(data_dic_list, pair, model_tot, model_tmp)
            else:
                self.logger.error(ret)
            # 过于频繁方位可能导致链接失败
            time.sleep(5)

    def _save_md(self, data_dic_list, pair, model_tot: MDMin1, model_tmp: MDMin1Temp):
        """
        保存md数据到数据库及文件
        :param data_dic_list:
        :param pair:
        :param model_tot:
        :param model_tmp:
        :return:
        """

        if data_dic_list is None or len(data_dic_list) == 0:
            self.logger.warning("data_dic_list 为空")
            return

        md_count = len(data_dic_list)
        # 保存到数据库
        with with_db_session(engine_md) as session:
            try:
                # session.execute(self.md_orm_table_insert, data_dic_list)
                session.execute(model_tmp.__table__.insert(on_duplicate_key_update=True), data_dic_list)
                self.logger.info('%d 条数据保存到 %s 完成', md_count, model_tmp.__tablename__)
                sql_str = f"""insert into {model_tot.__tablename__} select * from {model_tmp.__tablename__} 
                where market=:market and pair=:pair 
                ON DUPLICATE KEY UPDATE open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close)
                , amount=VALUES(amount), vol=VALUES(vol), count=VALUES(count)"""
                session.execute(sql_str, params={"pair": pair, "market": Config.MARKET_NAME})
                datetime_latest = session.query(
                    func.max(model_tmp.ts_start).label('ts_start_latest')
                ).filter(
                    model_tmp.pair == pair,
                    model_tmp.market == Config.MARKET_NAME
                ).scalar()
                # issue:
                # https://stackoverflow.com/questions/9882358/how-to-delete-rows-from-a-table-using-an-sqlalchemy-query-without-orm
                delete_count = session.query(model_tmp).filter(
                    model_tmp.market == Config.MARKET_NAME,
                    model_tmp.pair == pair,
                    model_tmp.ts_start < datetime_latest
                ).delete()
                self.logger.debug('%d 条历史数据被清理，最新数据日期 %s', delete_count, datetime_latest)
                session.commit()
            except:
                self.logger.exception('%d 条数据保存到 %s 失败', md_count, model_tot.__tablename__)


def start_supplier(init_symbols=False, do_fill_history=False) -> MDSupplier:
    supplier = MDSupplier(do_fill_history=do_fill_history)
    supplier.init(init_symbols=init_symbols)
    supplier.start()
    return supplier

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
from requests.exceptions import ProxyError
from datetime import datetime, timedelta
import itertools
from huobitrade.service import HBWebsocket, HBRestAPI
from huobitrade import setKey
from config import Config
from huobifeeder.backend import engine_md
from huobifeeder.utils.db_utils import with_db_session
from huobifeeder.utils.fh_utils import try_n_times
from huobifeeder.backend.orm import SymbolPair
import time
from threading import Thread
from huobifeeder.backend.orm import MDTick, MDMin1, MDMin1Temp, MDMin60, MDMin60Temp, MDMinDaily, MDMinDailyTemp
from huobifeeder.backend.handler import DBHandler, PublishHandler
from sqlalchemy import func


logger = logging.getLogger()
# 设置秘钥
setKey(Config.EXCHANGE_ACCESS_KEY, Config.EXCHANGE_SECRET_KEY)


class MDFeeder(Thread):
    """接受订阅数据想redis发送数据"""

    def __init__(self, init_symbols=False, do_fill_history=False):
        super().__init__(name='huobi websocket', daemon=True)
        self.hb = HBWebsocket()
        self.api = HBRestAPI()
        self.init_symbols = init_symbols
        self.logger = logging.getLogger(self.__class__.__name__)
        self.do_fill_history = do_fill_history

        # 加载数据库表模型（已经废弃，因为需要支持多周期到不同的数据库表）
        # self.table_name = MDMin1Temp.__tablename__
        # self.md_orm_table = MDMin1Temp.__table__
        # self.md_orm_table_insert = self.md_orm_table.insert(on_duplicate_key_update=True)

    def init(self, periods=['1min', '60min', '1day'], symbol_partition_set={'main', 'innovation', 'bifurcation'}):
        """
        初始化，订阅行情
        默认1分钟、1小时、1日
        包含 {'main', 'innovation', 'bifurcation'} 全部币种
        :param periods:
        :param symbol_partition_set:
        :return:
        """

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

            available_pairs = [d['base_currency'] + d['quote_currency']
                               for d in data_dic_list if d['symbol_partition'] in symbol_partition_set]

            # 通过 on_open 方式进行订阅总是无法成功
            for pair, period in itertools.product(available_pairs, periods):
                self.hb.sub_dict[pair+period] = {'id': '', 'topic': f'market.{pair}.kline.{period}'}
        else:
            self.hb.sub_dict['ethbtc60'] = {'id': '', 'topic': 'market.ethbtc.kline.60min'}
            # self.hb.sub_dict['ethusdt'] = {'id': '', 'topic': 'market.ethusdt.kline.1min'}
            self.hb.sub_dict['ethusdt60'] = {'id': '', 'topic': 'market.ethusdt.kline.60min'}

        # handler = SimpleHandler('simple handler')
        # Tick 数据插入
        handler = DBHandler(period='1min', db_model=MDTick, save_tick=True)
        self.hb.register_handler(handler)
        time.sleep(1)
        # 其他周期数据插入
        for period in periods:
            save_tick = False
            if period == '1min':
                db_model = MDMin1
            elif period == '60min':
                db_model = MDMin60
                # save_tick = True
            elif period == '1day':
                db_model = MDMinDaily
            else:
                self.logger.warning(f'{period} 不是有效的周期')
                continue
            handler = DBHandler(period=period, db_model=db_model, save_tick=save_tick)
            self.hb.register_handler(handler)
            time.sleep(1)

        # 数据redis广播
        handler = PublishHandler(market=Config.MARKET_NAME)
        self.hb.register_handler(handler)
        server_datetime = self.get_server_datetime()
        logger.info("api.服务期时间 %s 与本地时间差： %f 秒",
                    server_datetime, (datetime.now() - server_datetime).total_seconds())
        self.check_state()

    def check_state(self):
        self.check_accounts()
        data = self.get_balance()
        for bal in data:
            self.logger.info(f"{bal['currency']} : {bal['balance']}")

    def get_server_datetime(self):
        ret_data = self.api.get_timestamp()
        server_datetime = datetime.fromtimestamp(ret_data['data']/1000)
        return server_datetime

    def get_accounts(self):
        ret_data = self.api.get_accounts()

        account_info = [acc for acc in ret_data['data']]
        return account_info

    def check_accounts(self):
        account_info = self.get_accounts()
        is_ok = True
        for acc in account_info:
            if acc['state'] != 'working':
                self.logger.error(f'账户[%d] %s %s 状态异常：%s',
                                  acc['id'], acc['type'], acc['subtype'], acc['state'])
                is_ok = False
        return is_ok

    def get_balance(self, no_zero_only=True):
        ret_data = self.api.get_balance()
        acc_balance = ret_data['data']['list']
        if no_zero_only:
            ret_acc_balance = [balance for balance in acc_balance if balance['balance'] != '0']
        else:
            ret_acc_balance = acc_balance
        return ret_acc_balance

    def get_orders_info(self, symbol, states='submitted'):
        ret_data = self.api.get_orders_info(symbol=symbol, states=states)
        return ret_data['data']

    def run(self):
        self.hb.run()
        self.logger.info('启动')
        # 补充历史数据
        if self.do_fill_history:
            self.logger.info('开始补充历史数据')
            self.fill_history()
        while True:
            time.sleep(1)

    def fill_history(self, periods=['1day', '1min', '60min']):
        for period in periods:
            if period == '1min':
                model_tot, model_tmp = MDMin1, MDMin1Temp
            elif period == '60min':
                model_tot, model_tmp = MDMin60, MDMin60Temp
            elif period == '1day':
                model_tot, model_tmp = MDMinDaily, MDMinDailyTemp
            else:
                self.logger.warning(f'{period} 不是有效的周期')

            self.fill_history_period(period, model_tot, model_tmp)

    def fill_history_period(self, period, model_tot, model_tmp: MDMin1Temp):
        """
        根据数据库中的支持 symbol 补充历史数据
        :param period:
        :param model_tot:
        :param model_tmp:
        :return:
        """
        with with_db_session(engine_md) as session:
            data = session.query(SymbolPair).filter(
                SymbolPair.market == Config.MARKET_NAME).all()  # , SymbolPair.symbol_partition == 'main'
            pair_datetime_latest_dic = dict(
                session.query(
                    model_tmp.symbol, func.max(model_tmp.ts_start)
                ).filter(model_tmp.market == Config.MARKET_NAME).group_by(model_tmp.symbol).all()
            )

        # 循环获取每一个交易对的历史数据
        for symbol_info in data:
            symbol = f'{symbol_info.base_currency}{symbol_info.quote_currency}'
            if symbol in pair_datetime_latest_dic:
                datetime_latest = pair_datetime_latest_dic[symbol]
                if period == '1min':
                    second_of_period = 60
                elif period == '60min':
                    second_of_period = 60 * 60
                elif period == '1day':
                    second_of_period = 60 * 60 * 24
                else:
                    self.logger.warning(f'{period} 不是有效的周期')
                    continue
                size = min([2000, int((datetime.now() - datetime_latest).seconds / second_of_period * 1.2)])
            else:
                size = 2000
            if size <= 1:
                continue
            ret = self.get_kline(symbol, period, size=size)
            # for n in range(1, 3):
            #     try:
            #         ret = self.api.get_kline(symbol, period, size=size)
            #     except ProxyError:
            #         self.logger.exception('symbol:%s, period:%s, size=%d', symbol, period, size)
            #         ret = None
            #         time.sleep(5)
            #         continue
            #     break
            if ret is None:
                continue
            if ret['status'] == 'ok':
                data_list = ret['data']
                data_dic_list = []
                for data in data_list:
                    ts_start = datetime.fromtimestamp(data.pop('id'))
                    data['ts_start'] = ts_start
                    data['market'] = Config.MARKET_NAME
                    data['ts_curr'] = ts_start + timedelta(seconds=59)  # , microseconds=999999
                    data['symbol'] = symbol
                    data_dic_list.append(data)
                self._save_md(data_dic_list, symbol, model_tot, model_tmp)
            else:
                self.logger.error(ret)
            # 过于频繁方位可能导致链接失败
            time.sleep(5)  # 已经包含在 try_n_times 里面

    @try_n_times(5, sleep_time=5, logger=logger)
    def get_kline(self, symbol, period, size):
        ret = self.api.get_kline(symbol, period, size=size)
        return ret

    def _save_md(self, data_dic_list, symbol, model_tot: MDMin1, model_tmp: MDMin1Temp):
        """
        保存md数据到数据库及文件
        :param data_dic_list:
        :param symbol:
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
                self.logger.info('%d 条 %s 历史数据保存到 %s 完成', md_count, symbol, model_tmp.__tablename__)
                sql_str = f"""insert into {model_tot.__tablename__} select * from {model_tmp.__tablename__} 
                where market=:market and symbol=:symbol 
                ON DUPLICATE KEY UPDATE open=VALUES(open), high=VALUES(high), low=VALUES(low), close=VALUES(close)
                , amount=VALUES(amount), vol=VALUES(vol), count=VALUES(count)"""
                session.execute(sql_str, params={"symbol": symbol, "market": Config.MARKET_NAME})
                datetime_latest = session.query(
                    func.max(model_tmp.ts_start).label('ts_start_latest')
                ).filter(
                    model_tmp.symbol == symbol,
                    model_tmp.market == Config.MARKET_NAME
                ).scalar()
                # issue:
                # https://stackoverflow.com/questions/9882358/how-to-delete-rows-from-a-table-using-an-sqlalchemy-query-without-orm
                delete_count = session.query(model_tmp).filter(
                    model_tmp.market == Config.MARKET_NAME,
                    model_tmp.symbol == symbol,
                    model_tmp.ts_start < datetime_latest
                ).delete()
                self.logger.debug('%d 条 %s 历史数据被清理，最新数据日期 %s', delete_count, symbol, datetime_latest)
                session.commit()
            except:
                self.logger.exception('%d 条 %s 数据保存到 %s 失败', md_count, symbol, model_tot.__tablename__)


def start_supplier(init_symbols=False, do_fill_history=False) -> MDFeeder:
    supplier = MDFeeder(init_symbols=init_symbols, do_fill_history=do_fill_history)
    supplier.init()
    supplier.start()
    return supplier

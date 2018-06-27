#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/16 17:54
@File    : redis.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
from redis import StrictRedis, ConnectionPool
from redis.client import PubSub
from config import Config
from abat.common import PeriodType
_redis_client_dic = {}


def get_channel(market=None, period: PeriodType=PeriodType.Min1, symbol=''):
    """
    'md.{market}.{period}.{symbol}' or 'md.{period}.{symbol}'
    例如：
    md.huobi.Min1.ethusdt
    md.huobi.Tick.eosusdt
    通过 redis-cli 可以 PUBSUB CHANNELS 查阅活跃的频道
    :param market:
    :param period:
    :param symbol:
    :return:
    """
    if market:
        channel_str = f'md.{market}.{period.name}.{symbol}'
    else:
        channel_str = f'md.{period.name}.{symbol}'
    #     md.market.tick.pair
    return channel_str


def get_redis(db=0) -> StrictRedis:
    """
    get StrictRedis object
    :param db:
    :return:
    """
    if db in _redis_client_dic:
        redis_client = _redis_client_dic[db]
    else:
        conn = ConnectionPool(host=Config.REDIS_INFO_DIC['REDIS_HOST'],
                              port=Config.REDIS_INFO_DIC['REDIS_PORT'],
                              db=db)
        redis_client = StrictRedis(connection_pool=conn)
        _redis_client_dic[db] = redis_client
    return redis_client

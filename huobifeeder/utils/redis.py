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

_redis_client_dic = {}


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

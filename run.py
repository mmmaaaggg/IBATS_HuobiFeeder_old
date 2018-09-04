#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/12 20:38
@File    : run.py
@contact : mmmaaaggg@163.com
@desc    : 
"""
import time
import logging
from huobifeeder.backend.orm import init
from huobifeeder.feed.md_feeder import start_supplier
logger = logging.getLogger()


if __name__ == "__main__":
    init(True)

    # while True:
    supplier = start_supplier(init_symbols=True, do_fill_history=True)
    while supplier.is_working:
        time.sleep(5)
    supplier.stop()
    supplier.join()
    # logger.warning('子线程已经结束，开始新的线程')
    # time.sleep(10)

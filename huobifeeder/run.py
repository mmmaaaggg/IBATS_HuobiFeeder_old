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
from huobifeeder.backend.orm import init
from huobifeeder.feed.md_feeder import start_supplier


if __name__ == "__main__":
    init(True)

    supplier = start_supplier(init_symbols=True, do_fill_history=True)
    while supplier.is_alive():
        time.sleep(1)

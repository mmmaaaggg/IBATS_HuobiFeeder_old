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
from backend.orm import init
from agent.md_supplier import start_supplier


if __name__ == "__main__":
    init()

    supplier = start_supplier()
    while supplier.is_alive():
        time.sleep(1)

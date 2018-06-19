#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/13 15:42
@File    : bulk_pattern.py
@contact : mmmaaaggg@163.com
@desc    : 
"""


def bulk_invoke(func):
    print('bulk func')
    a = []

    def bulk_func(n):
        a.append(n)
        if len(a) > 3:
            func(a)
            a.clear()

    return bulk_func


@bulk_invoke
def fprint(n):
    print(n)


if __name__ == "__main__":
    for n in range(10):
        fprint(n)

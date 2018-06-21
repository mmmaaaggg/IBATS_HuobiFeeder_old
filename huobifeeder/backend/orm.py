#! /usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author  : MG
@Time    : 2018/6/12 13:02
@File    : orm.py
@contact : mmmaaaggg@163.com
@desc    :
"""
from sqlalchemy import Column, Integer, String, UniqueConstraint, TIMESTAMP
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.ext.declarative import declarative_base
from huobifeeder.utils import with_db_session
from huobifeeder.backend import engine_md
from config import Config
import logging
logger = logging.getLogger()
BaseModel = declarative_base()


class SymbolPair(BaseModel):
    __tablename__ = 'symbol_pair_info'
    id = Column(Integer, autoincrement=True, unique=True)
    market = Column(String(10), primary_key=True)
    base_currency = Column(String(10), primary_key=True)
    quote_currency = Column(String(10), primary_key=True)
    price_precision = Column(DOUBLE)
    amount_precision = Column(DOUBLE)
    symbol_partition = Column(String(12))
    __table_args__ = (
        UniqueConstraint('base_currency', 'quote_currency'),
    )


class MDTick(BaseModel):
    __tablename__ = 'md_min1_tick_bc'
    id = Column(Integer, autoincrement=True, unique=True)
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP)
    ts_curr = Column(TIMESTAMP, primary_key=True)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMin1(BaseModel):
    __tablename__ = 'md_min1_bc'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMin1Temp(BaseModel):
    __tablename__ = 'md_min1_bc_temp'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMin60(BaseModel):
    __tablename__ = 'md_min60_bc'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMin60Temp(BaseModel):
    __tablename__ = 'md_min60_bc_temp'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMinDaily(BaseModel):
    __tablename__ = 'md_daily_bc'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


class MDMinDailyTemp(BaseModel):
    __tablename__ = 'md_daily_bc_temp'
    market = Column(String(10), primary_key=True)
    pair = Column(String(10), primary_key=True)
    ts_start = Column(TIMESTAMP, primary_key=True)
    ts_curr = Column(TIMESTAMP)
    open = Column(DOUBLE)
    high = Column(DOUBLE)
    low = Column(DOUBLE)
    close = Column(DOUBLE)
    amount = Column(DOUBLE)
    vol = Column(DOUBLE)
    count = Column(DOUBLE)


def init(alter_table=False):
    BaseModel.metadata.create_all(engine_md)
    if alter_table:
        with with_db_session(engine=engine_md) as session:
            for table_name, _ in BaseModel.metadata.tables.items():
                sql_str = f"show table status from {Config.DB_SCHEMA_MD} where name=:table_name"
                row_data = session.execute(sql_str, params={'table_name': table_name}).first()
                if row_data is None:
                    continue
                if row_data[1].lower() == 'myisam':
                    continue

                logger.info('修改 %s 表引擎为 MyISAM', table_name)
                sql_str = "ALTER TABLE %s ENGINE = MyISAM" % table_name
                session.execute(sql_str)

            # This is an issue  https://www.mail-archive.com/sqlalchemy@googlegroups.com/msg19744.html
            session.execute(f"ALTER TABLE {SymbolPair.__tablename__} CHANGE COLUMN `id` `id` INT(11) NULL AUTO_INCREMENT")
            session.commit()
            # This is an issue  https://www.mail-archive.com/sqlalchemy@googlegroups.com/msg19744.html
            session.execute(f"ALTER TABLE {MDTick.__tablename__} CHANGE COLUMN `id` `id` INT(11) NULL AUTO_INCREMENT")
            session.commit()

    logger.info("所有表结构建立完成")


if __name__ == "__main__":
    init()

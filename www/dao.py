# -*- coding: UTF-8 -*-
"""  """
import logging
import aiomysql

logging.basicConfig(level=logging.INFO)

# 创建出数据库连接池
# 连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务
async def create_pool(loop, **kw):
    logging.info('create database connection pool..')
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', '127.0.0.1'),
        port=kw.get('port', 3306),
        user=kw['root'],
        password=kw['root'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


# 要执行SELECT语句，我们用select函数执行，需要传入SQL语句和SQL参数
async def select(sql, args, size=None):
    logging.log(sql, args)
    global __pool
    # 从数据库连接池中获取一个数据库连接
    with (await __pool) as conn:
        cur = await conn.cursor(aiomysql.DictCursor)
        # SQL语句的占位符是?，而MySQL的占位符是 %s，select()函数在内部自动替换
        await cur.execute(sql.replace('?', '%s'), args or ())
        # 如果传入size参数，就通过fetchmany()获取所有记录
        # 获取最多指定数量的记录，否则，通过fetchall()
        if size:
            rs = await cur.fetchmany(size)
        else:
            rs = await cur.fetchall()
        await cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs


# 要执行INSERT、UPDATE、DELETE语句，可以定义一个通用的execute()函数
async def execute(sql, args):
    logging.log(sql, args)
    global __pool
    with (await __pool) as conn:
        try:
            cur = await conn.cursor(aiomysql.DictCursor)
            await cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            await cur.close()
        except BaseException as e:
                raise
        return affected
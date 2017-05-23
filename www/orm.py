# -*- coding: UTF-8 -*-
"""自己编写的ORM框架"""
import logging
import aiomysql

logging.basicConfig(level=logging.INFO)

def log(sql, args):
    logging.info('SQL: %s' % sql)


# 创建出数据库连接池
# 连接池由全局变量__pool存储，缺省情况下将编码设置为utf8，自动提交事务
async def create_pool(loop, **kw):
    logging.info('create database connection pool..')
    global __pool
    __pool = await aiomysql.create_pool(
        # **kw参数可以包含所有连接需要用到的关键字参数
        host=kw.get('host', '127.0.0.1'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['database'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),  # 自动提交
        # 默认最大连接数为10
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        # 接收一个event_loop实例
        loop=loop
    )


# 要执行SELECT语句，我们用select函数执行，需要传入SQL语句和SQL参数
async def select(sql, args, size=None):
    log(sql, args)
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
    log(sql, args)
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

def create_args_string(param):
    L = []
    for n in range(param):
        L.append('?')
    # 以','为分隔符，将列表合成字符串
    return ", ".join(L)


# 使用元类来创建对象,会调用__new__()方法创建对象
# __new__()方法接收到的参数依次是：
#       1. 当前准备创建的类的对象；
#       2. 类的名字；
#       3. 类继承的父类集合；
#       4. 类的方法或者属性的集合。
class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        # 排除Model类本身:
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)

        # 获取table名称,根据__table__属性获取表名，如果为空，则用类名作为表名:
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (table: %s)' % (name, tableName))

        # 获取所有的Field和主键名:
        mappings = dict()
        fields = []
        primaryKey = None  # primaryKey的初始值设为None,表示主键
        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mapping: %s ==> %s' % (k, v))
                mappings[k] = v

                # 如果Field对象v的primary_key为True，就进入下面的判断语句
                if v.primary_key:
                    # 找到主键:
                    # 如果primaryKey的值不为None，说明在前面的循环中已经确定了主键，不能有多个主键，
                    # 所以就抛出主键重复的异常
                    if primaryKey:  # None在if判断语句中表示False
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k  # 将属性k作为主键
                else:
                    fields.append(k)  # 其他的属性作为普通的字段

        if not primaryKey:  # not相当于非
            # 经过上面的循环之后，仍没有找到主键，就抛出未找到主键的异常
            raise RuntimeError('Primary key not found.')

        # 从类属性中删除Field属性
        for k in mappings.keys():
            attrs.pop(k)

        # map()函数接收两个参数，一个是函数，一个是Iterable，
        # map将传入的函数依次作用到序列的每个元素，并把结果作为新的Iterator返回
        # 所以escaped_fields是一个包含了所有非主键字段的list集合
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))

        attrs['__mappings__'] = mappings  # 保存属性和列的映射关系
        attrs['__table__'] = tableName  # 保存表名
        attrs['__primary_key__'] = primaryKey  # 主键属性名
        attrs['__fields__'] = fields  # 除主键外的属性名
        # 构造默认的SELECT, INSERT, UPDATE和DELETE语句:
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey, ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (
            tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (
            tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)


# 定义ORM所有映射的基类：Model
# Model类的任何子类可以映射为一个数据库表
# Model类可以看做是对所有数据库表操作的基本定义的映射

# 基于字典查询形式
# Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__，能够实现属性操作
# 实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法
class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
    # 通过__getattr__和__setattr__方法使得能通过user.name的方式访问对象的属性
    # _getattr_用于查询不在__dict__系统中的属性
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    # 返回对象self属性为key的值，如果没有，则返回None
    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                # 当value为None并且默认值不为None，就用默认值来代表key对应的值
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        """find object by where clause."""
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)  # 语句中是否有orderBy参数
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit', None)  # 语句中是否有limit参数
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s ' % str(limit))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    async def findNumber(cls, selectField, where=None, args=None):
        """find number by select and where."""
        # 这里的 _num_ 为别名，任何客户端都可以按照这个名称引用这个列，就像它是个实际的列一样
        sql = ['select %s _num_ from `%s` ' % (selectField, cls.__table__)]

        if where:
            sql.append('where')
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        # rs[0]表示一行数据,是一个字典，而rs是一个列表
        return rs[0]['_num_']

    @classmethod
    async def find(cls, pk):
        """find object by primary key."""
        rs = await select('%s where `%s`= ?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        # 1.将rs[0]转换成关键字参数元组，rs[0]为dict，格式为：{'id':1,'name':'wanzhiwen'}
        # 2.通过<class '__main__.User'>(位置参数元组)，产生一个实例对象
        return cls(**rs[0])

    async def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:
            logging.warning('Failed to insert record: affected rows: %s' % rows)

    async def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warning('Failed to update by primary key: affected rows: %s' % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warning('Failed to remove by primary key: affected rows: %s' % rows)

# 定义Field类，负责保存(数据库)表的字段名和字段类型
class Field(object):
    # 表的字段包含名字、类型、是否为表的主键和默认值
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    # 当打印(数据库)表时，输出(数据库)表的信息:类名，字段类型和名字
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)


class StringField(Field):
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)

class BooleanField(Field):

    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)


class IntegerField(Field):

    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'bigint', primary_key, default)


class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'real', primary_key, default)

class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)

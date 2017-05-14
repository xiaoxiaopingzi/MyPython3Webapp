# -*- coding: UTF-8 -*-
"""用于代码编写过程中的额一些测试"""
import orm
from models import User, Blog, Comment
import asyncio


def sf():
    pass


a = 1
print('变量a的类型是:%s' % type(a))
print(type(type(a)))
print('函数sf的类型是:%s' % type(sf))
print(type(type(sf)))

if None:
    print('none')
if not None:
    print('not None')

L = ['name', 'age', 'score']
print(list(map(lambda f: '`%s`' % f, L)))
print(', '.join(L))


async def test(loop):
    await orm.create_pool(loop=loop, user='root', password='root', database='mypython3webapp')
    u = User(name='wanzhiwen', email='1231231@qq.com', passwd='101010', image='about:blank')
    await u.save()
    # await User.findAll()


loop = asyncio.get_event_loop()
loop.run_until_complete(test(loop))
print('test')
print('success')
loop.close()

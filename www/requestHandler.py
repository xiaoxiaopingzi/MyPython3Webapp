# -*- coding: UTF-8 -*-
"""编写一个比aiohttp更高层的框架"""
import asyncio
import functools
import inspect
import logging
from aiohttp import web

# 装饰器，用于获取GET提交的路径和参数
def get(path):
    """
    Define decorator @get('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper

    return decorator


# 装饰器，用于获取POST提交的路径和参数
def post(path):
    """
    Define decorator @post('/path')
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)

        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper

    return decorator


# RequestHandler目的就是从URL处理函数（如handlers.index）中分析其需要接收的参数，从web.request对象中获取必要的参数，
# 调用URL处理函数，然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求
class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn

    async def __call__(self, request):
        kw = {}  # ... 获取参数
        r = await self._func(**kw)
        return r


def add_route(app, fn):
    # 经过装饰器的装饰后，可以用__method__与__route__来获取请求的方法和路径
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    # 如果method并且path有一个为None，说明传入的方法没有用get或者post装饰器装饰，则抛出异常
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))

    # asyncio.iscoroutinefunction(fn)——判断函数是否是协程函数，是就返回True
    # inspect.isgeneratorfunction(fn)——Return true if the object is a Python generator function
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn = asyncio.coroutine(fn)  # 如果函数不是协程函数，就把它变成协程函数
    logging.info(
        'add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 正式注册为对应的url处理函数
    # RequestHandler类的实例是一个可以call的函数
    # 自省函数 '__call__'
    app.router.add_route(method, path, RequestHandler(app, fn))


def add_routes(app, module_name):
    # rfind()函数的作用是返回'.'在字符串module_name中最大的索引,返回-1则表示每找到'.'符号
    n = module_name.rfind('.')
    if n == (-1):
        # __import__ 作用同import语句，但__import__是一个函数，并且只接收字符串作为参数,
        # 其实import语句就是调用这个函数进行导入工作的, 其返回值是对应导入模块的引用
        # __import__('os',globals(),locals(),['path','pip']) ,等价于from os import path, pip
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n + 1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn = getattr(mod, attr)
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                add_route(app, fn)


async def logger_factory(app, handler):
    async def logger(request):
        # 记录日志:
        logging.info('Request: %s %s' % (request.method, request.path))
        # 继续处理请求:
        return (await handler(request))

    return logger

async def response_factory(app, handler):
    async def response(request):
        # 结果:
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):  # 下载文件
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):    # 网页
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp

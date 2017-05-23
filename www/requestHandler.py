# -*- coding: UTF-8 -*-
"""编写一个比aiohttp更高层的框架"""
import asyncio
import functools
import inspect
import logging
import os
import hashlib
import time
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from urllib import parse
from aiohttp import web

try:
    from apis import APIError
    from config import configs
    from models import User, Comment, Blog, next_id
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')


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

# ----使用inspect模块中的signature方法来获取函数的参数，实现一些复用功能--
# inspect.Parameter 的类型有5种：
# POSITIONAL_ONLY       只能是位置参数
# KEYWORD_ONLY          关键字参数且提供了key
# VAR_POSITIONAL        相当于是 *args
# VAR_KEYWORD           相当于是 **kw
# POSITIONAL_OR_KEYWORD
def get_required_kw_args(fn):
    args = []
    # 将参数名称按顺序映射到相应的Parameter对象
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # Parameter.default——参数的默认值,如果参数没有默认值,则该属性设置为Parameter.empty
        # Parameter.empty——指定缺少默认值和注释的特殊类级标记
        # 如果url处理函数需要传入关键字参数，且默认是空的话，获取这个key
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        # 如果url处理函数需要传入关键字参数，获取这个key
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

# 判断请求的url中是否有关键字参数
def has_named_kw_args(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

# 判断请求的url中是否有*args参数
def has_var_kw_arg(fn):
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

# 判断请求的url中是否有key为request的关键字参数,有则返回True，否则返回False
def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    # 判断是否存在一个参数叫做request，并且该参数要在其他普通的位置参数之后
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
            # request参数必须是函数中最后的命名参数
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# RequestHandler目的就是从URL处理函数（如handlers.index）中分析其需要接收的参数，从web.request对象中获取必要的参数，
# 调用URL处理函数，然后把结果转换为web.Response对象，这样，就完全符合aiohttp框架的要求
class RequestHandler(object):
    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)
        self._has_var_kw_arg = has_var_kw_arg(fn)
        self._has_named_kw_args = has_named_kw_args(fn)
        self._named_kw_args = get_named_kw_args(fn)
        self._required_kw_args = get_required_kw_args(fn)

    # 1.定义kw对象，用于保存参数
    # 2.判断URL处理函数是否存在参数，如果存在则根据是POST还是GET方法将request请求内容保存到kw
    # 3.如果kw为空(说明request没有请求内容)，则将match_info列表里面的资源映射表赋值给kw；如果不为空则把命名关键字参数的内容给kw
    # 4.完善_has_request_arg和_required_kw_args属性
    async def __call__(self, request):
        kw = None
        # 如果有需要处理的参数
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
            # POST提交的参数可以直接获取
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    # 解析url中?后面的键值对内容并保存到request_content
                    '''
                    qs = 'first=f,s&second=s'
                    parse.parse_qs(qs, True).items()
                    >>> dict([('first', ['f,s']), ('second', ['s'])])
                    '''
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            # 参数为空说明没有从request对象中获取到参数,或者URL处理函数没有参数
            '''
            def hello(request):
                    text = '<h1>hello, %s!</h1>' % request.match_info['name']
                    return web.Response()
            app.router.add_route('GET', '/hello/{name}', hello)
            '''
            '''if not self._has_var_kw_arg and not self._has_kw_arg and not self._required_kw_args:
                # 当URL处理函数没有参数时，将request.match_info设为空，防止调用出错
                request_content = dict()
            '''
            kw = dict(**request.match_info)
        else:
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw， 从request_content中删除URL处理函数中所有不需要的参数
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg: 检查关键字参数的名字是否和match_info中的重复
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        # 将request参数添加到kw字典中
        if self._has_request_arg:
            kw['request'] = request
        # check required kw: 检查是否有必须关键字参数
        if self._required_kw_args:
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        # 以上代码均是为了获取调用参数
        logging.info('call with args: %s' % str(kw))  # 打印所有的参数
        try:
            r = await self._func(**kw)  # 将请求的url后面带上的参数作为函数fn的参数，等待函数fn的执行结果
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)


# 对单个函数进行注册
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
    # RequestHandler类的实例是一个可以被call的函数
    app.router.add_route(method, path, RequestHandler(app, fn))   # 注册处理函数


# 添加CSS等静态文件所在路径
def add_static(app):
    # 获取当前文件所在的文件夹下的static文件夹的路径
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)  # 添加静态文件
    logging.info('add static %s => %s' % ('/static/', path))

def add_routes(app, module_name):
    # rfind()函数的作用是返回'.'在字符串module_name中最大的索引,返回-1则表示没找到'.'符号
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

# 在调用方法之前，用日志记录请求的方法(GET或者POST)以及路径
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger

# 如果请求的方式是POST，并且请求的类型是application/json或者application/x-www-form-urlencoded
# 就用日志记录请求的参数
async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

COOKIE_NAME = 'myblogsession'
_COOKIE_KEY = configs.secret
async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        # 从request中根据cookie的名字获取cookies
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            # 解析cookie，获取user对象
            user = await cookie2user(cookie_str)
            if user:  # 如果user不为None，表明这个cookie有效，则将user绑定到request对象中
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        # 管理页面需要管理员权限才允许访问
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/signin')
        return (await handler(request))
    return auth

# 对cookie进行解析
async def cookie2user(cookie_str):
    """
    Parse cookie and load user if cookie is valid.
    """
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        # 如果当前时间大于cookie的过期时间，就直接返回None
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '********'
        return user
    except Exception as e:
        logging.exception(e)
        return None


# 请求对象request的处理工序流水线先后依次是：
#     logger_factory->response_factory->RequestHandler().__call__->get或post->handler
# 对应的响应对象response的处理工序流水线先后依次是:
# 由handler构造出要返回的具体对象
# 然后在这个返回的对象上加上'__method__'和'__route__'属性，以标识别这个对象并使接下来的程序容易处理
# RequestHandler目的就是从请求对象request的请求content中获取必要的参数，调用URL处理函数,然后把结果返回给response_factory
# response_factory在拿到经过处理后的对象，经过一系列类型判断，构造出正确web.Response对象，以正确的方式返回给客户端
# 在这个过程中，只关心handler的处理，其他的都走统一通道，如果需要差异化处理，就在通道中选择适合的地方添加处理代码。
# 注：在response_factory中应用了jinja2来渲染模板文件
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # 使用模板对网页进行渲染
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default,默认是纯文本文件:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

# 用于显示时间戳参数t与当前时间的差值
def datetime_filter(t):
    # 根据参数t获取当前时间与t时间之间的差值，dalta表示的是时间戳
    delta = int(time.time() - t)
    if delta < 60:   # 1分钟为60秒
        return u'1分钟前'
    if delta < 3600:  # 1小时为3600秒
        return u'%s分钟前' % (delta // 60)   # //表示除(取整)
    if delta < 86400:  # 24小时为86400秒
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:   # 24*7小时(即7天)为86400秒
        return u'%s天前' % (delta // 86400)
    # 如果参数t所表示的时间在当前时间的7天之前，则直接根据时间戳t的值来显示时间
    dt = datetime.fromtimestamp(t)    # 将时间戳转化为时间
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


def init__jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        # 自动转义xml/html的特殊字符
        autoescape=kw.get('autoescape', True),
        # 代码块的开始结束标志
        block_start_string=kw.get('block_start_string', '{%'),
        block_end_string=kw.get('block_end_string', '%}'),
        # 变量的开始结束标志
        variable_start_string=kw.get('variable_start_string', '{{'),
        variable_end_string=kw.get('variable_end_string', '}}'),
        # 当模板文件被修改后，下次请求加载该模板文件的时候会自动重新加载修改后的模板文件
        auto_reload=kw.get('auto_reload', True)
    )
    # 获取模板文件的位置
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path : %s' % path)
    # Environment是jinjia2中的一个核心类，它的实例用来保存配置、全局对象以及模板文件的路径
    env = Environment(loader=FileSystemLoader(path), **options)
    # filters: 一个字典描述的filters过滤器集合, 如果非模板被加载的时候, 可以安全的添加或较早的移除.
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    # 所有的一切是为了给app添加__templating__字段
    # 前面将jinja2的环境配置都赋值给env了，这里再把env存入app的dict中，这样app就知道要到哪儿去找模板，怎么解析模板。
    app['__templating__'] = env

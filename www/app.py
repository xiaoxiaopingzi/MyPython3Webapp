# -*- coding: UTF-8 -*-
"""基本架构"""
import logging
import asyncio
from aiohttp import web
try:
    from requestHandler import add_routes, logger_factory, response_factory, auth_factory
    from requestHandler import init__jinja2, add_static, datetime_filter
    import orm, config
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

logging.basicConfig(level=logging.INFO)

async def init(loop):
    kw = config.configs
    print(kw)
    await orm.create_pool(loop=loop, **kw)
    # middlewares(中间件)设置2个中间处理函数(都是装饰器)
    # middlewares中的每个factory接受两个参数，app 和 handler(即middlewares中的下一个handler)
    # 譬如这里logger_factory的handler参数其实就是response_factory
    # middlewares的最后一个元素的handler会通过routes查找到相应的，就是routes注册的对应handler处理函数
    # 这是装饰模式的体现，logger_factory, response_factory都是URL处理函数前（如handler.index）的装饰功能
    app = web.Application(loop=loop, middlewares=[logger_factory, auth_factory, response_factory])
    init__jinja2(app, filters=dict(datetime=datetime_filter))  # 定义时间过滤器
    # 添加URL处理函数
    add_routes(app, 'handlers')
    # 添加CSS等静态文件路径
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 8000)
    logging.info('Server started at http://127.0.0.1:8000')
    return srv

# 获取eventloop
loop = asyncio.get_event_loop()
# 然后加入运行事件
loop.run_until_complete(init(loop))
loop.run_forever()

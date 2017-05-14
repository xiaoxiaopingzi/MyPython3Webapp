# -*- coding: UTF-8 -*-
"""基本架构"""
import logging
import asyncio
import aiomysql
import os, json, time
from datetime import datetime
from aiohttp import web

logging.basicConfig(level=logging.INFO)


async def index(request):
    return web.Response(body=b'<h1>index</h1>', content_type='text/html')


async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 8000)
    logging.info('server started at http://127.0.0.1:8000...')  # 用日志记录
    return srv


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

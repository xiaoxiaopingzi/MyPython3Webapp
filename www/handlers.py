# -*- coding: UTF-8 -*-
"""具体的函数"""
import asyncio

import time

try:
    from requestHandler import get, post
    from models import User, Comment, Blog, next_id
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

# @get('/')
# async def index(request):
#     users = await User.findAll()
#     return {
#         '__template__': 'index.html',
#         'users': users
#     }


@get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time() - 120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time() - 3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time() - 7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs
    }

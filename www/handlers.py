# -*- coding: UTF-8 -*-
"""具体的函数"""
import asyncio
try:
    from requestHandler import get, post
    from models import User, Comment, Blog, next_id
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

@get('/')
async def index(request):
    users = await User.findAll()
    return {
        '__template__': 'index.html',
        'users': users
    }

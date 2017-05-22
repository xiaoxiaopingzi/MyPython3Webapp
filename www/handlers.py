# -*- coding: UTF-8 -*-
"""  """
try:
    from requestHandler import get
    from models import User
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

@get('/')
def index(request):
    users = yield from User.findAll()
    return {
        '__template__': 'index.html',
        'users': users
    }

# -*- coding: UTF-8 -*-
"""数据库的默认配置文件"""

configs = {
    'debug': True,
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': 'root',
        'database': 'mypython3webapp'
    },
    'session': {
        'secret': 'MyBlog'
    }
}
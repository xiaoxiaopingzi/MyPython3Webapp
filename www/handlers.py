# -*- coding: UTF-8 -*-
"""具体的函数"""
import asyncio, re
import time, json
from aiohttp import web, hashlib

try:
    from requestHandler import get, post
    from models import User, Comment, Blog, next_id
    from apis import APIValueError, APIError
    from config import configs
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

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

# 返回一个dict，后续的response这个middleware就可以把结果序列化为JSON并返回
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)

@get('/register')
def register():
    return {
        "__template__": 'register.html'
    }

_RE_EMAIL = re.compile('^[a-z0-9\.\-\_]+@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile('^[0-9a-f]{40}$')  # 对正则表达式进行编译
COOKIE_NAME = 'myblogsession'
_COOKIE_KEY = configs.secret

def user2cookie(user, max_age):
    """
    Generate cookie str by user(id-expires-sha1).
    """
    # build cookie string by: id-expires-sha1
    # 过期时间是创建时间+存活时间
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    # SHA1是一种单向算法，可以通过原始字符串计算出SHA1结果，但无法通过SHA1结果反推出原始字符串。
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


@post('/api/users')
async def api_register_user(*, email, name, passwd):
    # 对客户端传递过来的参数进行校验
    # strip()函数用于出去字符串两端的空格
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')

    # 该邮箱是否已注册
    users = await User.findAll('email=?', [email])  # 根据email条件查找该邮箱是否已经注册
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')

    uid = next_id()
    # 数据库中存储的passwd是经过SHA1计算后的40位Hash字符串，所以服务器端并不知道用户的原始口令。
    sha1_passwd = '%s:%s' % (uid, passwd)  # 利用uid和用户提交的密码混合，作为sha1_passwd
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
                image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    # 将用户保存到数据库中
    await user.save()

    # make session cookie:
    r = web.Response()
    # 86400秒为24小时
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r
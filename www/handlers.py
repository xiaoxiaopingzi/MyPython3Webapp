# -*- coding: UTF-8 -*-
"""具体的函数"""
import asyncio, re, hashlib
import time, json, logging
from aiohttp import web

try:
    from requestHandler import get, post
    from models import User, Comment, Blog, next_id
    from apis import APIValueError, APIError
    from apis import APIPermissionError, Page, APIResourceNotFoundError
    from config import configs
    import markdown2
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')

# --------------------------------------主页---------------------------------------------------
# @get('/')
# async def index(request, *, page='1'):
#     return {
#         # '__template__'指定的模板文件是index.html，其他参数是传递给模板的数据
#         '__template__': 'index.html',
#         'user': request.__user__,
#         "page_index": get_page_index(page)
#     }

@get('/')
async def index(request, *, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    if not num or num == 0:
        logging.info('the type of num is :%s' % type(num))
        blogs = []
    else:
        page = Page(num, page_index)
        # 根据计算出来的offset(取的初始条目index)和limit(取的条数)，来取出条目
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        # '__template__'指定的模板文件是blogs.html，其他参数是传递给模板的数据
        '__template__': 'blogs.html',
        'page': page,
        'user': request.__user__,
        'blogs': blogs
    }


# -----------------------------------------用户模块-------------------------------------------

# 返回一个dict，后续的response这个middleware就可以把结果序列化为JSON并返回
@get('/api/users')
async def api_get_users():
    users = await User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)

# 用户注册页面
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

# 用户注册
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
    # 设置cookie
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '********'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 用户登录
@post('/api/authenticate')
async def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]

    # 在Python 3.x版本中，把'xxx'和u'xxx'统一成Unicode编码，即写不写前缀u都是一样的，
    # 而以字节形式表示的字符串则必须加上b前缀：b'xxx'。
    # sha1 = hashlib.sha1()
    # sha1.update(user.id.encode('utf-8'))
    # sha1.update(b':')
    # sha1.update(passwd.encode('utf-8'))

    # 检查密码
    browser_sha1_passwd = '%s:%s' % (user.id, passwd)
    browser_sha1 = hashlib.sha1(browser_sha1_passwd.encode('utf-8'))
    if user.passwd != browser_sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password')

    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "********"
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 用户登录页面
@get('/signin')
def signin():
    return {
        "__template__": 'signin.html'
    }

# 用户退出
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    # 清理掉cookie来退出账户
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r


# ---------------------------------博客模块需要用到的帮助类----------------------------------
def check_admin(request):
    # 判断用户是否登录并且登录的用户是否有发表博客的权限,user对象的admin属性是一个布尔值
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

# 将表示数字的字符串转化为整形
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

# 将文本中的特殊字符&、<、>转义，以便HTML在解析时能正确解析出原来的符号
def text2html(text):
    # HTML转义字符
    # "     &quot;
    # &     &amp;
    # <     &lt;
    # >     &gt;
    # 不断开空格 &nbsp;
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


# -----------------------------------------博客模块------------------------------------------------
# 添加新博文的页面
@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__': 'manage_blog_edit.html',
        'user': request.__user__,  # 这里要返回去，用于显示当前登录的用户
        'id': '',
        'action': '/api/blogs'  # 对应HTML页面中Vue的action名字
    }

# 注意：当添加博文的页面将博文的数据通过request对象带过来的时候，因为添加博文的页面中通过javascript语句
# location.assign('/manage/blogs')设定了需要跳转的页面,所以会跳转到此语句指定的页面
# 将用户添加的新博文添加到数据库中
@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

# 删除某一条博文，因为在manage_blogs.html页面中设置了删除某一条博文后会自动刷新当前页面，所以
# 在删除某一条博文后会重新装载manage_blogs.html页面
@post('/api/blogs/delete/{id}')
async def api_delete_blog(id, request):
    logging.info('删除博客的ID为：%s' % id)
    check_admin(request)  # 有管理权限才能删除
    b = await Blog.find(id)
    if b is None:
        raise APIResourceNotFoundError('Blog')
    await b.remove()
    return dict(id=id)


# 修改博文的页面
@get('/manage/blogs/modify/{id}')
def manage_modify_blog(id, request):
    return {
        '__template__': 'manage_blog_modify.html',
        'id': id,
        'user': request.__user__,
        'action': '/api/blogs/modify'
    }

# 将修改后的博文保存到数据库中
@post('/api/blogs/modify')
async def api_modify_blog(request, *, id, name, summary, content):
    logging.info('修改的博客的ID为：%s' % id)

    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')

    blog = await Blog.find(id)
    blog.name = name
    blog.summary = summary
    blog.content = content

    await blog.update()
    return blog

# 具体查看某一条博文
@get('/blog/{id}')
async def get_blog(id, request):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
        # 利用markdown2.py文件将普通的文本博客转化成使用Markdown语法的文件，以便展示成HTML文件
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        "blog": blog,
        "user": request.__user__,
        '__user__': request.__user__,
        'comments': comments
    }


# 管理博文的页面
@get('/manage/blogs')
def manage_blogs(request, *, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'user': request.__user__,
        'page_index': get_page_index(page)
    }

# ----------------------利用api来获取博文的数据-----------------------------------------
# 使用api来获取某一条具体的博文
@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog

# 使用api来获取分页的博文数据
@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    blogs_count = await Blog.findNumber('count(id)')
    p = Page(blogs_count, page_index)
    if blogs_count == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

# ----------------------------------------评论模块-----------------------------------------
# 直接跳到到/manage/comments函数进行处理
@get('/manage/')
async def manage():
    return 'redirect:/manage/comments'

# 评论管理页面
@get('/manage/comments')
async def manage_commets(request, *, page='1'):
    return {
        '__template__': 'manage_comments.html',
        'user': request.__user__,
        'page_index': get_page_index(page)
    }

# 将用户新建的评论保存到数据库中
# 用户在blog.html文件中新建评论,并且在该文件的javascript中设置了提交完毕后重新加载当前页面
@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('content')
    if not content or not content.strip():
        raise APIValueError('content')
    # 首先找到这条评论所属的博文
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name,
                      user_image=user.image, content=content.strip())
    await comment.save()  # 将评论保存到数据库中
    return comment

# 删除某条评论
@post('/api/comments/delete/{id}')
async def api_delete_comments(id, request):
    logging.info(id)
    check_admin(request)
    comment = await Comment.find(id)
    if comment is None:
        raise APIResourceNotFoundError('comment')
    await comment.remove()
    return dict(id=id)

# ----------------------利用api来获取分页的评论数据-----------------------------------------
@get('/api/comments')
async def api_comments(*, page='1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, comments=())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, comments=comments)


# -----------------------------------------用户管理模块----------------------------------------------
# 显示所有用户的页面
@get('/show_all_users')
async def show_all_users():
    users = await User.findAll(orderBy='created_at desc')
    logging.info('to index...')
    return {
        '__template__': 'all_users.html',
        'users:': users
    }

# 用户管理页面
@get('/manage/users')
def manage_users(request, *, page='1'):
    return {
        '__template__': 'manage_users.html',
        'user': request.__user__,
        'page_index': get_page_index(page)
    }


# ----------------------利用api来获取用户的数据-----------------------------------------
@get('/api/users')
async def api_get_users(*, page='1'):
    page_index = get_page_index(page)
    # count为MySQL中的聚集函数，用于计算某列的行数
    # user_count代表了有多个用户id
    user_count = await User.findNumber('count(id)')
    p = Page(user_count, page_index)
    # 通过Page类来计算当前页的相关信息, 其实是数据库limit语句中的offset，limit
    if user_count == 0:
        return dict(page=p, users=())
    # page.offset表示从那一行开始检索，page.limit表示检索多少行
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))

    for u in users:
        u.passwd = '*******'
    return dict(page=p, users=users)



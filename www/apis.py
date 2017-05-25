# -*- coding: UTF-8 -*-
try:
    from config import configs
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')
"""
JSON API definition.
"""

class Page(object):
    """
    Page object for display pages.
    """
    def __init__(self, item_count, page_index=1):
        """
        Init pagination by item_count, page_index and page_size
        """
        # startIndex 页码数组的开始索引
        # endIndex   页码数组的结束索引
        # pageArray  页码数组
        # page_index 待查看那一页
        # item_count 文章的总数
        # page_size 每页显示的文章数量
        # page_count 需要多少页才能所有的将文章全部显示出来
        self.item_count = item_count
        self.page_size = configs.page_size  # 从配置文件中读取page_size
        # 1 if item_count % page_size > 0 else 0表示如果item_count % page_size > 0则返回1，否则返回0
        self.page_count = item_count // configs.page_size + (1 if item_count % configs.page_size > 0 else 0)
        if (item_count == 0) or (page_index > self.page_count):
            self.offset = 0
            self.limit = 0
            self.page_index = 1
        else:
            # page_index 表明当前需要查看那一页
            self.page_index = page_index
            # offset表示sql的查询语句中的开始索引号
            self.offset = self.page_size * (page_index - 1)
            # limit表示sql查询语句中每次查询的记录数
            self.limit = self.page_size

            # 生成页码数组
            if self.page_count <= 10:
                self.startIndex = 1
                self.endIndex = self.page_count
            else:
                self.startIndex = page_index - 4
                self.endIndex = page_index + 5
                # 当前面不足4个页码时，就显示前10页
                if self.startIndex < 1:
                    self.startIndex = 1
                    self.endIndex = 10
                # 当后面不足5个页码时，就显示后10页
                if self.endIndex > self.page_count:
                    self.startIndex = self.page_count - 10 + 1
                    self.endIndex = self.page_count

            # 根据self.startIndex和self.endIndex生成索引数组
            # range函数中，当传入两个参数时，则将第一个参数做为起始位，第二个参数为结束位
            self.pageArray = [n for n in range(self.startIndex, self.endIndex + 1)]

        # 如果当前查看的那一页小于总页数，就说明有下一页
        self.has_next = self.page_index < self.page_count
        # 如果当前页大于1，就说明有上一页
        self.has_previous = self.page_index > 1



    def __str__(self):
        return 'item_count: %s, page_count: %s, page_index: %s, page_size: %s, offset:%s, limit:%s' \
                % (self.item_count, self.page_count, self.page_index, self.page_size, self.offset, self.limit)

    __repr__ = __str__



# 我们需要对Error进行处理，因此定义一个APIError，这种Error是指API调用时发生了逻辑错误（比如用户不存在），
# 其他的Error视为Bug，返回的错误代码为internalerror
class APIError(Exception):
    """
    the base APIError which contains error(required), data(optional) and message(optional).
    """
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    """
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    """
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIResourceNotFoundError(APIError):
    """
    Indicate the resource was not found. The data specifies the resource name.
    """
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)

class APIPermissionError(APIError):
    """
    Indicate the api has no permission.
    """
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)

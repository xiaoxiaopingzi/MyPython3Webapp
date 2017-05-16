# -*- coding: UTF-8 -*-
"""读取配置文件，将配置信息保存到configs中"""
# 导入两个配置文件
try:
    import config_default
    import config_override
except ImportError:
    raise ImportError('The file is not found. Please check the file name!')


class Dict(dict):
    """
    simple but support access as x.y style.
    """

    def __init__(self, names=(), values=(), **kw):
        super(Dict, self).__init__(**kw)  # 首先调用父类Dict的构造方法
        # 内建函数zip，迭代names和values,将迭代出来的单个name和value组成一个tuple-->(name,value)，
        # 并最终得到一个list. zip([1,2,3], [4,5,6])-->[(1, 4), (2, 5), (3, 6)]
        for k, v in zip(names, values):  # 根据传入的参数进行初始化
            self[k] = v

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute like '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value


# 用override中的值覆盖defaults中对应的值,使用递归来实现覆盖
# defaults, override都是dict，并且这两个参数中的参数也可能是dict，所以需呀递归
def merge(defaults, override):
    r = {}
    for k, v in defaults.items():
        if k in override:
            if isinstance(v, dict):  # 如果v是dict，则需要递归
                r[k] = merge(v, override[k])
            else:
                r[k] = override[k]
        else:
            r[k] = v
    return r

# 增加x.y的取值功能
def toDict(d):  # d是dict
    D = Dict()
    for k, v in d.items():
        # 下面的一条语句相当于以下的if-else语句
        # if isinstance(v, dict):
        #     D[k] = toDict(v)
        # else:
        #     D[k]  = v
        D[k] = toDict(v) if isinstance(v, dict) else v
    return D

configs = config_default.configs   # config_default.configs是取config_default.py文件的config变量
configs = merge(configs, config_override.configs)
# 通过toDict()方法来得到x.y的取值功能
configs = toDict(configs)


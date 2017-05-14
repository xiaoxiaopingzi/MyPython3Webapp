# -*- coding: UTF-8 -*-
"""用于代码编写过程中的额一些测试"""

def sf():
    pass

a = 1
print('变量a的类型是:%s' % type(a))
print(type(type(a)))
print('函数sf的类型是:%s' % type(sf))
print(type(type(sf)))

if None:
    print('none')
if not None:
    print('not None')

L = ['name', 'age', 'score']
print(list(map(lambda f: '`%s`' % f, L)))
print(', '.join(L))
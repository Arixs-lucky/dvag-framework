import re

def get_content(s, begin_str='[BEGIN]', end_str='[END]'):
    """
    从字符串中提取指定标记之间的内容
    参数:
        s (str): 要处理的原始字符串
        begin_str (str): 起始标记，默认为'[BEGIN]'
        end_str (str): 结束标记，默认为'[END]'
    返回:
        str: 提取到的内容字符串，如果未找到标记则返回空字符串
    """
    # 查找起始标记的位置
    _begin = s.find(begin_str)
    # 查找结束标记的位置
    _end = s.find(end_str)
    # 如果任一标记未找到，返回空字符串
    if _begin == -1 or _end == -1:
        return ''
    else:
        # 返回两个标记之间的内容，并去除首尾空白字符
        return s[_begin + len(begin_str):_end].strip()

def get_content_list(s, begin_str='[BEGIN]', end_str='[END]'):

    """
    从字符串中提取所有在指定开始和结束标记之间的内容，并去除重复项

    参数:
        s (str): 要处理的源字符串
        begin_str (str): 开始标记，默认为'[BEGIN]'
        end_str (str): 结束标记，默认为'[END]'

    返回:
        list: 包含所有提取的唯一内容的列表
    """
    result = []  # 用于存储所有找到的内容
    # 查找开始标记的位置
    _begin = s.find(begin_str)
    # 如果找到开始标记，则查找对应的结束标记位置
    if _begin>=0:
        # 在开始标记之后查找结束标记，并计算绝对位置
        _end = s[_begin + len(begin_str):].find(end_str) + _begin + len(begin_str)
    else:
        # 如果没有找到开始标记，直接查找结束标记
        _end = s.find(end_str)
    # 循环查找所有标记对之间的内容
    while not (_begin == -1 or _end == -1):
        # 提取开始和结束标记之间的内容，并去除首尾空格
        result.append(s[_begin + len(begin_str):_end].strip())
        # 将源字符串更新为结束标记之后的内容
        s = s[_end + len(end_str):]
        # 重新查找开始和结束标记的位置
        _begin = s.find(begin_str)
        _end = s.find(end_str)
    # 去除重复项，保持原始顺序
    unique_result = []
    for item in result:
        if item not in unique_result:
            unique_result.append(item)
    return unique_result


def string_to_function(string):
    """
    将字符串形式的函数定义转换为可调用的函数对象
    参数:
        string (str): 包含函数定义的字符串，例如 "def add(a, b): return a + b"
    返回:
        function: 通过字符串定义的函数对象
    注意:
        此函数使用exec()执行字符串中的代码，并从全局命名空间中获取对应的函数对象
    """
    # 执行字符串中的函数定义代码，将其添加到全局命名空间
    exec(string, globals())
    return globals()[string.split(' ')[1].split('(')[0]]

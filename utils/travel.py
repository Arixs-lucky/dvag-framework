import json

import requests
from utils.config_manager import ConfigManager
import ast
import re

config_manager = ConfigManager()


def action(action_str):
    """
    执行传入的字符串形式的Python代码，并返回执行结果
    参数:
        action_str (str): 要执行的Python代码字符串
    返回:
        执行结果，如果执行出错则返回错误信息字符串
    """
    try:
        print(f'action={action_str}')  # 打印当前要执行的代码
        result = eval(action_str)     # 使用eval函数执行字符串形式的代码
        return result                # 返回执行结果
    except Exception as e:            # 捕获所有可能的异常
        return f"An error occurred: {e}"  # 返回错误信息


def query_database(query: list):
    """
    数据库查询函数，用于执行数据库查询并返回结果
    参数:
        query (list): 包含查询语句的列表
    返回:
        str: JSON格式的查询结果字符串
    """
    # 清除代理配置
    config_manager.clear_proxies()
    try:
        # 发送POST请求到数据库工具接口
        response = requests.post(
            "http://localhost:8079/tools/database",
            json={'queries': query}
        )
        # 将响应转换为JSON格式
        response = response.json()
        # 如果响应结果不为空，取第一个结果
        if len(response) > 0:
            response = response[0]
    except Exception as e:
        response = {'result': f'error', 'error': f'run error{e}'}
        print(response)
    config_manager.apply_proxies()
    return json.dumps(response)
    # return re.sub(r'\\n', '\n', str(response))



def execute_sql(statement: str):

    """
    执行SQL语句的函数

    参数:
        statement (str): 需要执行的SQL语句字符串

    返回:
        查询数据库的结果，通过调用query_database函数实现
    """
    return query_database([statement])  # 将SQL语句作为列表元素传递给query_database函数


def execute_python(code: str):
    """
    执行Python代码并返回结果的函数
    参数:
        code (str): 需要执行的Python代码字符串
    返回:
        str: 执行结果的JSON格式字符串
    """
    # 清除代理配置
    config_manager.clear_proxies()
    # 向本地服务器发送POST请求执行Python代码
    response = requests.post(
        'http://127.0.0.1:8079/tools/python',
        json={'code': code}
    )
    # 应用代理配置
    config_manager.apply_proxies()
    # 获取响应结果并转换为JSON格式
    result=response.json()
    return json.dumps(result)
    # 注释掉的代码：返回字符串格式的结果
    # return str(result)


def is_error(observation: str) -> bool:
    """
    检查给定的观察结果是否包含错误信息
    参数:
        observation (str): 需要检查的观察结果字符串，应为JSON格式
    返回:
        bool: 如果观察结果中包含非空错误信息则返回True，否则返回False
    异常处理:
        当输入的observation不是有效的JSON格式时，捕获JSONDecodeError异常并返回False
    """
    try:
        # 尝试将输入的字符串解析为JSON对象
        obs_json = json.loads(observation)
        # 检查JSON对象中是否存在'error'键，且其值不为空
        return 'error' in obs_json and obs_json['error'] != ""
    except json.JSONDecodeError:
        return False

import re
from datetime import datetime

def check_plan_format(input_str):
    matches = re.findall(r'<plan>(\w+)\((.*?)\)</plan>', input_str)
    if not matches:
        return "No valid plan format found. Surround the plan in <plan> and </plan>"

    format_requirements = {
        'stay_in': ['str', 'time', 'time'],
        'visit': ['str', 'time', 'time'],
        'go_to_place': ['str', 'str', 'time', 'time'],
        'go_to_city': ['str', 'str', 'time', 'time', 'str']
    }

    errors = []

    if len(matches) == 0:
        return "Please provide a plan surrounded by <plan> and </plan> in the specified format."

    for method_name, params_str in matches:
        params = params_str.split(',')

        if method_name not in format_requirements:
            err_msg = f"Illegal plan: {method_name}."
            if err_msg not in errors:
                errors.append(err_msg)
            continue

        if len(params) != len(format_requirements[method_name]):
            err_msg = f"Incorrect number of parameters for {method_name}."
            if err_msg not in errors:
                errors.append(err_msg)
            continue

        for i, param in enumerate(params):
            param = param.strip()
            expected_format = format_requirements[method_name][i]

            if expected_format == 'str' and param.count('"') != 2:
                err_msg = f'Error in {method_name}: {param} should be surrounded by double quotes.'
                if err_msg not in errors:
                    errors.append(f'Error in {method_name}: {param} should be surrounded by double quotes.')

            if expected_format == 'time':
                try:
                    time_value = param.split('"')[1]
                    datetime.strptime(time_value, "%Y-%m-%d %H:%M")
                except (ValueError, IndexError):
                    err_msg = f'Error in {method_name}: {param} should be formatted as "%Y-%m-%d %H:%M".'
                    if err_msg not in errors:
                        errors.append(err_msg)

    return "\n".join(errors) if errors else "All formats are correct."

import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

router = APIRouter()


# 定义一个名为 SQLRequest 的类，继承自 BaseModel
class SQLRequest(BaseModel):
    # 定义一个名为 queries 的属性，类型为字符串列表(List[str])
    queries: List[str]


def execute_sql(queries: List[str]):
    """
    执行多个SQL查询并返回结果
    参数:
        queries (List[str]): SQL查询语句列表
    返回:
        List[Dict]: 包含每个查询结果的字典列表，每个字典包含:
            - query: 执行的SQL查询语句
            - result: 查询结果(如果有错误则为空字符串)
            - error: 错误信息(如果没有错误则为空字符串)
    """
    # 创建到SQLite数据库的连接
    conn = sqlite3.connect('./database/travel.db')
    cursor = conn.cursor()

    # 用于存储所有查询结果的列表
    results = []
    # 遍历并执行每个查询
    for query in queries:
        try:
            # 执行单个查询
            cursor.execute(query)
            # 将查询结果添加到结果列表中
            results.append({
                "query": query,
                "result": cursor.fetchall(),
                "error": ""
            })
        except Exception as e:
            # 如果查询出错，捕获异常并添加错误信息
            results.append({
                "query": query,
                "result": "",
                "error": str(e)
            })

    # Commit changes and close the connection to the database
    conn.commit()
    conn.close()

    return results


# 导入路由装饰器，用于定义POST请求路径
@router.post("/tools/database")
# 定义异步函数execute_sqlite，处理对/tools/database的POST请求
# 参数req为SQLRequest类型，包含SQL查询请求信息
async def execute_sqlite(req: SQLRequest):
    # 打印当前时间戳和接收到的请求信息，用于日志记录
    print(f"{datetime.datetime.now()}:{req}")
    # 调用execute_sql函数执行请求中的SQL查询，并返回结果
    return execute_sql(req.queries)

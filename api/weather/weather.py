# api/weather/weather.py
from fastapi import APIRouter, HTTPException, Query
import sqlite3

router = APIRouter()

# 路由装饰器，定义GET请求路径为/weather/query
@router.get("/weather/query")
def query_weather(date: str, city: str):
    try:
        # 连接到SQLite数据库，数据库文件为weather.db
        conn = sqlite3.connect('./database/weather.db')
        # 创建游标对象
        c = conn.cursor()
        # 执行SQL查询，获取指定城市和日期的天气数据
        c.execute("SELECT max_temp, min_temp, weather FROM weather WHERE city=? AND date=?", (city, date))
        # 获取查询结果的第一行
        row = c.fetchone()
        # 关闭数据库连接
        conn.close()

        # 如果查询结果存在
        if row:
            # 格式化查询结果为字符串
            result=f'{date}, {city}: {row[2]}, {row[1]}-{row[0]} ℃'
            # 返回成功结果和错误信息(无错误)
            return {"result": str(result), "error": None}
        else:
            # 如果查询结果不存在，返回空结果和错误信息
            {"result": '', "error": 'data not found'}

    # 异常处理
    except Exception as e:
        # 打印异常信息
        print(e)
        # 返回空结果和错误信息
        return {"result": '', "error": 'not found'}

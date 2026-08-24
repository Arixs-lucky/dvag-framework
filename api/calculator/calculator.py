from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from simpleeval import simple_eval, SimpleEval

router = APIRouter()

class Expression(BaseModel):

    """
    表达式模型类，用于表示一个表达式对象

    继承自BaseModel，通常用于数据验证和序列化
    """
    expression: str  # 表达式字符串，存储具体的表达式内容


# 导入路由装饰器，用于定义API端点
@router.post("/tools/calculator")
def evaluate(expression: Expression):
    try:
        # 创建SimpleEval实例，用于表达式求值
        s = SimpleEval()
        # 使用SimpleEval计算表达式的值
        result = s.eval(expression.expression)
        # 返回计算结果和错误信息（如果有）
        return {"result": str(result), "error": None}
    except Exception as e:
        # 如果发生异常，返回错误信息
        return {"result": None, "error": str(e)}

from fastapi import APIRouter
from pydantic import BaseModel
import subprocess

router = APIRouter()

class ShellCommandModel(BaseModel):

    """
    Shell命令模型类，用于表示和验证Shell命令的结构。
    继承自BaseModel，通常用于数据验证和序列化。
    """
    command: str  # 定义一个名为command的字符串类型字段，用于存储Shell命令

class ShellCommandResultModel(BaseModel):

    """
    Shell命令执行结果的数据模型类
    用于封装Shell命令执行后的输出结果，包括标准输出和错误输出
    """
    stdout: str  # 标准输出内容，存储命令执行成功时的输出信息
    stderr: str  # 标准错误输出内容，存储命令执行失败时的错误信息

# 导入路由装饰器和响应模型
@router.post("/tools/shell", response_model=ShellCommandResultModel)
async def execute_shell_command(command: ShellCommandModel):
    result = subprocess.run(command.command, capture_output=True, shell=True, text=True)
    return ShellCommandResultModel(stdout=result.stdout, stderr=result.stderr)

import ast
import os
import asyncio
import subprocess

import astor
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


# 定义一个名为Item的类，继承自BaseModel
class Item(BaseModel):
    # 定义一个名为code的属性，类型为字符串(str)
    code: str


def modify_code_to_print_last_expr(code: str):
    # Parse the code using AST
    tree = ast.parse(code, mode='exec')

    # Check if the last node is an expression and not a print statement
    last_node = tree.body[-1]
    if isinstance(last_node, ast.Expr) and not (
            isinstance(last_node.value, ast.Call) and getattr(last_node.value.func, 'id', None) == 'print'):
        # Create a new print node
        print_node = ast.Expr(
            value=ast.Call(func=ast.Name(id='print', ctx=ast.Load()), args=[last_node.value], keywords=[]))
        # Copy line number and column offset from the last expression
        print_node.lineno = last_node.lineno
        print_node.col_offset = last_node.col_offset
        # Replace the last expression with the print statement
        tree.body[-1] = print_node

    # Use astor to convert the modified AST back to source code
    modified_code = astor.to_source(tree)
    return modified_code


async def run_code(code: str):

    """
    异步执行给定的Python代码，并返回执行结果或错误信息
    参数:
        code (str): 要执行的Python代码字符串
    返回:
        dict: 包含执行结果和错误信息的字典，格式为:
            {
                "result": str,  # 代码执行结果
                "error": str    # 执行过程中的错误信息
            }
    """
    try:
        # 修改代码以打印最后一个表达式
        code = modify_code_to_print_last_expr(code)
        # Write the code to a file
        with open("code.py", "w") as f:
            f.write(code)
        with open("code_temp.py", "w") as f:
            f.write(code)
        # Run the file with a timeout of 3 seconds
        process = await asyncio.create_subprocess_shell(
            "python code.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=3)

        # Decode the stdout and stderr
        result = stdout.decode("utf-8")
        error = stderr.decode("utf-8")

        return {"result": result, "error": error}
    except asyncio.TimeoutError:
        process.terminate()
        await process.wait()
        return {"result": "", "error": "Code execution timed out"}
    except Exception as e:
        return {"result": "", "error": str(e)}
    finally:
        # Delete the code file
        if os.path.exists("code.py"):
            os.remove("code.py")


@router.post("/tools/python")
async def execute_python(item: Item):
    result = await run_code(item.code)
    return result

# import io
# import traceback
# from contextlib import redirect_stdout
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from concurrent.futures import ThreadPoolExecutor, TimeoutError
#
# router = APIRouter()
#
# executor = ThreadPoolExecutor(max_workers=1)
#
# class Item(BaseModel):
#     code: str
#
# def execute_code(code):
#     f = io.StringIO()
#     with redirect_stdout(f):
#         try:
#             exec(code)
#             return {"result": f.getvalue(), "error": None}
#         except Exception as e:
#             return {"result": f.getvalue(), "error": traceback.format_exc().split('exec(code)\n  ')[-1]}
#
# @router.post("/tools/python")
# async def execute_python(item: Item):
#     future = executor.submit(execute_code, item.code)
#     try:
#         result = future.result(timeout=3)  # Wait for the result or timeout after 3 seconds
#     except TimeoutError:
#         return {"result": None, "error": "TimeoutError"}
#     return result

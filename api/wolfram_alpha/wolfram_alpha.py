from fastapi import APIRouter
import wolframalpha
from pydantic import BaseModel
from typing import Optional

class QueryItem(BaseModel):

    """
    查询项模型类，继承自BaseModel

    用于表示一个查询请求的数据结构，包含一个查询字符串字段
    """
    query: str  # 查询内容，字符串类型

router = APIRouter()

app_id = "XRY28U-7PVE2LRH7H"  # Replace with your app id
client = wolframalpha.Client(app_id)

@router.post("/tools/wolframalpha")
async def wolframalpha_query(item: QueryItem):
    res = client.query(item.query)

    # Handle the query result
    if res['@success'] == 'false':
        return {"result": "Query failed"}
    else:
        # Return the first result text
        result = next(res.results).text
        return {"result": result}
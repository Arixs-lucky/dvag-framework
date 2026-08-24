from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from .bing_api import BingAPI

router = APIRouter()

bing_api = BingAPI('885e62a126554fb390af88ae31d2c8ff')

class QueryItem(BaseModel):

    """
    查询项模型类，用于定义查询数据的基本结构
    继承自BaseModel，提供数据验证和序列化功能
    """
    query: str  # 查询内容，字符串类型

class PageItem(BaseModel):

    # 定义一个继承自BaseModel的PageItem类
    url: str  # 定义一个名为url的字符串类型字段

# 路由装饰器，定义GET请求路径为"/tools/bing/search"
@router.get("/tools/bing/search")
# 异步函数定义，接受QueryItem类型的参数item
async def bing_search(item: QueryItem):
    try:
        # 调用bing_api的search方法，使用item.query作为搜索关键词
        search_results = bing_api.search(item.query)
    # 捕获运行时异常，并转换为HTTP状态码500的错误响应
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    # 返回搜索结果
    return search_results

# 路由定义，处理GET请求，路径为"/tools/bing/load_page"
@router.get("/tools/bing/load_page")
# 异步函数定义，接收PageItem类型的参数item
async def load_page(item: PageItem):
    try:
        # 尝试调用bing_api的load_page方法，传入item.url参数
        # page_loaded表示页面是否成功加载，page_detail包含页面内容或错误信息
        page_loaded, page_detail = bing_api.load_page(item.url)
    # 捕获运行时错误，并抛出HTTP异常，状态码为500，错误信息为异常的详细描述
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    # 检查页面是否成功加载，如果未成功则抛出HTTP异常
    if not page_loaded:
        raise HTTPException(status_code=500, detail=page_detail)
    # 返回包含页面内容的JSON响应
    return {"page_content": page_detail}
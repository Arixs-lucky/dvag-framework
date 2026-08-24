from fastapi import APIRouter
from pydantic import BaseModel
import arxiv

router = APIRouter()


class ArxivQuery(BaseModel):

    """
    ArxivQuery类，用于表示ArXiv查询的模型

    继承自BaseModel，这是一个数据模型类，用于定义查询参数的结构
    """
    query: str  # 查询字符串，用于ArXiv搜索的关键词或查询条件


top_k_results: int = 3
ARXIV_MAX_QUERY_LENGTH = 300
doc_content_chars_max: int = 4000


@router.get("/tools/arxiv")
async def get_arxiv_article_information(item: ArxivQuery):
    '''Run Arxiv search and get the article meta information.
    '''
    try:
        results = arxiv.Search(  # type: ignore
            item.query[: ARXIV_MAX_QUERY_LENGTH], max_results=top_k_results
        ).results()
    except Exception as ex:
        return {"result": None, "error": f"Arxiv exception: {ex}"}

    docs = [
        f"Published: {result.updated.date()}\nTitle: {result.title}\n"
        f"Authors: {', '.join(a.name for a in result.authors)}\n"
        f"Summary: {result.summary}"
        for result in results
    ]
    if docs:
        return {"result": "\n\n".join(docs)[: doc_content_chars_max], "error": None}
    else:
        return {"result": None, "error": "No good Arxiv Result was found"}
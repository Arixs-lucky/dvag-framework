import random

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional, Union
from .chemical_prop_api import ChemicalPropAPI

router = APIRouter()


class GetNameResponse(BaseModel):
    """name list"""
    names: List[str]


class GetStructureResponse(BaseModel):
    """structure list"""
    state: int
    content: Optional[str] = None


class GetIDResponse(BaseModel):

    """
    获取ID响应模型类，用于定义获取ID接口的返回数据结构

    Attributes:
        state (int): 状态码，表示请求的处理结果状态
        content (Union[str, List[str]]): 响应内容，可以是字符串或字符串列表，根据实际返回数据类型决定
    """
    state: int  # 状态码，标识请求处理状态
    content: Union[str, List[str]]  # 响应内容，可能为单个字符串或字符串列表


chemical_prop_api = ChemicalPropAPI


# 导入路由装饰器和响应模型
@router.get("/tools/chemical/get_name", response_model=GetNameResponse)
def get_name(cid: str):
    """prints the possible 3 synonyms of the queried compound ID"""
    ans = chemical_prop_api.get_name_by_cid(cid, top_k=3)
    return {
        "names": ans
    }


@router.get("/tools/chemical/get_allname", response_model=GetNameResponse)
def get_allname(cid: str):
    """prints all the possible synonyms (might be too many, use this function carefully).
    """
    ans = chemical_prop_api.get_name_by_cid(cid)
    return {
        "names": ans
    }


@router.get("/tools/chemical/get_id_by_struct", response_model=GetIDResponse)
def get_id_by_struct(smiles: str):
    """prints the ID of the queried compound SMILES. This should only be used if smiles is provided or retrieved in the previous step. The input should not be a string, but a SMILES formula.
    """
    cids = chemical_prop_api.get_cid_by_struct(smiles)
    if len(cids) == 0:
        return {
            "state": "no result"
        }
    else:
        return {
            "state": "matched",
            "content": cids[0]
        }


@router.get("/tools/chemical/get_id", response_model=GetIDResponse)
def get_id(name: str):
    """prints the ID of the queried compound name, and prints the possible 5 names if the queried name can not been precisely matched,
    """
    cids = chemical_prop_api.get_cid_by_name(name)
    if len(cids) > 0:
        return {
            "state": "precise",
            "content": cids[0]
        }

    cids = chemical_prop_api.get_cid_by_name(name, name_type="word")
    if len(cids) > 0:
        if name in get_name(cids[0]):
            return {
                "state": "precise",
                "content": cids[0]
            }

    ans = []
    random.shuffle(cids)
    for cid in cids[:5]:
        nms = get_name(cid)
        ans.append(nms)
    return {
        "state": "not precise",
        "content": ans
    }


# 导入路由装饰器，用于定义API端点
@router.get("/tools/chemical/get_prop")
def get_prop(cid: str):
    """prints the properties of the queried compound ID
    化合物属性查询函数，根据提供的化合物ID查询并返回其属性信息
    参数:
        cid (str): 化合物ID，用于标识特定的化学物质
    返回:
        返回查询到的化合物属性信息
    """
    # 调用chemical_prop_api模块中的get_prop_by_cid函数，传入化合物ID参数cid
    return chemical_prop_api.get_prop_by_cid(cid)

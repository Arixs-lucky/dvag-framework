import json
from typing import Optional, List

import requests
from bs4 import BeautifulSoup


class ChemicalPropAPI:
    def __init__(self) -> None:
        """
        初始化ChemicalPropAPI类，设置PubChem API的端点URL
        """
        self._endpoint = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/"

    def get_name_by_cid(self, cid: str, top_k: Optional[int] = None) -> List[str]:
        """
        根据化合物ID(CID)获取化合物的名称列表
        参数:
            cid: 化合物的CID标识符
            top_k: 返回前top_k个名称，如果为None则返回所有名称
        返回:
            化合物名称的列表
        """
        html_doc = requests.get(f"{self._endpoint}cid/{cid}/synonyms/XML").text
        soup = BeautifulSoup(html_doc, "html.parser", from_encoding="utf-8")
        syns = soup.find_all('synonym')
        ans = []
        if top_k is None:
            top_k = len(syns)
        for syn in syns[:top_k]:
            ans.append(syn.text)
        return ans

    def get_cid_by_struct(self, smiles: str) -> List[str]:
        """
        根据SMILES字符串获取化合物的CID列表
        参数:
            smiles: 化合物的SMILES表示
        返回:
            化合物CID的列表
        """
        html_doc = requests.get(f"{self._endpoint}smiles/{smiles}/cids/XML").text
        soup = BeautifulSoup(html_doc, "html.parser", from_encoding="utf-8")
        cids = soup.find_all('cid')
        if cids is None:
            return []
        ans = []
        for cid in cids:
            ans.append(cid.text)
        return ans

    def get_cid_by_name(self, name: str, name_type: Optional[str] = None) -> List[str]:
        """
        根据化合物名称获取CID列表
        参数:
            name: 化合物名称
            name_type: 名称类型(可选)，如"common"或"systematic"
        返回:
            化合物CID的列表
        """
        url = f"{self._endpoint}name/{name}/cids/XML"
        if name_type is not None:
            url += f"?name_type={name_type}"
        html_doc = requests.get(url).text
        soup = BeautifulSoup(html_doc, "html.parser", from_encoding="utf-8")
        cids = soup.find_all('cid')
        if cids is None:
            return []
        ans = []
        for cid in cids:
            ans.append(cid.text)
        return ans

    def get_prop_by_cid(self, cid: str) -> str:
        html_doc = requests.get(
            f"{self._endpoint}cid/{cid}/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,IUPACName,XLogP,ExactMass,MonoisotopicMass,TPSA,Complexity,Charge,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,HeavyAtomCount,CovalentUnitCount/json").text
        return json.loads(html_doc)['PropertyTable']['Properties'][0]
import requests
from bs4 import BeautifulSoup
from typing import Tuple
from enum import Enum

SEARCH_RESULT_LIST_CHUNK_SIZE = 3
RESULT_TARGET_PAGE_PER_TEXT_COUNT = 500


class BingAPI:
    def __init__(self, subscription_key: str) -> None:
        """
        初始化BingAPI类，设置必要的请求头和API端点
        参数:
            subscription_key (str): Bing搜索API的订阅密钥
        """
        self._headers = {
            'Ocp-Apim-Subscription-Key': subscription_key  # 设置API请求头，包含订阅密钥
        }
        self._endpoint = "https://api.bing.microsoft.com/v7.0/search"  # Bing搜索API的端点URL
        self._mkt = 'en-US'  # 设置市场参数为美国英语

    def search(self, key_words: str, max_retry: int = 3):

        """
        使用Bing搜索API进行搜索

        参数:
            key_words (str): 搜索关键词
            max_retry (int, optional): 最大重试次数，默认为3

        返回:
            dict: 搜索结果的JSON数据

        异常:
            RuntimeError: 当API访问失败时抛出
        """
        for _ in range(max_retry):  # 尝试最多max_retry次
            try:
                # 发送GET请求到Bing搜索API
                result = requests.get(self._endpoint, headers=self._headers, params={'q': key_words, 'mkt': self._mkt},
                                      timeout=10)
            except Exception:  # 捕获所有异常，继续下一次尝试
                continue
            if result.status_code == 200:  # 如果请求成功
                result = result.json()  # 解析JSON响应
                return result  # 返回搜索结果
            else:
                continue  # 如果请求失败，继续下一次尝试
        raise RuntimeError("Failed to access Bing Search API.")  # 如果所有尝试都失败，抛出异常

    def load_page(self, url: str, max_retry: int = 3) -> Tuple[bool, str]:

        """
        加载指定URL的网页内容并提取文本

        参数:
            url (str): 要加载的网页URL
            max_retry (int, optional): 最大重试次数，默认为3

        返回:
            Tuple[bool, str]: 包含加载状态和文本内容的元组

        异常:
            可能抛出各种异常，但都会被捕获并返回错误信息
        """
        for _ in range(max_retry):  # 尝试最多max_retry次
            try:
                # 发送GET请求获取网页内容
                res = requests.get(url, timeout=15)
                if res.status_code == 200:  # 如果请求成功
                    res.raise_for_status()  # 检查HTTP错误
                else:
                    raise RuntimeError("Failed to load page, code {}".format(res.status_code))  # 如果状态码不是200，抛出异常
            except Exception:  # 捕获所有异常
                res = None
                continue  # 继续下一次尝试
            res.encoding = res.apparent_encoding  # 设置正确的编码
            content = res.text  # 获取网页文本内容
            break  # 成功获取内容，退出循环
        if res is None:  # 如果所有尝试都失败
            return False, "Timeout for loading this page, Please try to load another one or search again."
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(content, 'html.parser')
            # 查找所有段落标签
            paragraphs = soup.find_all('p')
            page_detail = ""
            # 提取所有段落的文本内容
            for p in paragraphs:
                text = p.get_text().strip()
                page_detail += text
            return True, page_detail  # 返回成功状态和提取的文本
        except Exception:  # 如果解析过程中出现异常
            return False, "Timeout for loading this page, Please try to load another one or search again."

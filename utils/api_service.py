import json
import http.client
import ssl
from urllib.parse import urlparse
import os
import time
import numpy as np

# =============================================================================
# TDAG LLM 调用适配层
# 支持两种后端:
#   1. 原版 OpenAI (openai Python SDK) — 通过环境变量 OPENAI_API_KEY
#   2. OpenAI-Compatible 兼容 API（DeepSeek / Qwen / 火山引擎 等国产模型）
#       — 通过环境变量 LLM_BACKEND="openai_compatible"
#       — 配置 LLM_BASE_URL（如火山引擎: https://ark.cn-beijing.volces.com/api/v3）
#       — 配置 LLM_API_KEY
#       — 配置 LLM_MODEL（默认 deepseek-chat）
# =============================================================================

# ============= 第一步：在模块加载时彻底清除系统代理环境变量 =============
# 这是最关键的一步！必须在任何 requests/http 导入之后执行
# 这样可以确保后续所有 HTTP 调用都不会走代理
for key in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
    os.environ.pop(key, None)

# ============= 配置读取函数（延迟加载） =============
def _get_backend():
    return os.getenv("LLM_BACKEND", "openai")

def _get_base_url():
    return os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")

def _get_model():
    return os.getenv("LLM_MODEL", "deepseek-chat")

# ---- HuggingFace 国内镜像配置 ----
os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')


def _get_llm_api_key():
    """动态获取 API Key"""
    global keys, key_idx
    if keys is not None and len(keys) > 0:
        key_idx = (key_idx + 1) % len(keys)
        return keys[key_idx]
    return os.getenv("LLM_API_KEY", "")

key_idx = 0
keys = None
org = os.getenv("OPENAI_ORGANIZATION")


def set_keys(new_keys):
    """设置 OpenAI API Key 轮转列表（兼容旧代码）"""
    global keys
    keys = new_keys


def _call_openai_sdk(messages, model_name, temperature, timeout, proxy):
    """使用原版 openai Python SDK 调用（GPT-3.5/4 等）"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        api_key = _get_llm_api_key()
    if not api_key:
        raise ValueError(
            "No API key provided!\n"
            "Set OPENAI_API_KEY environment variable, or use LLM_BACKEND=openai_compatible"
        )
    print(f'[OpenAI SDK] model={model_name}, key={api_key[:10]}...')
    os.environ["OPENAI_API_KEY"] = api_key

    import openai
    openai.api_key = api_key
    if org:
        openai.organization = org

    try:
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
        return response['choices'][0]['message']
    except Exception as e:
        print(f'[OpenAI SDK Error] {e}')
        raise


def _https_post_direct(url, headers, body_json, timeout=60):
    """
    纯 Python http.client 发送 HTTPS POST 请求，完全绕过 requests 库和代理。
    这是解决系统代理干扰的终极方案。
    """
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 443
    path = parsed.path if parsed.path else "/"
    
    # 创建 SSL 上下文
    ctx = ssl.create_default_context()
    
    conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
    try:
        conn.request("POST", path, body=body_json, headers=headers)
        response = conn.getresponse()
        data = response.read()
        status = response.status
    except Exception as e:
        conn.close()
        raise
    finally:
        conn.close()
    
    if status >= 400:
        raise http.client.HTTPException(f"HTTP {status}: {data.decode('utf-8', errors='replace')[:500]}")
    
    return json.loads(data)


def _call_compatible_api(messages, model_name, temperature, timeout, proxy, base_url=None):
    """
    使用 OpenAI-Compatible REST API 调用（DeepSeek / Qwen / 火山引擎 等）
    
    核心修复：使用纯 http.client 直接发送 HTTPS 请求，完全绕过 requests 库
    这样无论系统环境变量怎么设置 http_proxy，都不会走代理。
    """
    url_base = base_url or _get_base_url()
    api_key = _get_llm_api_key()
    if not api_key:
        raise ValueError(
            "LLM_API_KEY is not set!\n"
            "Please set one of these:\n"
            "  1. Run llm_config.py to export LLM_API_KEY env var\n"
            "  2. Set LLM_API_KEY environment variable\n"
            "  3. Call set_keys(['sk-your-key']) before any Agent init\n"
        )
    print(f'[Compatible API] model={model_name}, key={api_key[:10]}...')

    url = f"{url_base}/chat/completions"
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "timeout": timeout,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    body_json = json.dumps(payload)

    try:
        # 使用纯 http.client 发送请求，完全绕过代理
        data = _https_post_direct(url, headers, body_json, timeout=timeout)

        # 兼容不同厂商的返回格式
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice:
                return choice["message"]
            elif "text" in choice:
                return {"role": "assistant", "content": choice["text"]}
            elif "delta" in choice:
                return {"role": "assistant", "content": choice["delta"].get("content", "")}

        print(f'[Compatible API] Unexpected response format: {json.dumps(data, ensure_ascii=False)[:300]}')
        raise ValueError(f"Unexpected API response format: {data}")

    except json.JSONDecodeError as e:
        print(f'[Compatible API] JSON decode error: {e}')
        raise
    except Exception as e:
        print(f'[Compatible API Error] {e}')
        raise


def chat_gpt(messages, model_name=None, sleep_time=20, temperature=0, proxy=None):
    """
    统一的 LLM 调用入口。
    
    参数:
        messages: 对话消息列表 [{"role":"user","content":"..."}]
        model_name: 模型名称。如果为 None，根据 LLM_BACKEND 自动选择：
                    - openai:         默认 "gpt-3.5-turbo-0613"
                    - openai_compatible: 默认 LLM_MODEL 环境变量值
        sleep_time: 调用后等待间隔（秒），用于控制 API 速率
        temperature: 采样温度
        proxy: 代理地址（如 "http://127.0.0.1:10809"），仅对旧版 OpenAI SDK 生效

    返回:
        dict: {"role": "assistant", "content": "..."}
    """
    # 动态获取配置（支持环境变量在模块导入后设置）
    current_backend = _get_backend()
    current_model = _get_model()
    current_base_url = _get_base_url()

    if model_name is None:
        if current_backend == "openai_compatible":
            model_name = current_model
        else:
            model_name = "gpt-3.5-turbo-0613"

    print(f'[LLM] backend={current_backend} model={model_name}')
    print(f'message[-1]={messages[-1]}')

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            if current_backend == "openai_compatible":
                response = _call_compatible_api(messages, model_name, temperature, timeout=60, proxy=proxy, base_url=current_base_url)
            else:
                response = _call_openai_sdk(messages, model_name, temperature, timeout=60, proxy=proxy)

            print(f'[LLM Response] role={response["role"]}, content_preview={str(response["content"])[:100]}...')
            time.sleep(sleep_time)
            return response

        except Exception as e:
            last_error = e
            print(f'[LLM Attempt {attempt+1}/{max_retries}] Error: {e}')
            if attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)
                print(f'  Retrying in {wait_time} seconds...')
                time.sleep(wait_time)

    # 全部重试失败
    print(f'[LLM] All {max_retries} attempts failed. Last error: {last_error}')
    raise last_error


def get_init_chat():
    return [
        {"role": "system", "content": "You are a helpful assistant."}
    ]


def get_token_num(text):
    from transformers import GPT2Tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokens = tokenizer.encode(text)
    return len(tokens)

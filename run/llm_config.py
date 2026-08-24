# =============================================================================
# TDAG 配置（国产大模型适配版）
# =============================================================================
# 使用方法: 复制本文件为 llm_config.py 并修改下面参数

# --- LLM 后端选择 ---
# "openai_compatible" = 使用 OpenAI-Compatible REST API（推荐国产模型）
# "openai"            = 使用原版 OpenAI Python SDK
LLM_BACKEND = "openai_compatible"

# --- 如果 LLM_BACKEND = "openai_compatible" ---
# 示例:
#   DeepSeek:  LLM_BASE_URL = "https://api.deepseek.com/v1",       LLM_MODEL = "deepseek-chat"
#   Qwen:      LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1", LLM_MODEL = "qwen-plus"
#   其他兼容:  LLM_BASE_URL = "你的API地址/v1",                    LLM_MODEL = "你的模型名"
LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
LLM_API_KEY = "替换为你的 API Key"  # 替换为你的 API Key
LLM_MODEL = "deepseek-v4-flash-ga-260731"

# --- 如果 LLM_BACKEND = "openai" ---
# OPENAI_API_KEY 应在环境变量中设置
# OPENAI_ORGANIZATION = "org-xxxxx"  # 可选

# --- API 调用配置 ---
# 调用间隔（秒），控制速率，防止被限流
API_INTERVAL = 5
# 每个 Agent 的最大迭代次数（run_incre.py 中单独配置）

# --- 工具服务配置 ---
# 工具后端（数据库、Python 执行器等）的端口
TOOL_SERVER_PORT = 8079

# --- HuggingFace 国内镜像（强烈推荐）---
# 不使用 VPN 也能快速下载模型，解决 sentence-transformers 下载失败问题
HF_ENDPOINT = "https://hf-mirror.com"

# --- 代理设置 ---
# 如果需要代理，取消注释并填写；不需要则设为 None
PROXY = None
# PROXY = "http://127.0.0.1:10809"

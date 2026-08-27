"""
decompose.py — 两阶段图构建模块

将 MainAgent.Decompose(T) -> t_list 改造为：
  阶段一：LLM 生成节点清单（扁平列表）
  阶段二：逐节点收集依赖声明
  代码层组装为 DiGraph
"""

import json
import re
from utils.graph_builder import GraphBuilder
from utils.api_service import chat_gpt
from agents.main_agent.prompt import NODE_LIST_PROMPT, DEPENDENCY_PROMPT


def _parse_json_response(response_text):
    """
    从 LLM 响应中解析 JSON。
    尝试直接解析，或提取代码块内的 JSON。
    """
    response_text = response_text.strip()

    # 尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 块中提取
    json_block = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', response_text)
    if json_block:
        try:
            return json.loads(json_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试从第一个 { 或 [ 开始解析
    for i, ch in enumerate(response_text):
        if ch in ('[', '{'):
            try:
                return json.loads(response_text[i:])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Failed to parse JSON from LLM response:\n{response_text[:500]}")


def _llm_chat(messages, model_name='gpt-3.5-turbo-0613', proxy=None):
    """
    统一 LLM 调用入口，适配现有 BaseAgent.chat_gpt 接口。

    Parameters
    ----------
    messages : list[dict] 或 str
        可以是单条消息的 content（str），也可以是消息列表。
    model_name : str
        模型名称。
    proxy : str
        代理地址。

    Returns
    -------
    str
        LLM 响应文本。
    """
    if isinstance(messages, str):
        messages = [{'role': 'user', 'content': messages}]
    response = chat_gpt(messages=messages, model_name=model_name, proxy=proxy, temperature=0)
    return response.get('content', '')


def generate_nodes(task, model_name='gpt-3.5-turbo-0613', proxy=None):
    """
    第一阶段：生成节点清单（扁平列表）。

    Parameters
    ----------
    task : str
        原始任务描述。
    model_name : str
        模型名称。
    proxy : str
        代理地址。

    Returns
    -------
    list[dict]
        节点列表，每个节点为 {"id": str, "desc": str}。
    """
    prompt = NODE_LIST_PROMPT.format(task=task)
    response_text = _llm_chat(prompt, model_name=model_name, proxy=proxy)
    nodes = _parse_json_response(response_text)

    if not isinstance(nodes, list):
        raise ValueError(f"Expected a JSON array of nodes, got: {type(nodes)}")

    # 校验：每个节点必须有 id 和 desc
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"Node at index {i} is not a dict")
        if 'id' not in node:
            raise ValueError(f"Node at index {i} missing 'id' field")
        if 'desc' not in node:
            raise ValueError(f"Node at index {i} missing 'desc' field")

    return nodes


def collect_dependencies(node_id, node_desc, all_nodes, model_name='gpt-3.5-turbo-0613', proxy=None):
    """
    第二阶段：收集单个节点的依赖。

    Parameters
    ----------
    node_id : str
        当前节点 ID。
    node_desc : str
        当前节点描述。
    all_nodes : list[dict]
        所有节点的列表，用于让 LLM 参考。
    model_name : str
        模型名称。
    proxy : str
        代理地址。

    Returns
    -------
    list[dict]
        依赖列表，每个元素为 {"from": str, "label": str}。
    """
    prompt = DEPENDENCY_PROMPT.format(
        node_id=node_id,
        node_desc=node_desc,
        all_nodes=json.dumps(all_nodes, ensure_ascii=False, indent=2)
    )
    response_text = _llm_chat(prompt, model_name=model_name, proxy=proxy)
    deps = _parse_json_response(response_text)

    if not isinstance(deps, list):
        raise ValueError(f"Expected a JSON array of dependencies, got: {type(deps)}")

    # 校验：deps 中的 id 必须存在于 all_nodes
    valid_ids = {n['id'] for n in all_nodes}
    for dep in deps:
        if not isinstance(dep, dict):
            raise ValueError(f"Dependency is not a dict: {dep}")
        if 'from' not in dep or 'label' not in dep:
            raise ValueError(f"Dependency missing 'from' or 'label': {dep}")
        if dep['from'] not in valid_ids:
            raise ValueError(
                f"Dependency references non-existent node '{dep['from']}'. "
                f"Valid IDs: {valid_ids}"
            )
        if dep['label'] not in ('TIME', 'LOCATION', 'COST', 'CATEGORY'):
            raise ValueError(
                f"Invalid edge label '{dep['label']}'. "
                f"Must be TIME/LOCATION/COST/CATEGORY"
            )

    return deps


def auto_inject_labels(G):
    """
    根据节点描述的关键词自动标注边类型。
    对 LLM 可能标注为 CATEGORY 的边，尝试用关键词规则细化。

    Parameters
    ----------
    G : nx.DiGraph
        任务依赖图。

    Returns
    -------
    nx.DiGraph
        带边标签的图。
    """
    for u, v in G.edges:
        label = G.edges[u, v].get('label', 'CATEGORY')
        # 如果 LLM 已经标注了非 CATEGORY 的值，直接保留
        if label != 'CATEGORY':
            continue

        desc_u = G.nodes[u].get('desc', '')
        desc_v = G.nodes[v].get('desc', '')

        # 规则1：TIME — 前驱含时间信息，后继涉及安排/预订
        if any(k in desc_u for k in ['时间', '班次', '出发', '到达', '车次']) and \
           any(k in desc_v for k in ['预订', '预约', '安排', '计划']):
            G.edges[u, v]['label'] = 'TIME'
            continue

        # 规则2：LOCATION — 后继涉及位置相关搜索/推荐
        if any(k in desc_v for k in ['搜索', '推荐', '查询', '查找']) and \
           any(k in (desc_u + desc_v) for k in ['酒店', '住宿', '位置', '地址', '城市', '路线', '交通']):
            G.edges[u, v]['label'] = 'LOCATION'
            continue

        # 规则3：COST — 两边都涉及价格
        if any(k in desc_u for k in ['价格', '费用', '预算', '花费', '成本']) and \
           any(k in desc_v for k in ['价格', '费用', '预算', '花费', '成本']):
            G.edges[u, v]['label'] = 'COST'
            continue

        # 默认保持 CATEGORY
        G.edges[u, v]['label'] = 'CATEGORY'

    return G


def build_graph_two_phase(task, model_name='gpt-3.5-turbo-0613', proxy=None):
    """
    两阶段图构建主入口。

    流程：
      1. LLM 生成节点清单（扁平列表）
      2. 创建空图，逐个添加节点
      3. 逐节点调用 LLM 收集依赖声明
      4. 自动注入边标签
      5. 校验与入度截断

    Parameters
    ----------
    task : str
        原始任务描述。
    model_name : str
        模型名称。
    proxy : str
        代理地址。

    Returns
    -------
    nx.DiGraph
        合法的有向无环图。
    """
    # 阶段一：生成节点清单
    nodes = generate_nodes(task, model_name=model_name, proxy=proxy)
    G = GraphBuilder.create_empty_graph()

    # 创建节点
    for n in nodes:
        GraphBuilder.add_node(G, n['id'], n['desc'])

    # 阶段二：逐个收集依赖
    for n in nodes:
        deps = collect_dependencies(n['id'], n['desc'], nodes, model_name=model_name, proxy=proxy)
        for dep in deps:
            GraphBuilder.add_edge(G, dep['from'], n['id'], dep['label'])

    # 自动注入边标签（细化 CATEGORY 边）
    G = auto_inject_labels(G)

    # 校验与截断（环检测 + 入度截断）
    G = GraphBuilder.validate(G)

    return G

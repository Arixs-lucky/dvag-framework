"""
repair.py — 局部修复模块

替代全局重规划的 UpdateTasks，仅重算因果影响域内的节点。
"""

import json
from utils.impact_zone import ImpactZone
from utils.graph_builder import GraphBuilder

# ── 修复提示模板 ──
REPAIR_SYSTEM = """You are a task repair expert. When certain subtasks fail due to an error, you need to regenerate the plan only for the affected subtasks (the "impact zone").

Rules:
1. Only regenerate the nodes listed in sub_tasks — do not change frozen nodes outside the impact zone.
2. Each subtask has dependencies listed in "deps" — these are nodes whose results you can rely on.
3. You must address the specific failure reason provided in the feedback.
4. Return ONLY a valid JSON array, nothing else.

Output format (JSON array of objects):
[
  {"id": "node_id", "desc": "updated description"},
  {"id": "node_id", "desc": "updated description"}
]

Each node should have its id preserved and a refined description that accounts for the failure and available cached results."""

REPAIR_PROMPT = f'''{REPAIR_SYSTEM}

反馈：
<<feedback>>

影响域内子任务：
<<sub_tasks>>

现在返回修复后的节点描述。'''


def repair_subgraph(G, Z, candidate_pool, failed_node, error_msg, llm_client):
    """
    局部修复：仅重算影响域内的节点。

    流程：
    1. 冻结影响域外节点
    2. 清空影响域内节点的候选结果
    3. 构建子任务列表（含依赖和缓存结果）
    4. 调用 LLM 生成修复方案
    5. 更新图中的节点描述和状态

    Parameters
    ----------
    G : nx.DiGraph
        任务依赖图。
    Z : set
        影响域节点集合。
    candidate_pool : dict
        候选结果缓存。
    failed_node : str
        失败节点 ID。
    error_msg : str
        失败原因。
    llm_client : object
        LLM 客户端，需具有 chat(messages) -> dict 方法。

    Returns
    -------
    nx.DiGraph
        修复后的图。
    """
    # 1. 冻结影响域外节点，恢复影响域内节点
    ImpactZone.freeze_others(G, Z)

    # 2. 清空影响域内节点的候选结果
    for n in Z:
        if n in candidate_pool:
            del candidate_pool[n]

    # 3. 构建反馈信息和子任务列表
    feedback = ImpactZone.format_feedback(failed_node, error_msg, Z)
    sub_tasks = ImpactZone.build_subtask_list(G, Z, candidate_pool)

    print(f'[Repair] Impact zone: {sorted(Z)}')
    print(f'[Repair] Failed node: {failed_node}')
    print(f'[Repair] Error: {error_msg}')
    print(f'[Repair] Subtasks to repair: {len(sub_tasks)}')

    # 4. 构建修复 prompt 并调用 LLM
    # 注意：REPAIR_PROMPT 使用 << >> 占位符而非 { }，
    # 因为 sub_tasks 是 JSON 字符串，其中的 { } 会被 Python str.format 误解析
    feedback_text = feedback
    sub_tasks_text = json.dumps(sub_tasks, ensure_ascii=False, indent=2)

    prompt = REPAIR_PROMPT
    prompt = prompt.replace('<<feedback>>', feedback_text)
    prompt = prompt.replace('<<sub_tasks>>', sub_tasks_text)

    response_text = llm_client.chat(prompt)

    # 5. 解析修复结果并更新图
    try:
        new_nodes = json.loads(response_text)
    except json.JSONDecodeError:
        # 尝试从代码块中提取
        import re
        m = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', response_text)
        if m:
            new_nodes = json.loads(m.group(1).strip())
        else:
            print(f'[Repair] Failed to parse LLM response, skipping update')
            return G

    if not isinstance(new_nodes, list):
        print(f'[Repair] Expected a JSON array, got {type(new_nodes)}')
        return G

    # 6. 更新图中的节点
    for node in new_nodes:
        node_id = node.get('id')
        if node_id and node_id in Z:
            G.nodes[node_id]['desc'] = node.get('desc', G.nodes[node_id].get('desc', ''))
            G.nodes[node_id]['status'] = 'pending'
            G.nodes[node_id]['frozen'] = False
            print(f'[Repair] Updated node {node_id}')

    return G

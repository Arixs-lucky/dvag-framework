"""
constraints.py — 声明式约束收集模块

将用户任务中的硬约束提取为结构化约束列表，供 MILP 求解器使用。
支持的约束类型: sum, sequence, count, xor, imply, ratio
"""

import json

CONSTRAINT_PROMPT = """\
You are a constraint extraction expert. Given a user task and candidate plan summaries,
extract all HARD constraints that must be satisfied by any valid solution.

User Task:
{task}

Candidate Plan Summary:
{candidate_summary}

Please output constraints in the following JSON format ONLY (no markdown, no extra text):
[
  {{"type": "sum", "items": ["v1.price", "v2.price"], "op": "<=", "value": 250000}},
  {{"type": "sequence", "before": "v1.arrival", "after": "v3.start", "op": "<"}},
  {{"type": "count", "items": ["v2.cuisine"], "must_contain": "Kaiseki", "op": ">=", "value": 1}}
]

Supported constraint types:
- **sum**: Aggregate over numeric fields. e.g. total price ≤ budget
- **sequence**: Temporal ordering. before.time < after.time (optionally with delta gap)
- **count**: Cardinality constraints on categorical fields
- **xor**: Exactly one of a set of alternatives must be chosen
- **imply**: If node A is selected, node B must also be selected
- **ratio**: Ratio between two numeric fields must be within range

Output ONLY a valid JSON array.

"""


def collect_constraints(task, candidate_pool, llm_client):
    """
    收集声明式约束。

    将用户任务中的硬约束提取为结构化约束列表，并做值域校验。

    Parameters
    ----------
    task : str
        用户原始任务。
    candidate_pool : dict
        节点 ID → 候选结果列表。
    llm_client : object
        LLM 客户端。

    Returns
    -------
    list[dict]
        结构化约束列表。
    """
    # 构建候选摘要
    summary = {}
    for node_id, results in candidate_pool.items():
        if not results:
            continue
        if isinstance(results, dict):
            results = [results]
        summary[str(node_id)] = {
            'count': len(results),
            'fields': list(results[0].keys()) if isinstance(results[0], dict) else [],
            'sample': {k: str(v)[:50] for k, v in results[0].items()} if isinstance(results[0], dict) else None
        }

    prompt = CONSTRAINT_PROMPT.format(
        task=task,
        candidate_summary=json.dumps(summary, ensure_ascii=False, indent=2)
    )

    response = llm_client.chat(prompt)

    # 解析 JSON 响应
    constraints = _parse_json_response(response)
    if not isinstance(constraints, list):
        raise ValueError(f"Expected a JSON array, got {type(constraints)}")

    # 校验：值域合理性
    for c in constraints:
        if not isinstance(c, dict) or 'type' not in c:
            raise ValueError(f"Invalid constraint format: {c}")

        if c['type'] == 'sum':
            if 'value' in c and isinstance(c['value'], (int, float)) and c['value'] < 0:
                raise ValueError(f"Invalid budget value: {c['value']}")

        if c['type'] == 'sequence':
            if c.get('delta', 0) < 0:
                raise ValueError(f"Invalid delta: {c.get('delta')}")

    return constraints


def _parse_json_response(response_text):
    """从 LLM 响应中安全解析 JSON"""
    # 尝试直接解析
    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试从代码块中提取
    import re
    m = re.search(r'```(?:json)?\s*\n([\s\S]*?)\n```', response_text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到第一个 '[' 到最后一个 ']' 之间的内容
    m = re.search(r'\[.*\]', response_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to parse JSON from LLM response:\n{response_text[:200]}")

"""
milp_solver.py — MILP 求解入口

封装 MILPTranslator，处理求解、解码和松弛向量计算。
"""

import itertools
from ortools.linear_solver import pywraplp
from utils.milp_translator import MILPTranslator


def solve_milp(candidate_pool, constraints):
    """
    求解 MILP 问题。

    Parameters
    ----------
    candidate_pool : dict
        节点 ID → 候选结果列表。
    constraints : list[dict]
        结构化约束列表。

    Returns
    -------
    dict
        {
            'status': 'optimal' | 'infeasible' | 'unknown',
            'solution': dict (optimal 时返回)
            'delta': dict (infeasible 时返回松弛向量)
        }
    """
    try:
        solver, variables = MILPTranslator.build_model(candidate_pool, constraints)
    except Exception as e:
        # 模型构建失败，直接返回不可行
        return {'status': 'infeasible', 'error': str(e)}

    status = solver.Solve()

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        return _decode_solution(solver, variables, candidate_pool)

    elif status == pywraplp.Solver.INFEASIBLE:
        delta = compute_relaxation(candidate_pool, constraints)
        return {'status': 'infeasible', 'delta': delta}

    else:
        return {'status': 'unknown', 'solver_status': status}


def _decode_solution(solver, variables, candidate_pool):
    """
    解码最优解：提取被选中的候选。

    Returns
    -------
    dict
        {
            'status': 'optimal',
            'solution': {node_id: selected_cand}
        }
    """
    selected = {}
    for var_name, var in variables.items():
        if var.solution_value() > 0.5:
            parts = var_name.rsplit('_', 1)
            node_id = parts[0]
            idx = int(parts[1])
            if node_id in candidate_pool:
                selected[node_id] = candidate_pool[node_id][idx]

    return {
        'status': 'optimal',
        'solution': selected,
        'objective_value': solver.Objective().Value()
    }


def compute_relaxation(candidate_pool, constraints):
    """
    计算最小松弛量：在忽略预算约束的情况下，满足时序约束的最低总成本。

    Parameters
    ----------
    candidate_pool : dict
        节点 ID → 候选结果列表。
    constraints : list[dict]
        结构化约束列表。

    Returns
    -------
    dict
        {
            'min_total': float (最低总成本),
            'delta_cost': float (超出预算的金额),
            'satisfy_constraints': bool
        }
    """
    # 提取预算
    budget = float('inf')
    has_budget_constraint = False
    for c in constraints:
        if c.get('type') == 'sum' and 'value' in c:
            budget = float(c['value'])
            has_budget_constraint = True
            break

    # 收集时序约束（before/after 节点及字段名）
    seq_constraints = []
    for c in constraints:
        if c.get('type') == 'sequence':
            seq_constraints.append({
                'before_node': c['before'].split('.')[0],
                'before_field': c['before'].split('.')[1],
                'after_node': c['after'].split('.')[0],
                'after_field': c['after'].split('.')[1],
                'delta': float(c.get('delta', 0))
            })

    # 遍历所有组合，找到满足时序约束且总成本最低的组合
    min_total = float('inf')
    best_combo = None

    node_ids = [nid for nid, cands in candidate_pool.items() if cands]
    if not node_ids:
        return {
            'min_total': 0,
            'delta_cost': 0,
            'satisfy_constraints': False
        }

    candidate_lists = [candidate_pool[nid] for nid in node_ids]

    # 如果组合数过大，只取每个节点评分最高的候选
    total_combos = 1
    for cl in candidate_lists:
        total_combos *= len(cl)

    if total_combos > 100000:
        # 取每个节点的最高评分候选
        best_cands = []
        for cl in candidate_lists:
            best = max(cl, key=lambda c: c.get('score', 0) if isinstance(c, dict) else 0)
            best_cands.append(best)
        combination = best_cands
    else:
        combination = None

    if combination is None:
        for combo in itertools.product(*candidate_lists):
            # 检查时序约束
            satisfies = True
            node_map = dict(zip(node_ids, combo))
            for seq in seq_constraints:
                b = node_map.get(seq['before_node'])
                a = node_map.get(seq['after_node'])
                if b and a:
                    bf = seq['before_field']
                    af = seq['after_field']
                    if isinstance(b, dict) and isinstance(a, dict):
                        if bf in b and af in a:
                            bv = float(b[bf])
                            av = float(a[af])
                            if bv + seq['delta'] > av:
                                satisfies = False
                                break

            if satisfies:
                total = sum(c.get('price', 0) if isinstance(c, dict) else 0
                           for c in combo)
                if total < min_total:
                    min_total = total
                    best_combo = combo

    if min_total == float('inf'):
        # 无可行的时序约束满足组合
        # 回退：找最低成本的任意组合
        min_total = sum(min(
            (c.get('price', 0) if isinstance(c, dict) else 0)
            for c in cl
        ) for cl in candidate_lists)

    delta_cost = max(0, min_total - budget) if has_budget_constraint else 0

    return {
        'min_total': min_total,
        'delta_cost': delta_cost,
        'satisfy_constraints': min_total < float('inf')
    }


def identify_expensive_nodes(candidate_pool, top_k=3):
    """
    识别最昂贵的节点（用于 infeasible 时的回退策略）。

    Parameters
    ----------
    candidate_pool : dict
        节点 ID → 候选结果列表。
    top_k : int
        返回前 k 个最贵的节点。

    Returns
    -------
    list[str]
        节点 ID 列表。
    """
    node_costs = {}
    for node_id, cands in candidate_pool.items():
        if not cands:
            continue
        # 取平均成本
        costs = [c.get('price', 0) if isinstance(c, dict) else 0 for c in cands]
        node_costs[node_id] = sum(costs) / len(costs) if costs else 0

    sorted_nodes = sorted(node_costs.items(), key=lambda x: x[1], reverse=True)
    return [n[0] for n in sorted_nodes[:top_k]]

"""
milp_translator.py — 从候选池 + 约束构建 MILP 模型的翻译器

使用 Google OR-Tools 的 pywraplp 构建混合整数线性规划模型。
每个节点恰好选择一个候选，同时满足所有声明式约束。
"""

from ortools.linear_solver import pywraplp


class MILPTranslator:
    """MILP 模型构建器"""

    @staticmethod
    def build_model(candidate_pool, constraints):
        """
        构建 MILP 模型。

        决策变量:
            x_{node_idx} ∈ {0, 1} 表示节点 node 的第 idx 个候选是否被选中。

        约束:
            1. 每个节点恰好选一个候选: Σ_ι x_{node,ι} = 1
            2. sum 约束: 聚合数值字段
            3. sequence 约束: 时间顺序约束
            4. count 约束: 基数约束

        目标:
            最大化综合评分 Σ x_{node,ι} · score_{node,ι}

        Parameters
        ----------
        candidate_pool : dict
            节点 ID → 候选结果列表。
        constraints : list[dict]
            结构化约束列表。

        Returns
        -------
        tuple(Solver, dict)
            (solver, variables) — OR-Tools 求解器和决策变量字典。
        """
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            raise RuntimeError("Failed to create MILP solver (SCIP)")

        # ── 创建决策变量 ──
        variables = {}
        for node_id, candidates in candidate_pool.items():
            if not candidates:
                continue
            for idx, cand in enumerate(candidates):
                var_name = f"{node_id}_{idx}"
                variables[var_name] = solver.IntVar(0, 1, var_name)

        # ── 每个节点恰选一个 ──
        for node_id, candidates in candidate_pool.items():
            if not candidates:
                continue
            node_vars = [variables[f"{node_id}_{idx}"] for idx in range(len(candidates))]
            solver.Add(sum(node_vars) == 1)

        # ── 翻译约束 ──
        for c in constraints:
            ctype = c.get('type')

            if ctype == 'sum':
                expr = []
                for item in c['items']:
                    node_id, field = item.split('.', 1)
                    for idx, cand in enumerate(candidate_pool.get(node_id, [])):
                        if isinstance(cand, dict) and field in cand:
                            val = float(cand[field])
                            expr.append(val * variables[f"{node_id}_{idx}"])

                op = c.get('op', '<=')
                rhs = float(c['value'])
                if op == '<=' or op == '<':
                    solver.Add(sum(expr) <= rhs)
                elif op == '>=' or op == '>':
                    solver.Add(sum(expr) >= rhs)
                elif op == '=':
                    solver.Add(sum(expr) == rhs)

            elif ctype == 'sequence':
                # 时间顺序约束: before.time + delta <= after.time
                before_node, before_field = c['before'].split('.', 1)
                after_node, after_field = c['after'].split('.', 1)
                delta = float(c.get('delta', 0))

                before_cands = candidate_pool.get(before_node, [])
                after_cands = candidate_pool.get(after_node, [])

                if not before_cands or not after_cands:
                    continue

                # 使用 Big-M 法构建逻辑约束
                # 如果 before_node 的第 i 个候选被选中 且 after_node 的第 j 个候选被选中，
                # 则 before.time[i] + delta <= after.time[j]
                big_m = 1e9

                for i, b_cand in enumerate(before_cands):
                    if not isinstance(b_cand, dict) or before_field not in b_cand:
                        continue
                    before_val = float(b_cand[before_field])

                    for j, a_cand in enumerate(after_cands):
                        if not isinstance(a_cand, dict) or after_field not in a_cand:
                            continue
                        after_val = float(a_cand[after_field])

                        # before_val + delta <= after_val + M*(1 - x_bi) + M*(1 - x_aj)
                        solver.Add(
                            before_val + delta - after_val <=
                            big_m * (1 - variables[f"{before_node}_{i}"]) +
                            big_m * (1 - variables[f"{after_node}_{j}"])
                        )

            elif ctype == 'count':
                # 基数约束: 至少/至多 k 个候选包含某分类值
                must_contain = c.get('must_contain')
                value = int(c.get('value', 0))
                op = c.get('op', '>=')
                items = c.get('items', [])

                for item in items:
                    node_id = item.split('.', 1)[0]
                    node_cands = candidate_pool.get(node_id, [])
                    match_vars = []

                    for idx, cand in enumerate(node_cands):
                        if isinstance(cand, dict):
                            # 检查是否匹配 must_contain
                            match = False
                            for field_val in cand.values():
                                if must_contain in str(field_val):
                                    match = True
                                    break
                            if match:
                                match_vars.append(variables[f"{node_id}_{idx}"])

                    if match_vars:
                        total = sum(match_vars)
                        if op == '>=' or op == '>':
                            solver.Add(total >= value)
                        elif op == '<=' or op == '<':
                            solver.Add(total <= value)

            elif ctype == 'xor':
                # 互斥：从一组选项中恰好选一个
                items = c.get('items', [])
                all_vars = []
                for node_id in items:
                    for idx in range(len(candidate_pool.get(node_id, []))):
                        all_vars.append(variables[f"{node_id}_{idx}"])

                if all_vars:
                    solver.Add(sum(all_vars) == 1)

            elif ctype == 'imply':
                # 蕴含约束: 如果 node_before 被选，则 node_after 必须被选
                # x_before ≤ sum(x_after)
                before_node = c.get('before') or c.get('if')
                after_node = c.get('after') or c.get('then')
                if before_node and after_node:
                    before_vars = [variables[f"{before_node}_{i}"]
                                   for i in range(len(candidate_pool.get(before_node, [])))]
                    after_vars = [variables[f"{after_node}_{i}"]
                                  for i in range(len(candidate_pool.get(after_node, [])))]
                    if before_vars and after_vars:
                        solver.Add(sum(before_vars) <= sum(after_vars))

        # ── 目标：最大化综合评分 ──
        objective = solver.Objective()
        for var_name, var in variables.items():
            node_id = var_name.split('_')[0]
            idx = int(var_name.split('_')[1])
            score = 0
            if node_id in candidate_pool and idx < len(candidate_pool[node_id]):
                cand = candidate_pool[node_id][idx]
                if isinstance(cand, dict):
                    score = float(cand.get('score', 1.0))
            objective.SetCoefficient(var, score)
        objective.SetMaximization()

        return solver, variables

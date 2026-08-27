"""
impact_zone.py — 因果影响域计算模块

当某个节点执行失败时，计算受影响的节点集合 Z。
传播规则：
- TIME/LOCATION 边：递归传播（下游任务强依赖上游的时间/位置信息）
- COST 边：标记但暂不加入（成本信息影响可验证，不一定需要重算）
- CATEGORY 边：截断（弱依赖，不影响下游）
- 失败节点的所有直接前驱：加入影响域（需要前驱提供新信息）
"""

from collections import deque


class ImpactZone:
    """因果影响域计算工具类"""

    @staticmethod
    def compute(G, failed_node):
        """
        计算因果影响域 Z。

        算法：
        1. 从失败节点开始前向传播，沿 TIME/LOCATION 边递归
        2. COST 边标记但不加入（影响可验证）
        3. CATEGORY 边截断
        4. 将失败节点的所有直接前驱加入影响域

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        failed_node : str
            失败节点的 ID。

        Returns
        -------
        set
            影响域节点 ID 集合。
        """
        Z = {failed_node}
        queue = deque([failed_node])

        while queue:
            v = queue.popleft()
            for succ in G.successors(v):
                if succ in Z:
                    continue
                label = G.edges[v, succ].get('label', 'CATEGORY')
                if label in ('TIME', 'LOCATION'):
                    Z.add(succ)
                    queue.append(succ)
                # COST: 标记但暂不加入
                # CATEGORY: 截断，不传播

        # 回溯加入：失败节点的所有直接前驱
        for pred in G.predecessors(failed_node):
            Z.add(pred)

        return Z

    @staticmethod
    def freeze_others(G, Z):
        """
        冻结影响域外的节点，恢复影响域内节点的状态。

        冻结节点标记为 'frozen'，影响域内节点标记为 'pending' 并取消冻结。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        Z : set
            影响域节点集合。
        """
        for n in G.nodes:
            if n not in Z:
                G.nodes[n]['frozen'] = True
            else:
                G.nodes[n]['frozen'] = False
                G.nodes[n]['status'] = 'pending'

    @staticmethod
    def format_feedback(failed_node, error_msg, Z):
        """
        构造修复反馈信息，供 LLM 阅读。

        Parameters
        ----------
        failed_node : str
            失败节点 ID。
        error_msg : str
            失败原因描述。
        Z : set
            影响域节点集合。

        Returns
        -------
        str
            格式化的反馈字符串。
        """
        return (
            f"节点 {failed_node} 失败，原因：{error_msg}。\n"
            f"影响域内节点：{sorted(Z)}。\n"
            f"请重新生成这些节点的方案，解决上述失败原因。"
        )

    @staticmethod
    def build_subtask_list(G, Z, candidate_pool):
        """
        构建影响域内子任务列表（含依赖信息）。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        Z : set
            影响域节点集合。
        candidate_pool : dict
            候选结果缓存。

        Returns
        -------
        list[dict]
            子任务列表，每个元素含 'id', 'desc', 'deps'（前驱中在影响域或已冻结的节点）。
        """
        sub_tasks = []
        for n in Z:
            pred_list = []
            for pred in G.predecessors(n):
                # 前驱在影响域内，或在影响域外但被冻结
                if pred in Z or G.nodes[pred].get('frozen', False):
                    pred_list.append(pred)

            # 如果有前驱结果可用，附加到描述中
            cached_result = None
            for pred in pred_list:
                if pred in candidate_pool:
                    cached_result = candidate_pool.get(pred)
                    break

            sub_tasks.append({
                'id': n,
                'desc': G.nodes[n].get('desc', ''),
                'deps': pred_list,
                'cached_result': str(cached_result)[:200] if cached_result else None
            })

        return sub_tasks

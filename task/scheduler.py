"""
scheduler.py — 基于拓扑并行的任务调度器

将 TDAG 的 for t_i in t_list 顺序执行改造为基于入度的并行调度。
"""

import asyncio
import json
import time
from collections import deque


class Scheduler:
    """
    基于 DAG 入度的并行任务调度器。

    核心机制：
    - 维护入度表，入度为 0 的节点放入就绪队列
    - 每轮从就绪队列取出一批节点并行执行
    - 每个节点执行完成后，更新后继节点的入度
    - 后继入度归零时加入就绪队列
    """

    def __init__(self, G, candidate_pool, llm_client, tool_doc=None, skill_lib=None):
        """
        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        candidate_pool : dict
            执行结果缓存，key=node_id, value=执行结果。
        llm_client : object
            LLM 客户端，需要具有 chat(prompt) -> str 方法。
        tool_doc : object, optional
            工具文档/注册表。
        skill_lib : object, optional
            技能库。
        """
        self.G = G
        self.candidate_pool = candidate_pool
        self.llm_client = llm_client
        self.tool_doc = tool_doc
        self.skill_lib = skill_lib
        # 维护入度表（独立副本，不影响图的原始入度）
        self.in_degree = {n: G.in_degree(n) for n in G.nodes}
        # 就绪队列：入度为 0 且状态为 pending 的节点
        self.ready_queue = deque(
            [n for n in G.nodes if self.in_degree[n] == 0 and G.nodes[n].get('status') == 'pending']
        )
        self.failed_nodes = []

    def build_context(self, node_id):
        """
        构建子智能体上下文：仅包含直接前驱的摘要。

        Parameters
        ----------
        node_id : str
            当前节点 ID。

        Returns
        -------
        dict
            包含 'task'（任务描述）和 'inputs'（前驱结果摘要）的上下文字典。
        """
        context = {
            'task': self.G.nodes[node_id].get('desc', ''),
            'inputs': {}
        }
        for pred in self.G.predecessors(node_id):
            label = self.G.edges[pred, node_id].get('label', 'CATEGORY')
            pred_result = self.candidate_pool.get(pred, {})
            # 根据标签类型提取对应字段
            extracted = self.extract_fields(pred_result, label)
            context['inputs'][pred] = {
                'label': label,
                'data': extracted
            }
        return context

    @staticmethod
    def extract_fields(result, label):
        """
        按标签类型从结果中提取相关字段。
        
        兼容两种结果格式：
        1. 原始格式: {"time": "08:00"}  
        2. 封装格式: {"data": {"time": "08:00"}}

        Parameters
        ----------
        result : dict
            前驱节点的执行结果。
        label : str
            依赖类型：TIME, LOCATION, COST, CATEGORY。

        Returns
        -------
        any
            提取的相关数据。
        """
        # 处理封装格式: 先提取 data 层
        data = result.get('data', result)
        if not isinstance(data, dict):
            return result

        if label == 'TIME':
            return data.get('time', data.get('arrival', data.get('departure')))
        elif label == 'LOCATION':
            return data.get('location', data.get('address', data.get('lat_lng')))
        elif label == 'COST':
            return data.get('price', data.get('cost'))
        else:
            return data.get('category', data.get('type'))

    def execute_node(self, node_id):
        """
        执行单个节点任务。

        流程：
        1. 构建上下文（仅包含直接前驱的摘要）
        2. 使用 AgentGenerator 构建子任务 prompt
        3. 使用 SubAgent 执行子任务
        4. 返回结果

        Parameters
        ----------
        node_id : str
            节点 ID。

        Returns
        -------
        dict
            执行结果，包含 'status' 和 'data' 字段。
        """
        print(f'[Scheduler] Executing node: {node_id}')
        context = self.build_context(node_id)

        try:
            from agents.agent_generator.agent import AgentGenerator
            from agents.sub_agent.agent import SubAgent
            from utils.prompt import generate_prompt

            # 构建子任务 prompt
            # 将上下文整合为一个子任务描述
            task_desc = context['task']
            inputs_desc = json.dumps(context['inputs'], ensure_ascii=False, indent=2)
            
            subtask_content = f"""当前子任务：{task_desc}

前驱节点输入：
{inputs_desc}

请基于以上信息完成此子任务。"""

            # 使用 SubAgent 执行（保留 TDAG 架构）
            # 这里 tool_doc 和 skill_lib 通过 SubAgent 的 prompt 系统间接传递
            subagent = SubAgent(
                action=subtask_content,
                total_task=task_desc,
                current_task=subtask_content,
                completed_task='',
                model_name=self.llm_client.model_name if hasattr(self.llm_client, 'model_name') else 'gpt-3.5-turbo',
                proxy=self.llm_client.proxy if hasattr(self.llm_client, 'proxy') else None
            )

            response = subagent.get_response()
            text = response['content']

            # 提取结果
            from utils.code import get_content
            result_text = get_content(text, begin_str='<result>', end_str='</result>')
            if result_text:
                return {'status': 'success', 'data': result_text}
            else:
                return {'status': 'success', 'data': text}

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'[Scheduler] Node {node_id} failed: {e}')
            return {'status': 'failed', 'error': str(e)}

    async def execute_node_async(self, node_id):
        """异步执行节点（用于 asyncio.gather 并行）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_node, node_id)

    def execute(self):
        """
        主执行循环：基于拓扑并行的调度。

        流程：
        1. 从就绪队列取出一批入度为 0 的节点
        2. 并行执行这一批节点
        3. 每个节点完成后：
           a. 将结果存入 candidate_pool
           b. 更新后继节点的入度
           c. 后继入度归零时加入就绪队列
        4. 任一节点失败则终止并返回失败信息

        Returns
        -------
        tuple(bool, str|None, dict|None)
            (success, failed_node_id, failed_result)
            - success: True 表示全部完成，False 表示中途失败
            - failed_node_id: 失败节点 ID（失败时）
            - failed_result: 失败结果详情（失败时）
        """
        print(f'[Scheduler] Starting execution with {len(self.G.nodes)} nodes')
        round_num = 0

        while self.ready_queue:
            round_num += 1
            batch = list(self.ready_queue)
            self.ready_queue.clear()

            print(f'[Scheduler] Round {round_num}: executing {len(batch)} nodes in parallel: {batch}')

            # 并行执行当前批次的节点
            try:
                results = asyncio.run(
                    asyncio.gather(*[self.execute_node_async(n) for n in batch], return_exceptions=True)
                )
            except Exception as e:
                print(f'[Scheduler] Async execution error: {e}')
                results = [{'status': 'failed', 'error': str(e)}] * len(batch)

            # 处理执行结果
            for node_id, result in zip(batch, results):
                # 处理异常对象
                if isinstance(result, Exception):
                    result = {'status': 'failed', 'error': str(result)}

                if result.get('status') == 'failed':
                    print(f'[Scheduler] Node {node_id} FAILED: {result}')
                    self.failed_nodes.append((node_id, result))
                    return False, node_id, result

                # 记录结果
                self.candidate_pool[node_id] = result.get('data', result)
                self.G.nodes[node_id]['status'] = 'done'
                print(f'[Scheduler] Node {node_id} DONE. Pool size: {len(self.candidate_pool)}')

                # 更新后继入度
                for succ in self.G.successors(node_id):
                    self.in_degree[succ] -= 1
                    if self.in_degree[succ] == 0:
                        self.ready_queue.append(succ)
                        print(f'[Scheduler] Successor {succ} added to ready queue (in_degree=0)')

        success = True
        # 检查是否所有节点都已标记为 done
        for n in self.G.nodes:
            if self.G.nodes[n].get('status') != 'done':
                success = False
                break

        print(f'[Scheduler] Execution finished. success={success}, total nodes={len(self.G.nodes)}, pool size={len(self.candidate_pool)}')
        return success, None, None

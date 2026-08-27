"""
GraphBuilder: 基于 networkx.DiGraph 的任务依赖图构建器。
支持节点/边增删、入度截断、拓扑就绪节点查询等功能。
"""

import networkx as nx
from config import MAX_INDEGREE


class GraphBuilder:
    """有向无环图（DAG）构建器，用于表示任务间的依赖关系。"""

    @staticmethod
    def create_empty_graph():
        """创建一个空的有向图。"""
        return nx.DiGraph()

    @staticmethod
    def add_node(G, node_id, description, tool=None):
        """
        向图中添加一个任务节点。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        node_id : str or int
            节点唯一标识。
        description : str
            任务描述。
        tool : str, optional
            关联的工具名称。
        """
        G.add_node(node_id, desc=description, tool=tool, status='pending')

    @staticmethod
    def add_edge(G, from_id, to_id, label):
        """
        向图中添加一条有向边，表示 from_id 完成后才能执行 to_id。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        from_id : str or int
            前驱节点标识。
        to_id : str or int
            后继节点标识。
        label : str
            依赖类型标签，可选值：'TIME', 'LOCATION', 'COST', 'CATEGORY'。
        """
        G.add_edge(from_id, to_id, label=label)

    @staticmethod
    def validate(G):
        """
        验证图的合法性：
        1. 检查是否含有环（必须是 DAG）。
        2. 对入度超过 MAX_INDEGREE 的节点，仅保留前 MAX_INDEGREE 条边。

        Parameters
        ----------
        G : nx.DiGraph
            待验证的任务依赖图。

        Returns
        -------
        nx.DiGraph
            验证并通过截断处理后的图。

        Raises
        ------
        ValueError
            当图中存在环时抛出。
        """
        # 1. 无环检测
        if not nx.is_directed_acyclic_graph(G):
            raise ValueError("Graph contains cycles")

        # 2. 入度截断
        for node in list(G.nodes):
            if G.in_degree(node) > MAX_INDEGREE:
                preds = list(G.predecessors(node))
                for pred in preds[MAX_INDEGREE:]:
                    G.remove_edge(pred, node)

        return G

    @staticmethod
    def get_ready_nodes(G):
        """
        获取所有就绪节点（入度为 0 且状态为 pending）。
        这些节点可以立即执行，因为它们所依赖的前驱任务全部完成。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。

        Returns
        -------
        list
            就绪节点 ID 列表。
        """
        return [n for n in G.nodes if G.in_degree(n) == 0 and G.nodes[n].get('status') == 'pending']

    @staticmethod
    def all_done(G):
        """
        检查图中所有节点是否都已标记为 done。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。

        Returns
        -------
        bool
            所有节点均完成则返回 True。
        """
        return all(G.nodes[n].get('status') == 'done' for n in G.nodes)

    @staticmethod
    def mark_done(G, node_id):
        """将指定节点的状态标记为 done。"""
        G.nodes[node_id]['status'] = 'done'

    @staticmethod
    def to_topological_list(G):
        """
        将图转换为拓扑排序后的节点列表。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。

        Returns
        -------
        list
            拓扑排序节点 ID 列表。
        """
        return list(nx.topological_sort(G))

    @staticmethod
    def get_dependents(G, node_id):
        """
        获取指定节点的所有后继节点（下游任务）。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        node_id : str or int
            节点标识。

        Returns
        -------
        list
            后继节点 ID 列表。
        """
        return list(G.successors(node_id))

    @staticmethod
    def get_prerequisites(G, node_id):
        """
        获取指定节点的所有前驱节点（上游任务）。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。
        node_id : str or int
            节点标识。

        Returns
        -------
        list
            前驱节点 ID 列表。
        """
        return list(G.predecessors(node_id))

    @staticmethod
    def graph_to_dict(G):
        """
        将图序列化为字典格式（JSON 可序列化）。

        Parameters
        ----------
        G : nx.DiGraph
            任务依赖图。

        Returns
        -------
        dict
            包含 nodes 和 edges 的字典。
        """
        nodes = []
        for node, data in G.nodes(data=True):
            nodes.append({
                'id': node,
                'desc': data.get('desc', ''),
                'tool': data.get('tool', None),
                'status': data.get('status', 'pending'),
            })

        edges = []
        for u, v, data in G.edges(data=True):
            edges.append({
                'from': u,
                'to': v,
                'label': data.get('label', ''),
            })

        return {'nodes': nodes, 'edges': edges}

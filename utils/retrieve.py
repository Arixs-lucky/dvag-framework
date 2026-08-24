import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import json
import numpy as np
import os
import random

from sentence_transformers import SentenceTransformer, util

def get_similarity(text1, text2, model_name='all-mpnet-base-v2'):
    """
    Calculate the cosine similarity between two text strings.

    Args:
    text1 (str): The first text string.
    text2 (str): The second text string.
    model_name (str): The name of the SentenceTransformer model to use.

    Returns:
    float: The cosine similarity between text1 and text2.
    """
    # Load the SentenceTransformer model
    model = SentenceTransformer(model_name)

    # Encode the texts into embeddings
    embedding1 = model.encode(text1, convert_to_tensor=True)
    embedding2 = model.encode(text2, convert_to_tensor=True)

    # Calculate cosine similarity
    similarity = util.pytorch_cos_sim(embedding1, embedding2)

    return similarity.item()


def encode_tasks(model, tasks, embeddings_file, rewrite=False):
    """
    对任务列表进行编码并保存或加载嵌入向量
    参数:
        model: 用于编码的模型
        tasks: 需要编码的任务列表
        embeddings_file: 嵌入向量的保存文件路径
        rewrite: 是否重写已存在的嵌入向量文件，默认为False
    返回:
        embeddings: 任务的嵌入向量
    """
    # 检查嵌入向量文件是否存在，并且rewrite参数为False
    if os.path.exists(embeddings_file) and not rewrite:
        # 如果文件存在且不需要重写，则直接加载已保存的嵌入向量
        embeddings = np.load(embeddings_file)
    else:
        # 如果文件不存在或需要重写，则使用模型对任务进行编码
        embeddings = model.encode(tasks, convert_to_tensor=True)
        # 将编码后的嵌入向量保存到文件
        np.save(embeddings_file, embeddings)
    return embeddings


def find_similar_tasks(embedding, embeddings, num_solutions=1):
    """
    根据嵌入向量查找最相似的任务
    参数:
        embedding (torch.Tensor): 当前任务的嵌入向量
        embeddings (torch.Tensor): 所有任务的嵌入向量矩阵
        num_solutions (int): 返回的最相似任务的数量，默认为1
    返回:
        numpy.ndarray: 最相似任务的索引数组
    """
    # 计算当前任务嵌入向量与所有任务嵌入向量之间的余弦相似度
    similarities = util.pytorch_cos_sim(embedding, embeddings)[0]
    # 获取相似度最高的num_solutions个任务的索引
    # argsort默认是升序，所以取负号实现降序排列
    most_similar_indices = np.argsort(-similarities)[:num_solutions]
    return most_similar_indices

# 少样本学习思想
def get_prompt(task_name, task_detail, solution_num=1, example_file='./data/travel/skill.json', rewrite=True,
               reverse=True, theta=None, use_detail=True):
    """
    根据任务名称和详情获取示例提示
    参数:
        task_name (str): 当前任务名称
        task_detail (str): 当前任务详情
        solution_num (int): 需要返回的示例数量，默认为1
        example_file (str): 示例数据文件路径，默认为'./data/travel/skill.json'
        rewrite (bool): 是否重新计算嵌入向量，默认为True
        reverse (bool): 是否反转结果顺序，默认为True
        theta (float): 相似度阈值，低于此值的示例将被过滤，默认为None
        use_detail (bool): 是否使用任务详情进行初始过滤，默认为True
    返回:
        str: 格式化后的示例任务信息字符串
    """
    # 构建嵌入文件路径
    example_file_name = example_file[:example_file.rfind('.json')]
    name_embeddings_file = f'{example_file_name}_name_embedding.npy'
    detail_embeddings_file = f'{example_file_name}_detail_embedding.npy'
    model_name = 'all-mpnet-base-v2'  # 使用的预训练模型名称

    # 加载示例数据
    with open(example_file, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 如果请求数量大于等于示例总数，返回所有示例
    if solution_num >= len(data):
        results = []
        for d in data:
            result = f"Example Task Name:\n{d['task_name']}\nExample Task Detail:\n{d['task_detail']}\nExample Solution:\n{d['solution']}\n"
            results.append(result)
        return '\n'.join(results[::])

    # 提取所有任务名称和详情
    task_names = [item['task_name'] for item in data]
    task_details = [item['task_detail'] for item in data]
    # 初始化句子编码模型
    model = SentenceTransformer(model_name)
    # 加载或生成任务名称的嵌入向量
    name_embeddings = encode_tasks(model, task_names, name_embeddings_file, rewrite)
    # 加载或生成任务详情的嵌入向量
    detail_embeddings = encode_tasks(model, task_details, detail_embeddings_file, rewrite)

    # Initial filtering based on task name
    current_task_name_embedding = model.encode(task_name, convert_to_tensor=True)

    if use_detail:
        similar_name_indices = find_similar_tasks(current_task_name_embedding, name_embeddings, solution_num * 2)
    else:
        similar_name_indices = find_similar_tasks(current_task_name_embedding, name_embeddings, solution_num)
    # Further filtering based on task detail
    current_task_detail_embedding = model.encode(task_detail, convert_to_tensor=True)
    filtered_task_details = [task_details[i] for i in similar_name_indices]
    filtered_detail_embeddings = detail_embeddings[np.array(similar_name_indices)]
    similar_detail_indices = find_similar_tasks(current_task_detail_embedding, filtered_detail_embeddings, solution_num)

    results = []
    for idx in similar_detail_indices:
        index = similar_name_indices[idx.item()]
        similar_task = data[index]
        if theta is not None:
            if len(results)>0 and get_similarity(similar_task['task_name'], task_name) < theta:
                continue
        result = f"Example Task Name:\n{similar_task['task_name']}\nExample Task Detail:\n{similar_task['task_detail']}\nExample Solution:\n{similar_task['solution']}\n"
        results.append(result)

    if reverse:
        return '\n'.join(results[::-1])
    return '\n'.join(results[::])

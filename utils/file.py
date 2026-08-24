import json


# ... existing code ...
def jsonl_to_json(jsonl_file_path, json_file_path):
    """
    将JSONL格式文件转换为标准JSON数组格式。

    Args:
        jsonl_file_path (str): 输入的JSONL文件路径，每行一个JSON对象。
        json_file_path (str): 输出的JSON文件路径，将保存为JSON数组格式。
    """
    data = []
    # 逐行读取JSONL文件并解析为Python对象列表
    with open(jsonl_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            data.append(json.loads(line))

    # 将数据写入格式化的JSON文件
    with open(json_file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
# ... existing code ...



# ... existing code ...
def json_to_jsonl(json_file_path, jsonl_file_path, filter_func=lambda x: True):
    """
    将JSON数组文件转换为JSONL格式，支持过滤数据。

    Args:
        json_file_path (str): 输入的JSON文件路径，应包含JSON数组。
        jsonl_file_path (str): 输出的JSONL文件路径。
        filter_func (function): 过滤函数，默认为保留所有数据项。
    """
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # 根据过滤函数筛选数据
    data = [d for d in data if filter_func(d)]

    # 将每个数据项逐行写入JSONL文件
    with open(jsonl_file_path, 'w', encoding='utf-8') as file:
        for entry in data:
            json.dump(entry, file, ensure_ascii=False)
            file.write('\n')
# ... existing code ...


# ... existing code ...
def merge_json(file_list, output_file):
    """
    合并多个JSON数组文件为一个JSON文件。

    Args:
        file_list (list): JSON文件路径列表，每个文件应包含JSON数组。
        output_file (str): 输出合并后的JSON文件路径。
    """
    data_all = []
    # 遍历所有输入文件并累积数据
    for f in file_list:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            data_all.extend(data)

    # 将合并后的数据写入输出文件
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(data_all, file, ensure_ascii=False, indent=4)
# ... existing code ...



# ... existing code ...
def get_json_refined(json_str):
    """
    解析并规范化JSON字符串，将单引号转换为双引号后加载为JSON对象。

    Args:
        json_str (str): 可能包含单引号的原始JSON字符串。

    Returns:
        dict or list: 解析后的JSON对象（字典或列表）。
    """
    formatted_str = ''
    in_double_quotes = False
    for char in json_str:
        if char == '"' and not in_double_quotes:
            in_double_quotes = True
        elif char == '"' and in_double_quotes:
            in_double_quotes = False

        # 在双引号外部将单引号替换为双引号以符合JSON规范
        if char == "'" and not in_double_quotes:
            formatted_str += '"'
        else:
            formatted_str += char

    # 解析格式化后的JSON字符串
    json_object = json.loads(formatted_str)
    return json_object
# ... existing code ...

import copy


def generate_prompt(template: str, replace_dict: dict):
    """
    根据模板和替换字典生成提示文本
    参数:
        template (str): 原始模板字符串
        replace_dict (dict): 包含替换键值对的字典
    返回:
        str: 替换后的提示文本
    """
    # 创建模板的深拷贝，避免修改原始模板
    prompt = copy.deepcopy(template)
    # 遍历替换字典中的所有键值对
    for k, v in replace_dict.items():
        # 在提示文本中替换所有匹配的键为对应的值（转换为字符串）
        prompt = prompt.replace(k, str(v))
    # 返回处理后的提示文本
    return prompt

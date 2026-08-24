import json

from agents.update_agent.prompt import SYSTEM_PROMPT, USER_FIRST_PROMPT
from agents.base_agent import BaseAgent
from utils.api_service import chat_gpt
from utils.code import get_content_list
from utils.prompt import generate_prompt
import copy


class UpdateAgent(BaseAgent):
    def __init__(self, task1,solution1,task2,solution2, record_path=None, model_name='gpt-3.5-turbo-0613',
                 proxy='http://127.0.0.1:10809'):

        """
        初始化UpdateAgent类
        :param task1: 第一个任务
        :param solution1: 第一个任务的解决方案
        :param task2: 第二个任务
        :param solution2: 第二个任务的解决方案
        :param record_path: 记录路径，可选
        :param model_name: 模型名称，默认为'gpt-3.5-turbo-0613'
        :param proxy: 代理地址，默认为'http://127.0.0.1:10809'
        """
        super().__init__(record_path, model_name, proxy)  # 调用父类的初始化方法
        self.system_prompt = self.generate_system_prompt()  # 生成系统提示
        self.messages.append({'role': 'system',  # 添加系统消息
                              'content': self.system_prompt})
        self.solution=solution1  # 设置当前解决方案为solution1
        self.messages.append({'role': 'user',  # 添加用户消息
                              'content': self.generate_first_user_prompt(task1=task1,
                                                                         solution1=solution1,
                                                                         task2=task2,
                                                                         solution2=solution2)})


    def generate_system_prompt(self):
        """
        生成系统提示
        :return: 格式化后的系统提示
        """
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
        }
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    def generate_first_user_prompt(self, task1,solution1,task2,solution2):
        """
        生成第一个用户提示
        :param task1: 第一个任务
        :param solution1: 第一个任务的解决方案
        :param task2: 第二个任务
        :param solution2: 第二个任务的解决方案
        :return: 格式化后的用户提示
        """
        user_prompt = USER_FIRST_PROMPT
        replace_dict = {
            '{{task1}}': str(task1),  # 替换任务1
            '{{solution1}}': solution1,  # 替换解决方案1
            '{{task2}}': str(task2),  # 替换任务2
            '{{solution2}}':solution2  # 替换解决方案2
        }
        return generate_prompt(template=user_prompt, replace_dict=replace_dict)

    def get_new_solution(self):

        """
        获取新的解决方案
        :return: 更新后的解决方案或保持原方案
        """
        response = chat_gpt(self.messages, model_name=self.model_name, proxy=self.proxy)  # 获取GPT响应
        self.messages.append(response)  # 将响应添加到消息列表
        if self.record_path is not None:  # 如果指定了记录路径
            with open(self.record_path, 'w', encoding='utf-8') as f:  # 打开文件
                json.dump(self.messages, f, indent=4, ensure_ascii=False)  # 保存消息到文件
        text = response['content']  # 获取响应文本
        functions = self.parse_functions(text)  # 解析函数

        if len(functions) == 0 or functions[0]['function_name'] == 'keep':  # 如果没有函数或选择保持
            return self.solution  # 返回原解决方案
        elif functions[0]['function_name'] == 'update':  # 如果选择更新
            return functions[0]['args'][0]  # 返回更新后的解决方案
import json

from agents.sub_agent.prompt import SYSTEM_PROMPT, MAX_ITER, CHECK_PROMPT, USER_PROMPT, USER_OVER_PROMPT \
    , USER_ERROR_PROMPT, SOLUTION_PROMPT, USER_FIRST_PROMPT
from agents.base_agent import BaseAgent

import copy
from utils.code import get_content, get_content_list
from utils.prompt import generate_prompt


class SubAgent(BaseAgent):
    def __init__(self, action, total_task, current_task, completed_task, record_path=None,
                 model_name='gpt-3.5-turbo-0613', proxy='http://127.0.0.1:10809',api_interval=20):

        """
        初始化SubAgent类
        :param action: 动作类型
        :param total_task: 总任务数
        :param current_task: 当前任务
        :param completed_task: 已完成的任务
        :param record_path: 记录路径
        :param model_name: 模型名称，默认为'gpt-3.5-turbo-0613'
        :param proxy: 代理地址，默认为'http://127.0.0.1:10809'
        :param api_interval: API调用间隔，默认为20
        """
        super().__init__(record_path, model_name, proxy, api_interval)  # 调用父类初始化方法
        self.total_task = total_task  # 设置总任务数
        self.subtasks = []  # 初始化子任务列表
        self.completed_tasks = []  # 初始化已完成任务列表

        # 生成系统提示
        self.system_prompt = self.generate_system_prompt(action=action, total_task=total_task,
                                                         current_task=current_task,
                                                         completed_task=completed_task)
        self.action_apace = self.get_action_space()  # 获取动作空间
        # 将系统提示添加到消息列表中
        self.messages.append({'role': 'system',
                              'content': self.system_prompt})
        # 生成并添加第一个用户提示
        self.messages.append({'role': 'user',
                              'content': self.generate_first_user_prompt(current_task=current_task)})

    def generate_first_user_prompt(self, current_task):
        """
        生成第一个用户提示
        :param current_task: 当前任务
        :return: 格式化后的用户提示
        """
        user_prompt = USER_FIRST_PROMPT
        replace_dict = {
            '{{current_task}}': str(current_task),
            '{{action_space}}': self.get_action_space()
        }

        return generate_prompt(template=user_prompt, replace_dict=replace_dict)

    def generate_system_prompt(self, action, total_task, current_task, completed_task):
        """
        生成系统提示
        :param action: 动作类型
        :param total_task: 总任务数
        :param current_task: 当前任务
        :param completed_task: 已完成的任务
        :return: 格式化后的系统提示
        """
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
            '{{action}}': action,
            '{{max_iter}}': str(MAX_ITER),
            '{{total_task}}': str(total_task),
            '{{current_task}}': str(current_task),
            '{{completed_task}}': str(completed_task)
        }
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    def generate_verify_prompt(self, check_ans):
        """
        生成验证提示
        :param check_ans: 检查答案
        :return: 格式化后的验证提示
        """
        check_prompt = CHECK_PROMPT
        replace_dict = {
            '{{answer}}': check_ans
        }
        prompt = copy.deepcopy(check_prompt)
        for k, v in replace_dict.items():
            prompt = prompt.replace(k, v)
        return prompt

    def add_user_prompt(self, observation):
        """
        添加用户提示
        :param observation: 观察内容
        """
        user_prompt = USER_PROMPT
        replace_dict = {
            '{{observation}}': observation,
            '{{action_space}}': str(self.action_apace)
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)
        print(f'user prompt={prompt}')
        self.messages.append({'role': 'user', 'content': prompt})

    def add_user_error_prompt(self, observation):
        """
        添加用户错误提示
        :param observation: 观察内容
        """
        user_prompt = USER_ERROR_PROMPT
        replace_dict = {
            '{{observation}}': observation,
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)
        print(f'user prompt={prompt}')
        self.messages.append({'role': 'user', 'content': prompt})

    def add_over_prompt(self):
        """添加结束提示"""
        self.messages.append({'role': 'user', 'content': USER_OVER_PROMPT})

    def add_verify_prompt(self, check_ans):
        """
        添加验证提示
        :param check_ans: 检查答案
        """
        check_prompt = CHECK_PROMPT
        replace_dict = {
            '{{answer}}': check_ans
        }
        prompt = copy.deepcopy(check_prompt)
        for k, v in replace_dict.items():
            prompt = prompt.replace(k, v)
        self.messages.append({'role': 'user',
                              'content': f'{prompt}'})

    def get_result(self, text):
        """
        从文本中提取结果
        :param text: 输入文本
        :return: 提取的结果
        """
        return get_content(text, begin_str='<result>', end_str='</result>')

    def get_process(self, text):
        """
        从文本中提取过程
        :param text: 输入文本
        :return: 提取的过程
        """
        return get_content(text, begin_str='<process>', end_str='</process>')

    def load_from_json(self, json_path):
        """
        从JSON文件加载消息
        :param json_path: JSON文件路径
        """
        with open(json_path, "r",encoding="utf-8") as json_file:
            self.messages = json.load(json_file)
        self.system_prompt = self.messages[0]['content']
        self.action_apace = self.get_action_space()

    def add_solution_prompt(self):
        """添加解决方案提示"""
        self.messages.append({'role': 'user',
                              'content': f'{SOLUTION_PROMPT}'})

from agents.plan_and_execute.planner.prompt import SYSTEM_PROMPT, USER_FIRST, USER_OVER_PROMPT, EXAMPLE_MESSAGES
from agents.base_agent import BaseAgent
from utils.prompt import generate_prompt


class Planner(BaseAgent):
    def __init__(self, task, record_path=None, model_name='gpt-3.5-turbo-0613', proxy='http://127.0.0.1:10809',example_message=EXAMPLE_MESSAGES, api_interval=20):
        """
        初始化Planner类
        :param task: 要执行的任务
        :param record_path: 记录路径
        :param model_name: 模型名称
        :param proxy: 代理地址
        :param example_message: 示例消息
        :param api_interval: API调用间隔
        """
        super().__init__(record_path=record_path, model_name=model_name, proxy=proxy,api_interval=api_interval)
        self.task = task  # 存储任务
        self.subtasks = []  # 子任务列表
        self.completed_tasks = []  # 已完成任务列表
        self.system_prompt = self.generate_system_prompt()  # 生成系统提示
        self.messages.append({'role': 'system',  # 添加系统消息
                              'content': self.system_prompt})
        self.action_apace = self.get_action_space()  # 获取动作空间
        self.messages.extend(example_message)  # 添加示例消息
        self.messages.append({'role': 'user',  # 添加用户消息
                              'content': self.generate_first_user_prompt(task=self.task)})

    def generate_system_prompt(self):
        """
        生成系统提示
        :return: 格式化后的系统提示
        """
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
        }  # 替换字典，用于模板替换
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    def generate_first_user_prompt(self, task):
        """
        生成第一个用户提示
        :param task: 任务内容
        :return: 格式化后的用户提示
        """
        user_prompt = USER_FIRST
        replace_dict = {
            '{{task}}': str(task)  # 替换任务内容
        }
        return generate_prompt(template=user_prompt, replace_dict=replace_dict)

    def add_over_prompt(self, observation):
        """
        添加结束提示
        :param observation: 观察结果
        """
        user_prompt = USER_OVER_PROMPT
        replace_dict = {
            '{{observation}}': observation  # 替换观察结果
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)
        self.messages.append({'role': 'user', 'content': prompt})  # 添加用户消息

    def add_result_prompt(self, observation):
        """
        添加结果提示
        :param observation: 观察结果
        """
        user_prompt = USER_OVER_PROMPT
        replace_dict = {
            '{{observation}}': observation,  # 替换观察结果
            '{{task}}': str(self.task)  # 替换任务内容
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)
        self.messages.append({'role': 'user', 'content': prompt})  # 添加用户消息

    def generate_subtasks(self):

        """
        生成子任务
        :return: 子任务列表
        """
        self.get_response()  # 获取响应
        return self.subtasks  # 返回子任务列表

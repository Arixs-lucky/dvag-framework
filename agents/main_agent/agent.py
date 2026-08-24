from agents.main_agent.prompt import SYSTEM_PROMPT, USER_FIRST, USER_OVER_PROMPT, USER_PROMPT, EXAMPLE_MESSAGES
from agents.base_agent import BaseAgent
from utils.prompt import generate_prompt


class MainAgent(BaseAgent):
    def __init__(self, task, record_path=None, model_name='gpt-3.5-turbo-0613', proxy='http://127.0.0.1:10809',example_message=EXAMPLE_MESSAGES, api_interval=20):
        """
        初始化MainAgent类
        :param task: 要执行的任务
        :param record_path: 记录路径
        :param model_name: 使用的模型名称，默认为'gpt-3.5-turbo-0613'
        :param proxy: 代理地址，默认为'http://127.0.0.1:10809'
        :param example_message: 示例消息，默认为EXAMPLE_MESSAGES
        :param api_interval: API调用间隔时间，默认为20
        """
        super().__init__(record_path=record_path, model_name=model_name, proxy=proxy,api_interval=api_interval)
        self.task = task  # 存储任务
        self.subtasks = []  # 子任务列表
        self.completed_tasks = []  # 已完成任务列表
        self.system_prompt = self.generate_system_prompt()  # 生成系统提示
        # 将系统提示添加到消息列表中
        self.messages.append({'role': 'system',
                              'content': self.system_prompt})
        self.action_apace = self.get_action_space()  # 获取动作空间
        self.messages.extend(example_message)  # 添加示例消息
        # 生成并添加第一个用户提示
        self.messages.append({'role': 'user',
                              'content': self.generate_first_user_prompt(task=self.task)})

    def generate_system_prompt(self):
        """
        生成系统提示
        :return: 生成的系统提示
        """
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
        }
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    def generate_first_user_prompt(self, task):
        """
        生成第一个用户提示
        :param task: 任务内容
        :return: 生成的用户提示
        """
        user_prompt = USER_FIRST
        replace_dict = {
            '{{task}}': task
        }
        return generate_prompt(template=user_prompt, replace_dict=replace_dict)

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
        self.messages.append({'role': 'user', 'content': prompt})

    def add_over_prompt(self):
        """
        添加结束提示
        """
        self.messages.append({'role': 'user', 'content': USER_OVER_PROMPT})
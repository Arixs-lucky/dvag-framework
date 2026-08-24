from agents.plan_and_execute.executor.prompt import SYSTEM_PROMPT, MAX_ITER, USER_PROMPT, USER_OVER_PROMPT \
    , USER_ERROR_PROMPT, USER_FIRST_PROMPT
from agents.base_agent import BaseAgent

from utils.code import get_content
from utils.prompt import generate_prompt


class Executor(BaseAgent):
    def __init__(self, action, total_task, current_task, completed_task, record_path=None,
                 model_name='gpt-3.5-turbo-0613', proxy='http://127.0.0.1:10809',api_interval=20):

        """
        初始化执行器类
        :param action: 执行的动作类型
        :param total_task: 总任务数量
        :param current_task: 当前任务
        :param completed_task: 已完成的任务
        :param record_path: 记录路径
        :param model_name: 使用的模型名称
        :param proxy: 代理服务器地址
        :param api_interval: API调用间隔时间
        """
        super().__init__(record_path, model_name, proxy, api_interval=api_interval)  # 调用父类初始化方法
        self.total_task = total_task  # 设置总任务数
        self.subtasks = []  # 初始化子任务列表
        self.completed_tasks = []  # 初始化已完成任务列表

        # 生成系统提示并设置初始消息
        self.system_prompt = self.generate_system_prompt(action=action, total_task=total_task,
                                                         current_task=current_task,
                                                         completed_task=completed_task)
        self.action_apace = self.get_action_space()  # 获取动作空间
        self.messages.append({'role': 'system',  # 添加系统消息
                              'content': self.system_prompt})
        self.messages.append({'role': 'user',  # 添加用户消息
                              'content': self.generate_first_user_prompt(current_task=current_task)})

    def generate_first_user_prompt(self, current_task):
        """
        生成第一个用户提示
        :param current_task: 当前任务
        :return: 格式化后的用户提示
        """
        user_prompt = USER_FIRST_PROMPT
        replace_dict = {
            '{{current_task}}': str(current_task),  # 替换当前任务占位符
            '{{action_space}}': self.get_action_space()  # 替换动作空间占位符
        }
        return generate_prompt(template=user_prompt, replace_dict=replace_dict)  # 生成并返回提示

    def generate_system_prompt(self, action, total_task, current_task, completed_task):
        """
        生成系统提示
        :param action: 执行的动作类型
        :param total_task: 总任务数量
        :param current_task: 当前任务
        :param completed_task: 已完成的任务
        :return: 格式化后的系统提示
        """
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
            '{{action}}': action,  # 替换动作类型占位符
            '{{max_iter}}': str(MAX_ITER),  # 替换最大迭代次数占位符
            '{{total_task}}': str(total_task),  # 替换总任务数占位符
            '{{current_task}}': str(current_task),  # 替换当前任务占位符
            '{{completed_task}}': str(completed_task)  # 替换已完成任务占位符
        }
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)  # 生成并返回系统提示


    def add_user_prompt(self, observation):
        """
        添加用户提示
        :param observation: 观察结果
        """
        user_prompt = USER_PROMPT
        replace_dict = {
            '{{observation}}': observation,  # 替换观察结果占位符
            '{{action_space}}': str(self.action_apace)  # 替换动作空间占位符
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)  # 生成提示
        print(f'user prompt={prompt}')  # 打印生成的提示
        self.messages.append({'role': 'user', 'content': prompt})  # 将提示添加到消息列表

    def add_user_error_prompt(self, observation):
        """
        添加用户错误提示
        :param observation: 观察结果
        """
        user_prompt = USER_ERROR_PROMPT
        replace_dict = {
            '{{observation}}': observation,  # 替换观察结果占位符
        }
        prompt = generate_prompt(template=user_prompt, replace_dict=replace_dict)  # 生成提示
        print(f'user prompt={prompt}')  # 打印生成的提示
        self.messages.append({'role': 'user', 'content': prompt})  # 将提示添加到消息列表

    def add_over_prompt(self):

        """添加结束提示"""
        self.messages.append({'role': 'user', 'content': USER_OVER_PROMPT})  # 将结束提示添加到消息列表

    def get_result(self, text):

        """
        从文本中提取结果
        :param text: 包含结果的文本
        :return: 提取的结果内容
        """
        return get_content(text, begin_str='<result>', end_str='</result>')  # 使用开始和结束标记提取结果

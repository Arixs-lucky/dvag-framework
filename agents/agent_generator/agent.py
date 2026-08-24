import json

from agents.agent_generator.prompt import SYSTEM_PROMPT, TOTAL_TASK, CURRENT_TASK, COMPLETED_TASK, ORIGINAL_DOCUMENT, \
    USER_FIRST_PROMPT, EXAMPLE_MESSAGES
from agents.base_agent import BaseAgent
from utils.api_service import chat_gpt
from utils.code import get_content_list
from utils.prompt import generate_prompt
import copy


class AgentGenerator(BaseAgent):
    def __init__(self, total_task, current_task, completed_task, record_path=None, model_name='gpt-3.5-turbo-0613',
                 proxy='http://127.0.0.1:10809'):
        # 初始化父类，设置记录路径、模型名称和代理
        super().__init__(record_path, model_name, proxy)
        # 生成系统提示并添加到消息历史中
        self.system_prompt = self.generate_system_prompt()
        self.messages.append({'role': 'system',
                              'content': self.system_prompt})
        # 添加示例消息到消息历史中
        self.messages.extend(EXAMPLE_MESSAGES)
        # 生成第一个用户提示并添加到消息历史中
        self.messages.append({'role': 'user',
                              'content': self.generate_first_user_prompt(total_task=total_task,
                                                                         current_task=current_task,
                                                                         completed_task=completed_task)})


    def generate_system_prompt(self):
        """
        生成系统提示的函数
        返回:
            str: 返回替换占位符后的系统提示
        """
        # 定义替换字典（当前 被注释掉的变量可能需要在其他地方设置）
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
            # '{{total_task}}': str(total_task),
            # '{{current_task}}': str(current_task),
            # '{{completed_task}}': str(completed_task)
        }
        # 使用模板生成器生成提示
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    def generate_first_user_prompt(self, total_task, current_task, completed_task):
        """
        生成第一个用户提示的函数
        此函数用于根据任务信息生成初始的用户提示，通过替换模板中的占位符来实现
        参数:
            total_task: 总任务数
            current_task: 当前任务
            completed_task: 已完成的任务
        返回:
            str: 返回替换占位符后的用户提示
        """
        # 获取用户提示模板
        user_prompt = USER_FIRST_PROMPT
        # 定义需要替换的占位符及其对应的值
        replace_dict = {
            '{{total_task}}': total_task,
            '{{current_task}}': current_task,
            '{{completed_task}}': completed_task
        }
        # 使用模板生成器生成提示
        return generate_prompt(template=user_prompt, replace_dict=replace_dict)

    def generate_agent_prompt(self, generate=False):
        """
        生成代理提示的函数
        参数:
            generate (bool): 是否生成新的提示，默认为False
        返回:
        str: 返回生成的提示或原始文档
        """
        # 如果不生成新提示，直接返回原始文档
        if not generate:
        # 如果不生成新提示，直接返回原始文档
            return ORIGINAL_DOCUMENT
        else:
        # 调用ChatGPT生成响应
            response = chat_gpt(self.messages, model_name=self.model_name, proxy=self.proxy)
        # 将响应添加到消息历史中
            self.messages.append(response)
        # 如果设置了记录路径，将消息历史保存到文件
            if self.record_path is not None:
                with open(self.record_path, 'w', encoding='utf-8') as f:
                    json.dump(self.messages, f, indent=4, ensure_ascii=False)
        # 从响应内容中提取新的提示
            new_prompts = get_content_list(response['content'], begin_str='<action document>', end_str='</action document>')
        # 如果没有提取到新提示，返回原始文档
            if len(new_prompts) == 0:
                return ORIGINAL_DOCUMENT
        # 返回第一个提取到的新提示
            return new_prompts[0]

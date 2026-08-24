from agents.verify_agent.prompt import SYSTEM_PROMPT
from agents.base_agent import BaseAgent
from utils.prompt import generate_prompt


class VerifyAgent(BaseAgent):
    def __init__(self, total_task, current_task, completed_task, process, result, record_path=None,
                 model_name='gpt-3.5-turbo-0613', proxy='http://127.0.0.1:10809'):
        """
        初始化验证代理
        参数:
            total_task (str): 总任务描述
            current_task (str): 当前任务描述
            completed_task (str): 已完成任务描述
            process (str): 处理过程描述
            result (str): 结果描述
            record_path (str, optional): 记录路径，默认为None
            model_name (str, optional): 模型名称，默认为'gpt-3.5-turbo-0613'
            proxy (str, optional): 代理地址，默认为'http://127.0.0.1:10809'
        """
        # 调用父类初始化方法
        super().__init__(record_path, model_name, proxy)
        # 添加系统角色消息，包含生成的系统提示
        self.messages.append({'role': 'system',
                              'content': self.generate_system_prompt(total_task=total_task, current_task=current_task,
                                                                     completed_task=completed_task, process=process,
                                                                     result=result)})
        # 添加用户角色消息，开始对话
        self.messages.append({'role': 'user',
                              'content': 'Start.'})

    def generate_system_prompt(self, total_task, current_task, completed_task, process, result):
        """
        生成系统提示
        参数:
            total_task (str): 总任务描述
            current_task (str): 当前任务描述
            completed_task (str): 已完成任务描述
            process (str): 处理过程描述
            result (str): 结果描述
        返回:
            str: 生成的系统提示
        """
        # 使用基础系统提示模板
        system_prompt = SYSTEM_PROMPT
        # 创建替换字典，用于模板替换
        replace_dict = {
            '{{total_task}}': total_task,
            '{{current_task}}': str(current_task),
            '{{completed_task}}': str(completed_task),
            '{{process}}': process,
            '{{result}}': result
        }
        # 生成并返回替换后的提示
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

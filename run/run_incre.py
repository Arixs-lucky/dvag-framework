# 导入必要的库
"""
智能旅行规划系统
该系统使用多智能体架构来处理复杂的旅行规划任务，包括任务分解、执行、验证和更新。
主要功能包括：
1. 使用多个专业智能体（MainAgent, SubAgent, VerifyAgent等）协作完成旅行规划
2. 支持任务分解和递归执行
3. 提供技能库管理和动态更新功能
4. 包含旅行模拟器用于验证和评分
5. 支持多种执行模式和调度策略
"""

# 标准库导入
import copy  # 用于深拷贝操作
import json  # 用于JSON数据处理
import os  # 用于操作系统相关功能
import sys  # 用于系统相关功能
import time  # 用于时间相关功能

# 第三方库导入
import io  # 修复 Windows 控制台 Unicode 编码问题
# 导入项目模块
from agents.main_agent.prompt import EXAMPLE_MESSAGES
from agents.main_agent.agent import MainAgent
from agents.agent_generator.agent import AgentGenerator
from agents.sub_agent.agent import SubAgent
from agents.sub_agent.prompt import MAX_ITER
from task.travel.simulator import TravelSimulator
from utils.config_manager import ConfigManager
from utils.retrieve import get_prompt, get_similarity
from utils.code import get_content_list
from utils.file import get_json_refined
from agents.verify_agent.agent import VerifyAgent
from agents.update_agent.agent import UpdateAgent
# 修复 Windows 控制台 Unicode 编码问题
import io

from agents.main_agent.prompt import EXAMPLE_MESSAGES

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import openai
from agents.main_agent.agent import MainAgent
from agents.agent_generator.agent import AgentGenerator
from agents.sub_agent.agent import SubAgent
from agents.sub_agent.prompt import MAX_ITER
from task.travel.simulator import TravelSimulator
from utils.config_manager import ConfigManager
from utils.retrieve import get_prompt
from utils.code import get_content_list
from utils.file import get_json_refined
from utils.retrieve import get_prompt, get_similarity
from agents.verify_agent.agent import VerifyAgent
from agents.update_agent.agent import UpdateAgent

# ---- 加载 LLM 配置 ----
# 导入sys模块，用于与Python解释器交互
import sys
# 将当前文件所在目录添加到系统路径中，以便导入同级目录下的模块
sys.path.insert(0, os.path.dirname(__file__))
# 从llm_config模块中导入多个配置项
from llm_config import (
    LLM_BACKEND, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL,
    API_INTERVAL, PROXY, HF_ENDPOINT,
)
# 设置大语言模型(LLM)相关环境变量
# 配置LLM后端
os.environ['LLM_BACKEND'] = LLM_BACKEND
# 配置LLM基础URL
os.environ['LLM_BASE_URL'] = LLM_BASE_URL
# 配置LLM API密钥
os.environ['LLM_API_KEY'] = LLM_API_KEY
# 配置LLM模型名称
os.environ['LLM_MODEL'] = LLM_MODEL
# 配置HuggingFace国内镜像端点
os.environ['HF_ENDPOINT'] = HF_ENDPOINT  # HuggingFace 国内镜像
# 从utils.api_service模块导入set_keys函数
from utils.api_service import set_keys

# 创建配置管理器实例
config_manager = ConfigManager()
# 如果启用了代理设置
if PROXY:
    # 设置代理配置，包括HTTP和HTTPS代理
    # 这里使用相同的代理地址同时设置HTTP和HTTPS代理
    config_manager.set_proxies(PROXY, PROXY)

max_error_times = 3  # 最大错误尝试次数
max_depth = 2  # 最大递归深度
model_name = LLM_MODEL  # 使用配置的模型名
agent_id = 1  # 智能体ID计数器
sub_max_iter = MAX_ITER  # 子智能体最大迭代次数
method = "decompose/incre"  # 使用的分解方法
library_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'travel', 'skill.json')  # 技能库路径
interrupt = 0  # 中断标志
api_interval = API_INTERVAL  # 从配置读取
# 初始化阈值参数theta，用于后续可能的条件判断
theta = 0.7
# 设置是否使用详细模式的标志，初始为False
use_detail = False
# 打开文件'run_incre.txt'用于写入输出，使用utf-8编码
output = open('run_incre.txt', 'w', encoding='utf-8')
# 将标准输出重定向到打开的文件
sys.stdout = output
# 设置是否进行扩展的标志，初始为True
extend = True
# 定义扩展结束的列表，包含三个数值
extend_ends = [32, 32, 57]

# 导入旅行工具模块中的函数
from utils.travel import query_database, execute_sql, execute_python, is_error, check_plan_format

# 使用with语句打开文件，确保文件正确关闭
with open(library_path, 'r', encoding='utf-8') as f:
    # 从JSON文件中加载数据并转换为列表
    skills_save = list(json.load(f))

# 创建skills_save的深拷贝，确保原始数据不被修改
skills = copy.deepcopy(skills_save)


def check_item(agent_file):
    """
    检查代理文件中的任务完成情况并验证结果
    参数:
        agent_file (str): 代理文件的路径
    返回:
        bool: 任务验证是否成功
    """
    # 使用utf-8编码打开并读取代理文件
    with open(agent_file, 'r', encoding='utf-8') as f:
        # 将文件内容加载为JSON列表
        messages = list(json.load(f))
    # 获取任务消息和结果消息
    task_message = messages[0]['content']
    result_message = messages[-1]['content']
    # 从任务消息中提取当前任务
    current_tasks = get_content_list(task_message, begin_str='And the subtask you need to complete is:',
                                     end_str='\n\n\n')
    # 从任务消息中提取整体任务
    overall_tasks = get_content_list(task_message, begin_str='The total task is: \n',
                                     end_str='\n\n')
    # 从任务消息中提取已完成的任务部分
    completed_taskss = get_content_list(task_message, begin_str='The part that has been completed is \n',
                                        end_str='\n\n')
    # 从结果消息中提取结果
    results = get_content_list(result_message, begin_str='<result>',
                               end_str='</result>')
    # 从结果消息中提取过程
    processes = get_content_list(result_message, begin_str='process>',
                                 end_str='</process>')
    # 检查所有必要的内容是否存在
    # 检查多个列表是否都不为空
    if not (len(current_tasks) > 0 and len(overall_tasks) > 0 and len(completed_taskss) > 0 and len(
            results) > 0 and len(processes) > 0):
        # 如果任一列表为空，打印提示信息
        print(f'content not found in {agent_file}')
        # 打印各列表是否为空的状态列表（True表示不为空，False表示为空）
        print(
            f'{[len(current_tasks) > 0, len(overall_tasks) > 0, len(completed_taskss) > 0, len(results) > 0, len(processes) > 0]}')
        # 返回False表示检查未通过
        return False

    # 获取第一个任务和结果
    # 获取当前任务列表中的第一个任务
    current_task = current_tasks[0]
    # 获取整体任务列表中的第一个任务
    overall_task = overall_tasks[0]
    # 获取已完成任务列表中的第一个任务
    completed_tasks = completed_taskss[0]
    # 获取结果列表中的第一个结果
    result = results[0]
    # 获取进程列表中的第一个进程
    process = processes[0]

    # 创建验证代理实例
    verify_agent = VerifyAgent(model_name=model_name, total_task=overall_task,
                               current_task=current_task,
                               completed_task=completed_tasks,
                               process=process, result=result, record_path=f'{agent_file[:-5]}_verify.json')
    # 获取验证响应
    response = verify_agent.get_response()
    text = response['content']
    # 解析响应中的函数调用
    functions = verify_agent.parse_functions(text)
    # 根据函数调用结果返回相应的验证状态
    # 检查functions列表是否为空，或者第一个元素的function_name是否为'success'
    if len(functions) == 0 or functions[0]['function_name'] == 'success':
        # 如果条件满足，打印成功信息，并返回True
        print(f'{agent_file} success')
        return True
    # 如果第一个元素的function_name为'fail'
    elif functions[0]['function_name'] == 'fail':
        # 打印失败信息，并返回False
        print(f'{agent_file} fail')
        return False
    # 默认情况下返回False
    return False


def generate_solution(agent_file, output_file):
    # 创建一个SubAgent实例，传入相关参数
    # action: 当前执行的动作
    # total_task: 总任务描述
    # current_task: 当前任务描述
    # completed_task: 已完成任务记录
    # record_path: 输出文件路径
    # model_name: 使用的模型名称
    subagent = SubAgent(action="", total_task="", current_task="", completed_task="", record_path=output_file,
                        model_name=model_name)
    # 从JSON文件加载SubAgent的数据
    subagent.load_from_json(agent_file)
    # 添加解决方案提示到SubAgent中
    subagent.add_solution_prompt()
    # 获取SubAgent的响应内容
    text = subagent.get_response()['content']
    # 返回生成的解决方案文本
    return text


def extend_skill(agent_file, theta=0.7, max_similar_count=2):

    """
    扩展技能函数，用于根据现有技能和新的任务描述来更新或添加技能

    参数:
        agent_file (str): 代理文件路径
        theta (float): 相似度阈值，默认为0.7
        max_similar_count (int): 最大相似技能数量，默认为2
    """
    global interrupt  # 全局中断计数器
    if interrupt > 0:
        interrupt -= 1  # 减少中断计数
        return  # 如果有中断请求，则提前返回

    # 检查代理文件是否存在
    if os.path.exists(agent_file):
        print(f'extend kill in {agent_file}')  # 打印处理信息
        with open(agent_file, 'r', encoding='utf-8') as f:
            data = json.load(f)  # 加载JSON数据
        # 从数据中提取任务消息和子任务
        task_message = data[0]['content']
        sub_tasks = get_content_list(task_message, begin_str='And the subtask you need to complete is:',
                                     end_str='\n\n\n')
        # 从数据中提取结果消息和处理过程
        result_message = data[-1]['content']
        processes = get_content_list(result_message, begin_str='<process>', end_str='</process>')
        # 确保子任务和处理过程都存在
        if len(sub_tasks) > 0 and len(processes) > 0:
            try:
                global skills  # 全局技能列表

                # 获取第一个子任务的JSON格式
                sub_task = get_json_refined(sub_tasks[0])

                # 构建任务详情字典
                task_detail = {'subtask_name': sub_task['subtask_name'], 'goal': sub_task['goal']}
                if 'result_format' in sub_task:
                    task_detail['result_format'] = sub_task['result_format']
                task_name = sub_task['subtask_name']
                similar_count = 0  # 相似技能计数器
                # 遍历现有技能，计算相似度
                for idx_e, existing_skill in enumerate(skills):
                    if get_similarity(existing_skill['task_name'], task_name) > theta:
                        print(f"sim>{theta}\n{existing_skill['task_name']}\n{task_name}")
                        similar_count += 1
                        if similar_count >= max_similar_count:
                            break
                print(f"{sub_task['subtask_name']}:sim_count={similar_count}")

                # 检查项目状态
                if not check_item(agent_file=agent_file):
                    return

                # 生成解决方案
                solution_text = generate_solution(agent_file=agent_file, output_file=agent_file[:-5] + "_sol.json")
                solutions = get_content_list(solution_text, begin_str='<solution>', end_str='</solution>')
                if len(solutions) == 0:
                    print("solution not found")
                    return
                solution = solutions[0]

                # 如果相似技能数量达到阈值，则更新现有技能
                if similar_count >= max_similar_count:
                    update_agent = UpdateAgent(task1=existing_skill['task_detail'],
                                               solution1=existing_skill['solution'],
                                               task2=task_detail,
                                               solution2=solution,
                                               record_path=f'{agent_file[:-5]}_update.json')
                    new_solution = update_agent.get_new_solution()
                    # update
                    if skills[idx_e]['solution'] != new_solution:
                        print(f"update {skills[idx_e]}: {new_solution}")
                    skills[idx_e]['solution'] = new_solution
                else:
                    skills.append(
                        {'task_name': sub_task['subtask_name'], 'task_detail': str(task_detail),
                         'solution': solution})
                    print(f"add: {skills[-1]}")
            except Exception as e:
                print("exception", e)


def over():
    """
    该函数返回一个格式化的提示字符串，用于以特定格式表达已确认的计划部分。
    提示字符串包含四种可能的计划格式：
    1. go_to_place: 表示从一个地点到另一个地点的行程
    2. visit: 表示在某个地点的访问时间
    3. go_to_city: 表示从一个城市到另一个城市的行程，需要提供票据号码
    4. stay_in: 表示在某个城市的停留时间
    时间格式要求为"%Y-%m-%d %H:%M"，例如2023-07-02 16:00。
    每个计划部分需要被<plan>和</plan>标签包围。
    """
    summary_prompt = '''Please express the part of the plan that has been confirmed in chronological order in the following formats:
    1.go_to_place(origin:str,destination:str,departure_time,arrival_time): go to destination from origin.
    2.visit(place:str,begin_time,end_time): visit somewhere from begin_time to end_time. The time should be expressed\
     as "%Y-%m-%d %H:%M", e.g. 2023-07-02 16:00.
    3.go_to_city(origin_city:str,destination_city:str,departure_time,arrival_time,ticket_number): go to destination city from origin city, using the ticket with the ticket_number(you have known the ticket number from the database).
    4.stay_in(city:str,begin_time,end_time): stay in somewhere from begin_time to end_time. The time should be expressed\
     as "%Y-%m-%d %H:%M".
    You should surround the action between <plan> and </plan> such as <plan>go_to_place(\"Beijing Railway Hotel\",\"The Great Wall\",\
    \"2023-07-02 7:00\",\"2023-07-02 8:05\")</plan>, <plan>visit(\"Great Wall\",\
    \"2023-07-02 8:05\",\"2023-07-05 17:00\")</plan>,<plan>go_to_city(\"Shanghai\",\"Beijing\",\
    \"2023-07-02 16:00\",\"2023-07-02 22:30\",\"D1111\")</plan>, <plan>stay_in(\"Beijing\",\
    \"2023-07-02 22:30\",\"2023-07-05 8:00\")</plan>
    '''
    return summary_prompt


def invoke_function(func_data):
    # 通过函数名从全局命名空间中获取函数对象
    func = globals()[func_data['function_name']]
    # 使用传入的参数调用函数
    result = func(*func_data['args'])
    # 返回函数执行结果
    return result


def subagent_handle2(overall_task, completed_tasks, current_task, verify=False, depth=1, output_path='.'):
    """
    处理子任务的函数，通过递归方式分解和执行任务
    参数:
        overall_task (str): 整体任务描述
        completed_tasks (list): 已完成的任务列表
        current_task (dict): 当前要处理的任务，包含子任务名称和目标等信息
        verify (bool): 是否需要验证结果，默认为False
        depth (int): 当前递归深度，默认为1
        output_path (str): 输出文件路径，默认为当前目录
    返回:
        str: 任务执行结果
    """
    # 检查是否达到最大递归深度
    if depth > max_depth:
        return 'Cannot decompose anymore'

    # 打印当前函数调用的参数信息
    print(f'\nsubagent_handle2({overall_task},{completed_tasks}, {current_task}, {verify},{depth},{output_path})\n')
    # 声明全局变量agent_id
    global agent_id
    # 创建代理生成器，用于生成新的代理
    agent_generator = AgentGenerator(model_name=model_name, total_task=overall_task, completed_task=completed_tasks,
                                     current_task=current_task,
                                     record_path=f'{output_path}/agent_generator_{agent_id}.json')
    # 生成代理提示
    modified_prompt = agent_generator.generate_agent_prompt(generate=True)

    # 创建子代理文件路径
    subagent_file = f'{output_path}/sub_agent_{agent_id}.json'
    # 创建子代理实例
    subagent = SubAgent(model_name=model_name, action=modified_prompt, total_task=overall_task,
                        current_task=current_task,
                        completed_task=completed_tasks, record_path=subagent_file, api_interval=api_interval)
    # 构建任务详情字典
    task_detail = {'subtask_name': current_task['subtask_name'], 'goal': current_task['goal']}
    # 如果当前任务包含结果格式，则添加到任务详情中
    if 'result_format' in current_task:
        task_detail['result_format'] = current_task['result_format']

    # 向子代理的消息中添加提示信息
    subagent.messages[0]['content'] += get_prompt(task_name=current_task['subtask_name'], task_detail=str(task_detail),
                                                  solution_num=2, rewrite=True, example_file=library_path, theta=theta,
                                                  use_detail=use_detail)
    # 增加代理ID计数器
    agent_id += 1
    # 初始化当前子任务迭代次数
    cur_sub_iter = 0
    try:
        # 初始化错误次数计数器
        error_times = 0
        # 开始子任务循环处理
        while cur_sub_iter < sub_max_iter:
            try:
                # 打印当前迭代次数
                print(f'cur_iter={cur_sub_iter}')
            except Exception:
                pass
            # 增加迭代次数
            cur_sub_iter += 1
            # 获取子代理的响应
            response = subagent.get_response()
            # 打印响应内容的前200个字符
            print(f'response {json.dumps(response, ensure_ascii=False)[:200]}')
            # 从响应中解析函数调用
            text = response['content']
            functions = subagent.parse_functions(text)

            try:
                # 打印解析的函数
                print(f'functions={functions}')
            except Exception:
                pass
            # 如果没有解析到函数
            if len(functions) == 0:
                print('no action')
                # 向子代理添加提示信息
                subagent.messages.append(
                    {'role': 'user',
                     'content': f'Available Actions:{subagent.action_apace}\nGive me the action between <action> and </action>.'})
                # 再次获取响应
                response = subagent.get_response()
                try:
                    # 打印响应内容的前200个字符
                    print(f'response {json.dumps(response, ensure_ascii=False)[:200]}')
                except Exception:
                    pass
                text = response['content']
                # subagent.subtasks.extend(subagent.get_subtasks(text))
                functions = subagent.parse_functions(text)

            observation = 'No valid action found. Surround it by <action> and </action>'
            exec_function = None
            for function in functions:
                try:
                    if function['function_name'] == 'over':
                        break
                    elif function['function_name'] == 'subagent_handle':
                        function['args'].append(subagent)
                        function['args'].append(output_path)
                        function['args'].append(depth + 1)

                        subtask_name = function['args'][0]
                        subtask_idx = subagent.get_subtask_idx(subtask_name)
                        subagent.subtasks[subtask_idx]['result'] = observation

                    observation = invoke_function(function)
                    exec_function = function
                    break
                except Exception as e:
                    observation = f'{e}. No valid action found. Surround it by <action> and </action>. Make sure to pass in the correct parameters'
                    print(e)
            if is_error(observation):
                if "is not defined" in observation:
                    observation = observation + "The interpreter does not store previous code or variables. So you should define the variable before your code."
                error_times += 1
            else:
                error_times = 0
            if error_times >= max_error_times:
                name = exec_function['function_name']
                subagent.messages = subagent.messages[:-((max_error_times - 1) * 2)]
                observation = f"For some unknown reason, this step cannot be completed with {name}. Try to solve this problem yourself."

            try:
                print(f'observation {observation}')
            except Exception:
                pass
            if len(functions) > 0 and functions[0]['function_name'] == 'over':
                subagent.add_over_prompt()
                response = subagent.get_response()
                try:
                    print(f'response {json.dumps(response, ensure_ascii=False)[:200]}')
                except Exception:
                    pass
                text = response['content']

                result = subagent.get_result(text)
                process = subagent.get_process(text)
                if verify:
                    verify_agent = VerifyAgent(model_name=model_name, total_task=overall_task,
                                               current_task=current_task,
                                               completed_task=completed_tasks,
                                               process=process, result=result,
                                               record_path=f'verify_agent_{agent_id}.json')
                    response = verify_agent.get_response()
                    text = response['content']
                    functions = verify_agent.parse_functions(text)
                    if len(functions) == 0 or functions[0]['function_name'] == 'success':
                        pass
                    elif functions[0]['function_name'] == 'fail':
                        subagent.add_verify_prompt(check_ans=functions[0]['args'][0])
                        response = subagent.get_response()
                        text = response['content']
                if extend:
                    extend_skill(agent_file=subagent_file)
                break
            if error_times > 0:
                subagent.add_user_error_prompt(observation)
            else:
                subagent.add_user_prompt(observation)
    except openai.error.InvalidRequestError as e:
        print(f'{e} InvalidRequestError. Context length error?')
        for idx in range(len(subagent.messages) - 1, 0, -1):
            if subagent.messages[idx]["role"] == "user":
                break
        subagent.messages = subagent.messages[:idx - 2]  # 从后往前删掉idx:user, idx-1:assistant, idx-2:user
        subagent.messages.append({'role': 'user',
                                  'content': 'Give me the result immediately. Surrounded it with <result> and </result>'})
        response = subagent.get_response()
        text = response['content']

    if cur_sub_iter >= sub_max_iter:
        subagent.messages[-1] = {'role': 'user',
                                 "content": "Give me the final result of the subtask immediately, regardless of whether certain restrictions are met. Surrounded it with <result> and </result> If all conditions cannot be perfectly met, please return a result that is as appropriate as possible instead of an empty result."
                                 }
        response = subagent.get_response()
        text = response['content']

    result = subagent.get_result(text)
    return result


def subagent_handle(task_name, agent: MainAgent, output_path, depth=1):
    print(f'subagent_handle({task_name} {agent})')
    overall_task = agent.task
    completed_tasks = agent.completed_tasks
    current_task = None
    for subtask in agent.subtasks:
        if subtask['subtask_name'] == task_name:
            current_task = subtask
    if current_task is None:
        from agents.main_agent.prompt import subtask_format
        return f'''Cannot find a subtask named {task_name}.
make sure that a subtask-structure has the following json component and surrounded with <subtask></subtask> as follows:
{subtask_format}'''
    else:
        result = subagent_handle2(overall_task=overall_task, completed_tasks=completed_tasks, current_task=current_task,
                                  output_path=output_path, depth=depth)
        completed_task = copy.deepcopy(current_task)
        completed_task['result'] = result
        agent.completed_tasks.append(completed_task)
        return result


def run_item(task, output_path="."):
    global skills, skills_save
    skills = copy.deepcopy(skills_save)

    max_iter = 10
    global agent_id
    if type == 3:
        from agents.main_agent.prompt import EXAMPLE_MESSAGES_3
        main_agent = MainAgent(model_name=model_name, task=task,
                               record_path=f'{output_path}/main_agent_{agent_id}_record.json',
                               example_message=EXAMPLE_MESSAGES_3)
    elif type == 2:
        from agents.main_agent.prompt import EXAMPLE_MESSAGES_2
        main_agent = MainAgent(model_name=model_name, task=task,
                               record_path=f'{output_path}/main_agent_{agent_id}_record.json',
                               example_message=EXAMPLE_MESSAGES_2)
    else:
        from agents.main_agent.prompt import EXAMPLE_MESSAGES
        main_agent = MainAgent(model_name=model_name, task=task,
                               record_path=f'{output_path}/main_agent_{agent_id}_record.json',
                               example_message=EXAMPLE_MESSAGES)

    agent_id += 1
    cur_iter = 0
    completed = False
    try:
        while cur_iter < max_iter:
            cur_iter += 1
            response = main_agent.get_response()
            text = response['content']
            functions = main_agent.parse_functions(text)
            if len(functions) == 0:
                print('no action')
                main_agent.messages.append(
                    {'role': 'user',
                     'content': f'Available actions:{main_agent.get_action_space()}\nGive me the action between <action> and </action>.'})
                response = main_agent.get_response()
                text = response['content']
                functions = main_agent.parse_functions(text)

            if len(functions) == 0:
                functions.append({'function_name': 'over', 'args': []})

            if functions[0]['function_name'] == 'subagent_handle':
                functions[0]['args'].append(main_agent)
                functions[0]['args'].append(output_path)
                observation = invoke_function(functions[0])
                main_agent.add_user_prompt(observation)

                subtask_name = functions[0]['args'][0]
                subtask_idx = main_agent.get_subtask_idx(subtask_name)
                if subtask_idx >= 0:
                    main_agent.subtasks[subtask_idx]['result'] = observation

            elif functions[0]['function_name'] == 'over':
                completed = True
                main_agent.add_over_prompt()
                response = main_agent.get_response()
                text = response['content']
                break
            else:
                main_agent.messages.append(
                    {'role': 'user',
                     'content': f'No valid action Found. Available actions:{main_agent.get_action_space()}\nGive me the action between <action> and </action>.'})

        if cur_iter >= max_iter:
            main_agent.add_over_prompt()
            response = main_agent.get_response()
            text = response['content']

    except openai.error.InvalidRequestError as e:
        for idx in range(len(main_agent.messages) - 1, 0, -1):
            if main_agent.messages[idx]["role"] == "user":
                break
        main_agent.messages = main_agent.messages[:idx - 2]  # 从后往前删掉idx:user, idx-1:assistant, idx-2:user
        main_agent.add_over_prompt()
        response = main_agent.get_response()
        text = response['content']

    check_result = check_plan_format(text)
    if check_result == "All formats are correct." and completed:
        skills_save = skills
        with open(library_path, 'w', encoding='utf-8') as f:
            json.dump(skills_save, f, indent=4)
        with open(f"{output_path}/skill.json", 'w', encoding='utf-8') as f:
            json.dump(skills_save, f, indent=4)

    if "No valid plan format found." in check_result:
        main_agent.messages.append({"role": "user", "content": f"{check_result}"})
        response = main_agent.get_response()
        text = response['content']
        check_result = check_plan_format(text)
    if check_result != "All formats are correct.":
        main_agent.messages.append({"role": "user", "content": f"{check_result}"})
        response = main_agent.get_response()
        text = response['content']
    plan_strs = get_content_list(text, begin_str='<plan>', end_str='</plan>')

    return plan_strs, completed


def run_item_scheduler(task, output_path="."):
    """
    基于 Scheduler 的图调度执行入口（含因果影响域修复）。

    流程：
    1. MainAgent 通过两阶段图生成构建 DiGraph
    2. Scheduler 按拓扑顺序并行调度执行
    3. 若执行失败，计算因果影响域并局部修复
    4. 最多重试 MAX_RETRY_DEPTH 次
    5. 全部成功则汇总输出

    Parameters
    ----------
    task : str
        原始任务描述。
    output_path : str
        输出路径。

    Returns
    -------
    tuple(list, bool)
        (plan_strs, completed)
    """
    from agents.main_agent.agent import MainAgent
    from agents.main_agent.decompose import build_graph_two_phase
    from agents.main_agent.repair import repair_subgraph
    from task.scheduler import Scheduler
    from utils.impact_zone import ImpactZone
    from utils.travel import check_plan_format
    from config import MAX_RETRY_DEPTH

    global agent_id

    # 初始化 MainAgent（用于图生成和修复）
    main_agent = MainAgent(
        model_name=model_name,
        task=task,
        record_path=f'{output_path}/main_agent_schedule_record.json',
        example_message=EXAMPLE_MESSAGES
    )
    agent_id += 1

    print(f'[Scheduler Mode] Generating task graph for: {task}')

    # 阶段一：通过 MainAgent.decompose 构建 DiGraph
    G = build_graph_two_phase(task, model_name=model_name, proxy=PROXY)
    print(f'[Scheduler Mode] Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges')

    # 准备 candidate_pool 和重试计数器
    candidate_pool = {}
    retry_depth = 0

    # 主执行循环（含修复重试）
    while retry_depth <= MAX_RETRY_DEPTH:
        if retry_depth > 0:
            print(f'\n[Scheduler Mode] Retry depth {retry_depth}/{MAX_RETRY_DEPTH}')
            # 重新构建调度器（图已更新）

        scheduler = Scheduler(
            G=G,
            candidate_pool=candidate_pool,
            llm_client=main_agent,
            tool_doc=None,
            skill_lib=None
        )

        # 执行调度
        print(f'[Scheduler Mode] Starting execution (retry={retry_depth})...')
        success, failed_node, failed_result = scheduler.execute()

        if success:
            print(f'[Scheduler Mode] All nodes completed successfully.')
            # 汇总结果
            return _summarize_results(G, scheduler.candidate_pool, main_agent, output_path)

        # 执行失败：计算影响域
        failed_result_dict = failed_result if isinstance(failed_result, dict) else {}
        error_msg = failed_result_dict.get('error', str(failed_result))
        
        Z = ImpactZone.compute(G, failed_node)
        print(f'[Scheduler Mode] Failed at node: {failed_node}')
        print(f'[Scheduler Mode] Error: {error_msg}')
        print(f'[Scheduler Mode] Impact zone: {sorted(Z)}')

        # 局部修复
        G = repair_subgraph(
            G, Z, candidate_pool,
            failed_node, error_msg,
            main_agent
        )

        retry_depth += 1

    # 超过重试深度
    print(f'[Scheduler Mode] Exceeded max retry depth ({MAX_RETRY_DEPTH}). Returning partial results.')
    return _summarize_results(G, scheduler.candidate_pool if 'scheduler' in dir() else candidate_pool, main_agent, output_path)


def _summarize_results(G, candidate_pool, main_agent, output_path):
    """
    汇总所有执行结果并格式化为计划字符串。

    Parameters
    ----------
    G : nx.DiGraph
        任务依赖图。
    candidate_pool : dict
        候选结果缓存。
    main_agent : MainAgent
        主智能体实例。
    output_path : str
        输出路径。

    Returns
    -------
    tuple(list, bool)
        (plan_strs, completed)
    """
    # 检查是否全部完成
    completed = all(G.nodes[n].get('status') == 'done' for n in G.nodes)

    all_results = []
    for node_id in candidate_pool:
        result_data = candidate_pool[node_id]
        desc = G.nodes[node_id].get('desc', node_id)
        all_results.append({
            'node_id': node_id,
            'desc': desc,
            'result': str(result_data)[:500] if isinstance(result_data, str) else result_data
        })

    print(f'[Scheduler Mode] Results collected: {len(all_results)} nodes, completed={completed}')
    for r in all_results:
        print(f'  [{r["node_id"]}] {r["desc"]}: {r["result"][:100]}')

    # 将结果格式化为计划字符串
    plan_strs = []
    if completed:
        for r in all_results:
            result_text = str(r['result'])
            if '<plan>' in result_text:
                plan_strs.extend(get_content_list(result_text, begin_str='<plan>', end_str='</plan>'))
            else:
                plan_strs.append(result_text)

    return plan_strs, completed


def solve_and_feedback(G, candidate_pool, task, llm_client, output_path="."):
    """
    声明式约束求解 + 反馈驱动重试闭环。

    流程：
    1. 从候选池中收集硬约束（通过 LLM 提取）
    2. 调用 MILP 求解器找出最优组合
    3. 如果最优解不可行，计算松弛向量并反馈驱动重试
    4. 最多 MAX_ITERATIONS 次迭代

    Parameters
    ----------
    G : nx.DiGraph
        任务依赖图。
    candidate_pool : dict
        节点 ID → 候选结果列表。
    task : str
        原始用户任务。
    llm_client : object
        LLM 客户端。
    output_path : str
        输出路径。

    Returns
    -------
    dict
        {'status': 'success'|'failed', 'plan': ..., 'reason': ...}
    """
    from agents.main_agent.constraints import collect_constraints  # 导入约束收集模块
    from utils.milp_solver import solve_milp, identify_expensive_nodes  # 导入MILP求解器和昂贵节点识别工具
    from config import MAX_ITERATIONS  # 导入最大迭代次数配置

    max_iterations = MAX_ITERATIONS  # 设置最大迭代次数
    iteration = 0  # 初始化迭代计数器

    while iteration < max_iterations:  # 开始迭代循环
        print(f'[Solver] Iteration {iteration + 1}/{max_iterations}')  # 打印当前迭代信息

        # 1. 收集约束
        try:
            constraints = collect_constraints(task, candidate_pool, llm_client)  # 尝试收集约束
            print(f'[Solver] Collected {len(constraints)} constraints')  # 打印收集到的约束数量
        except Exception as e:
            print(f'[Solver] Constraint collection failed: {e}')  # 打印约束收集失败信息
            return deliver_plan(candidate_pool)  # 返回候选池中的计划

        # 2. 求解 MILP
        result = solve_milp(candidate_pool, constraints)  # 调用MILP求解器

        if result['status'] == 'optimal':  # 如果找到最优解
            print(f'[Solver] Optimal solution found')  # 打印最优解找到信息
            return deliver_plan(result['solution'])  # 返回最优解

        elif result['status'] == 'infeasible':  # 如果问题无解
            delta = result.get('delta', {})  # 获取松弛向量
            budget = 'N/A'  # 初始化预算变量
            for c in constraints:  # 遍历约束
                if c.get('type') == 'sum' and 'value' in c:  # 查找总和类型的约束
                    budget = c['value']  # 获取预算值
                    break

            min_total = delta.get('min_total', 'N/A')  # 获取最小总成本
            delta_cost = delta.get('delta_cost', 0)  # 获取成本差值

            # 打印无解信息
            print(f'[Solver] Infeasible: min_total={min_total}, budget={budget}, ' +
                  f'delta_cost={delta_cost}')

            # 根据成本差值生成反馈信息
            if delta_cost <= 0:
                feedback = (
                    f"当前满足时序约束的最低总成本为 {min_total}，预算为 {budget}。"
                    f"时序约束存在冲突，请重新生成部分节点的候选方案。"
                )
            else:
                expensive_nodes = identify_expensive_nodes(candidate_pool, top_k=2)  # 识别最昂贵的节点
                feedback = (
                    f"当前满足所有时间约束的最低总成本为 {min_total} 元，"
                    f"超出预算 {delta_cost} 元。"
                    f"请针对最昂贵的子任务（{', '.join(expensive_nodes)}）生成更低成本的替代选项。"
                )

            print(f'[Solver] Feedback: {feedback}')  # 打印反馈信息

            # 如果存在昂贵节点且有依赖图，则触发修复
            if expensive_nodes and G is not None:
                for n in expensive_nodes:
                    if n in G.nodes:
                        G.nodes[n]['status'] = 'pending'  # 将节点状态设置为待处理
                    if n in candidate_pool:
                        candidate_pool[n] = []  # 清空候选池中的昂贵节点

                print('[Solver] Triggering repair for expensive nodes...')  # 打印修复触发信息
                iteration += 1  # 增加迭代次数
                continue  # 继续下一次迭代
            else:
                iteration += 1  # 增加迭代次数
                continue  # 继续下一次迭代

        else:  # 其他求解器状态
            print(f'[Solver] Unknown solver status, returning partial results')  # 打印未知状态信息
            return deliver_plan(candidate_pool)  # 返回部分结果

    # 如果达到最大迭代次数仍未解决，返回失败状态
    return {'status': 'failed', 'reason': f'exceeded max iterations ({max_iterations})'}


def deliver_plan(solution):
    """
    将选中的候选方案格式化为最终交付计划。

    Parameters
    ----------
    solution : dict
        节点 ID → 选中的候选结果。

    Returns
    -------
    dict
        {'status': 'success', 'plan': solution}
    """
    # 返回一个包含状态和计划的字典
    return {
        'status': 'success',  # 表示处理成功状态
        'plan': solution     # 原始的候选方案计划
    }


# def run(type, task_ids, extend_end=999):
#     """
#     运行旅行规划任务的主要函数
#     参数:
#         type: 数据类型标识
#         task_ids: 需要处理的任务ID列表
#         extend_end: 扩展结束的索引位置，默认为999
#     功能:
#     1. 设置项目路径和输出目录
#     2. 加载指定类型的数据
#     3. 遍历处理每个任务
#     4. 创建模拟器并执行规划
#     5. 保存预测结果
#     """
#     # 获取项目根目录路径
#     project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#     # 构建输出目录路径，包含方法、模型名和数据类型信息
#     output_dir = f'{project_root}/output/travel/{method}/{model_name}/type{type}'
#     # 构建数据文件路径
#     data_path = f'{project_root}/data/travel/data_type{type}.json'
#
#     # 打开并加载JSON数据文件
#     with open(data_path, 'r', encoding='utf-8') as file:
#         data = json.load(file)
#     # 声明全局变量extend
#     global extend
#     # 遍历处理每个数据项
#     for task_id, d in enumerate(data):
#         # 根据任务ID决定是否启用扩展模式
#         if task_id < extend_end:
#             extend = True
#         else:
#             extend = False
#         # 跳过不在指定任务ID列表中的任务
#         if task_id not in task_ids:
#             continue
#         # 打印当前任务ID和时间戳
#         print(f'data_idx={task_id}:{time.localtime()}')
#         prediction = []
#         # try:
#         global agent_id
#         agent_id = 0
#         output_path = f'{output_dir}/{task_id}'
#         if not os.path.exists(output_path):
#             os.makedirs(output_path)
#         prediction_file = f'{output_path}/prediction.json'
#         task = d['question']
#         simulator = TravelSimulator(**d['demands']['TravelSimulator'])
#         simulator.create_constraints(d['demands']['Constraints'])
#         plan_strs, completed = run_item(task=task, output_path=output_path)
#         for plan_str in plan_strs:
#             print(f'plan_str={plan_str}')
#             simulator.action(plan_str)
#         simulator.over()
#         errors = simulator.get_errors()
#         score = simulator.get_score()
#         print(f'state={simulator.state}')
#         prediction.append(
#             {"question": d['question'], "plan": plan_strs, "errors": errors, "score": score,
#              "over": completed, "state": str(simulator.state)})
#         print(f'prediction={prediction}')
#         with open(prediction_file, 'w', encoding='utf-8') as f:
#             json.dump(prediction, f, indent=4, ensure_ascii=False)


def run(type, task_ids, extend_end=999):
    """
    运行旅行规划任务的主要函数
    参数:
        type: 数据类型标识
        task_ids: 需要处理的任务ID列表
        extend_end: 扩展结束的索引位置，默认为999
    功能:
    1. 设置项目路径和输出目录
    2. 加载指定类型的数据
    3. 遍历处理每个任务
    4. 创建模拟器并执行规划
    5. 保存预测结果
    6. 输出处理进度和指标信息
    """
    # 获取项目根目录路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 构建输出目录路径，包含方法、模型名和数据类型信息
    output_dir = f'{project_root}/output/travel/{method}/{model_name}/type{type}'
    # 构建数据文件路径
    data_path = f'{project_root}/data/travel/data_type{type}.json'

    # 打开并加载JSON数据文件
    with open(data_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    # 声明全局变量extend
    global extend
    # 计算总任务数
    total_tasks = len(task_ids)
    # 统计处理进度
    processed_count = 0

    # 遍历处理每个数据项
    for task_id, d in enumerate(data):
        # 根据任务ID决定是否启用扩展模式
        if task_id < extend_end:
            extend = True
        else:
            extend = False
        # 跳过不在指定任务ID列表中的任务
        if task_id not in task_ids:
            continue

        # 打印当前任务ID和时间戳
        print(f"\n{'=' * 50}")
        print(f"正在处理第 {processed_count + 1}/{total_tasks} 条数据 (ID: {task_id})")
        print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        print(f"问题: {d['question']}")
        print(f"{'=' * 50}")

        prediction = []
        global agent_id
        agent_id = 0
        output_path = f'{output_dir}/{task_id}'
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        prediction_file = f'{output_path}/prediction.json'
        task = d['question']

        # 创建模拟器并设置约束
        simulator = TravelSimulator(**d['demands']['TravelSimulator'])
        simulator.create_constraints(d['demands']['Constraints'])

        # 执行规划任务
        plan_strs, completed = run_item(task=task, output_path=output_path)

        # 处理规划结果
        for plan_str in plan_strs:
            print(f'执行规划: {plan_str}')
            simulator.action(plan_str)

        # 完成处理并获取结果
        simulator.over()
        errors = simulator.get_errors()
        score = simulator.get_score()

        # 打印处理结果指标
        print(f"\n处理完成时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
        print(f"规划完成状态: {'完成' if completed else '未完成'}")
        print(f"错误数量: {len(errors)}")
        print(f"最终得分: {score}")
        print(f"模拟器状态: {simulator.state}")

        # 记录预测结果
        prediction.append({
            "question": d['question'],
            "plan": plan_strs,
            "errors": errors,
            "score": score,
            "over": completed,
            "state": str(simulator.state)
        })

        # 保存预测结果
        with open(prediction_file, 'w', encoding='utf-8') as f:
            json.dump(prediction, f, indent=4, ensure_ascii=False)

        # 更新进度计数器
        processed_count += 1

        # 打印总体进度
        print(f"\n已完成 {processed_count}/{total_tasks} 条数据处理")
        print(f"{'=' * 50}\n")


# for type in [1, 2, 3]:
#     begin = 0
#     end = 999
#     step = 1
#     extend_end = extend_ends[type-1]
#     task_ids = range(begin, end, step)
#     run(type, task_ids, extend_end=extend_end)
for type in [1, 2, 3]:
    begin = 0
    # 只跑前10条数据
    end = 10
    step = 1
    extend_end = extend_ends[type-1]
    task_ids = range(begin, end, step)
    run(type, task_ids, extend_end=extend_end)
import datetime
import json
import os
from datetime import datetime
from datetime import timedelta

import requests
from utils.config_manager import ConfigManager

config_manager = ConfigManager()
time_format = "%Y-%m-%d %H:%M"
time_format2 = ""


def query_database(query):
    """
    执行数据库查询函数
    参数:
        query (str): 要执行的SQL查询语句
    返回:
        list: 查询结果，通常是数据行的列表
    异常:
        Exception: 当查询执行过程中发生错误时，会打印错误信息并抛出异常
    """
    try:
        # 向本地数据库服务发送POST请求
        response = requests.post(
            "http://localhost:8079/tools/database",  # 数据库服务的URL
            json={'queries': [query]}  # 将查询语句封装在JSON中发送
        ).json()  # 获取响应并解析为JSON格式
        # 打印响应内容，用于调试
        print(f'response={response}')
        # 返回第一个查询的结果
        return response[0]['result']
    except Exception as e:
        # 发生异常时打印错误信息
        print(f'run error{e}')


def get_place_duration(origin, destination):
    # 构建SQL查询语句，查询从起点到终点的城市内交通信息
    query = f"SELECT * FROM in_city_transport\nWHERE origin = '{origin}' and destination = '{destination}';"
    # 清除代理配置，确保数据库查询不受代理影响
    config_manager.clear_proxies()

    # 执行数据库查询获取交通信息
    item = query_database(query)
    # 恢复代理配置
    config_manager.apply_proxies()
    # 检查查询结果是否为空
    if item is None or len(item) == 0:
        return None
    # 获取查询结果中的第一个记录
    item = item[0]
    # 提取并返回交通持续时间（假设持续时间是第三个字段）
    duration = item[2]
    return duration


def get_ticket(number):
    # 构建SQL查询语句，查询指定车票编号的车票信息
    query = f"SELECT * FROM railway\nWHERE number = '{number}';"
    # 清除代理配置
    config_manager.clear_proxies()

    # 执行数据库查询
    item = query_database(query)
    # 应用代理配置
    config_manager.apply_proxies()

    # 如果查询结果为空，则返回None
    if item is None or len(item) == 0:
        return None
    # 获取查询结果的第一条记录
    item = item[0]
    # 将查询结果转换为字典格式的车票信息
    ticket = {
        "number": item[0],           # 车票编号
        "origin": item[1],           # 出发地
        "destination": item[2],      # 目的地
        "departure_time": datetime.strptime(item[3], '%Y-%m-%d %H:%M:%S'),  # 出发时间，转换为datetime对象
        "arrival_time": datetime.strptime(item[4], '%Y-%m-%d %H:%M:%S'),    # 到达时间，转换为datetime对象
        "duration": item[5],         # 行程时长
        "price": item[6]             # 票价
    }
    # 打印车票信息（用于调试或日志记录）
    print(f'ticket {number} = {ticket}')
    # 返回车票信息
    return ticket


#
# print(get_ticket('D1000'))


def get_opening_hours(spot):
    # 构建SQL查询语句，查询指定地点的信息
    query = f"SELECT * FROM place\nWHERE name = '{spot}';"
    # 清除代理设置
    config_manager.clear_proxies()

    # 执行数据库查询
    item = query_database(query)
    # 重新应用代理设置
    config_manager.apply_proxies()
    # 检查查询结果是否为空
    if item is None or len(item) == 0:
        return None
    # 获取第一个查询结果
    item = item[0]
    # 获取营业开始时间
    opening_hours_begin = item[3]
    # 获取营业结束时间
    opening_hours_end = item[4]
    # 返回营业开始和结束时间
    return opening_hours_begin, opening_hours_end


#
# print(get_opening_hours('Tiananmen Square'))


def parse_datetime(datetime_str):
    """
    解析日期时间字符串，处理可能的格式异常
    参数:
        datetime_str (str): 需要解析的日期时间字符串，预期格式为 "YYYY-MM-DD HH:MM"
    返回:
        datetime: 解析后的datetime对象
    异常处理:
        当输入字符串不符合标准格式时，尝试分割日期和时间部分，
        并手动构造时间部分，然后重新组合成标准格式进行解析
    """
    try:
        # 尝试按照标准格式解析日期时间字符串
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
    except ValueError:
        # 如果标准格式解析失败，分割日期和时间部分
        date_part, time_part = datetime_str.split(' ')
        # 提取小时和分钟，忽略秒数（如果有）
        hours, minutes = map(int, time_part.split(':')[:2])

        # 创建一个timedelta对象表示时间部分
        adjusted_time = timedelta(hours=hours, minutes=minutes)

        # 将时间部分格式化为"HH:MM"格式
        new_time_str = date_part + ' ' + (datetime.min + adjusted_time).strftime("%H:%M")

        # 使用重新组合的标准格式字符串解析datetime对象
        return datetime.strptime(new_time_str, "%Y-%m-%d %H:%M")


def create_object(class_name: str, attributes: dict):
    """
    根据类名和属性字典创建并返回类的实例
    参数:
        class_name (str): 类的名称，必须是已定义类的字符串名称
        attributes (dict): 包含类实例属性的字典，键为属性名，值为属性值
    返回:
        根据类名和属性创建的类实例
    异常:
        ValueError: 当指定的类名在全局命名空间中不存在时抛出
    """
    # 从全局命名空间中获取类对象
    cls = globals().get(class_name)
    # 检查类是否存在
    if cls:
        # 使用传入的属性创建并返回类实例
        return cls(**attributes)
    else:
        # 如果类不存在，抛出ValueError异常
        raise ValueError(f"Class '{class_name}' not found.")


class Constraint:
    def check(self, state: dict, error_instruction: str):
        """
        检查约束条件是否满足
        参数:
            state (dict): 当前状态字典，包含需要检查的各种状态值
            error_instruction (str): 当约束条件不满足时的错误提示信息
        返回值:
            int: 约束状态
                0: waiting for satisfying - 等待满足约束条件
                1: satisfied - 约束条件已满足
                2: violated - 约束条件被违反
        """
        # 0: waiting for satisfying - 表示约束条件尚未满足，需要等待
        # 1: satisfied - 表示约束条件已经满足
        # 2: violated - 表示约束条件被违反
        pass

    def get_err_msg(self):
        """
        获取约束条件违反时的错误信息
        返回值:
            str: 错误提示信息，用于提示用户约束条件为何不满足
        """
        pass


class CityDurationConstraint(Constraint):
    def __init__(self, city, days):

        """
        初始化城市停留时间约束类
        :param city: 城市名称
        :param days: 最少需要停留的天数
        """
        self.city = city  # 存储城市名称
        self.days = days  # 存储最少需要停留的天数

    def check(self, state: dict, error_instruction: str):
        """
        检查在城市停留的天数是否满足约束条件
        :param state: 当前状态字典，包含各城市的停留天数等信息
        :param error_instruction: 错误指令信息
        :return: 0-未在该城市停留，1-满足约束条件，2-不满足约束条件
        """
        # 检查是否在该城市停留过
        if f'days_{self.city}' not in state.keys() or state[f'days_{self.city}'] == 0:
            return 0  # 未在该城市停留
        # 检查停留天数是否满足最小天数要求
        elif state[f'days_{self.city}'] >= self.days:
            return 1  # 满足约束条件
        else:
            # 不满足约束条件，添加错误信息
            state['error'].append(f"{error_instruction}City duration error: have stayed in {self.city}"
                                  f" for only {state[f'days_{self.city}']} days")
            return 2  # 不满足约束条件

    def get_err_msg(self):
        """
        获取错误信息
        :return: 错误信息字符串
        """
        return f"Stay in {self.city} for less than {self.days} days"


class SpotDurationConstraint(Constraint):
    def __init__(self, spot, minutes):
        """
        初始化景点停留时间约束对象
        参数:
            spot (str): 景点名称
            minutes (int): 要求的最小停留时间(分钟)
        """
        self.spot = spot
        self.minutes = minutes

    def check(self, state: dict, error_instruction: str):
        """
        检查景点停留时间是否满足约束条件
        参数:
            state (dict): 当前状态字典，包含景点停留时间等信息
            error_instruction (str): 错误提示信息的前缀
        返回:
            int: 返回状态码
                0 - 景点未访问或停留时间为0
                1 - 停留时间满足要求
                2 - 停留时间不满足要求，添加错误信息
        """
        if f'minutes_{self.spot}' not in state.keys() or state[f'minutes_{self.spot}'] == 0:
            return 0  # 景点未访问或停留时间为0
        elif state[f'minutes_{self.spot}'] >= self.minutes:
            return 1  # 停留时间满足要求
        else:
            # 停留时间不足，添加错误信息
            state['error'].append(f"{error_instruction}Spot visiting time error: have stayed in {self.spot}"
                                  f" for only {state[f'minutes_{self.spot}']} minutes")
            return 2  # 停留时间不满足要求

    def get_err_msg(self):
        """
        获取错误信息
        返回:
            str: 描述景点停留时间不足的错误信息
        """
        return f"visit {self.spot} for less than {self.minutes} minutes"


class TravelSimulator:
    def __init__(self, begin_time, end_time, origin_city, origin_place=None, budget=999999, check_opening_hours=False,
                 check_meal=False, type=1, one_day=0, limit='time', money_min=0, money_max=99999, time_min=0,
                 set_budget=False,
                 time_max=99999):
        self.state = {'error': [],
                      'cost': 0,
                      'track': []}
        begin_time = datetime.strptime(begin_time, time_format)
        end_time = datetime.strptime(end_time, time_format)
        self.begin_time = begin_time
        self.time = begin_time
        self.end_time = end_time
        self.origin_city=origin_city
        self.city = origin_city
        self.place = origin_place
        self.check_opening_hours = check_opening_hours
        self.budget = budget
        self.money = budget
        self.constraints = []
        self.check_meal = check_meal
        self.check_sleep = True
        self.type = type
        if type == 1:
            self.check_sleep = False
        self.one_day = one_day
        self.limit = limit
        self.money_min = money_min
        self.money_max = money_max
        self.time_min = time_min
        self.time_max = time_max

        self.elementary_right = 0
        self.elementary_wrong = 0
        self.intermediate_right = 0
        self.intermediate_wrong = 0
        self.advanced_score = 0

    def create_constraints(self, para_dict):
        constrains = []
        for class_name, attributes_list in para_dict.items():
            if isinstance(attributes_list, list):
                for attributes in attributes_list:
                    constrains.append(create_object(class_name, attributes))
            elif isinstance(attributes_list, dict):
                constrains.append(create_object(class_name, attributes_list))
        self.constraints = constrains

    def action(self, action_str):
        # eval('self.' + action_str)
        try:
            # Use eval to execute the string as Python code.
            # The local scope is set to the methods of the current instance.
            eval('self.' + action_str)

        except Exception as e:
            print(f"An error occurred: {e} in self.{action_str}")
            # raise e

    def check_time_money(self, error_instruction):
        if self.money < 0:
            self.state['error'].append(f'{error_instruction}Over budget')
        if self.time > self.end_time:
            self.state['error'].append(f'{error_instruction}Time limit({self.end_time}) exceeded.')

    def go_to_city(self, origin: str, destination: str, departure_time, arrival_time, ticket_number):

        origin = origin.replace(" Railway Hotel", "")
        destination = destination.replace(" Railway Hotel", "")

        error_instruction = f'Error in \"goto_city({origin},{destination},{departure_time},{arrival_time},{ticket_number})\"\n'

        departure_time = parse_datetime(departure_time)#TODO:异常处理
        arrival_time = parse_datetime(arrival_time)
        # departure_time = datetime.strptime(departure_time, time_format)
        # arrival_time = datetime.strptime(arrival_time, time_format)

        ticket = get_ticket(ticket_number)
        if ticket is None:
            self.state['error'].append(f'{error_instruction}Ticket error: no ticket {ticket_number}')
            self.elementary_wrong += 1
        elif not (ticket['origin'] == origin and ticket['destination'] == destination and
                  ticket['departure_time'] == departure_time and ticket['arrival_time'] == arrival_time):
            self.state['error'].append(f'{error_instruction}Ticket error: ticket does not match the itinerary')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1

        if origin != self.city:
            self.state['error'].append(f'{error_instruction}Position error: In {self.city},not {origin}')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1
        if departure_time < self.time:
            self.state['error'].append(f'{error_instruction}Time error: already {self.time}, beyond the departure time')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1

        if self.time != departure_time:
            self.stay_in(city=self.city, begin_time=self.time, end_time=departure_time)

        for constraint in self.constraints:
            if isinstance(constraint, CityDurationConstraint):
                constraint.check(state=self.state, error_instruction=error_instruction)

        self.time = arrival_time
        self.city = destination
        self.place = f'{destination} Railway Hotel'
        self.money -= ticket['price']

        self.check_time_money(error_instruction)

        self.state['track'].append({'begin_time': departure_time, 'end_time': arrival_time, 'action': 'go_to_city'})

    def go_to_place(self, origin: str, destination: str, departure_time, arrival_time):
        error_instruction = f'Error in \"go_to_place({origin},{destination},{departure_time},{arrival_time})\"\n'

        departure_time = parse_datetime(departure_time)
        arrival_time = parse_datetime(arrival_time)
        # departure_time = datetime.strptime(departure_time, time_format)
        # arrival_time = datetime.strptime(arrival_time, time_format)
        if origin != self.place:
            self.state['error'].append(f'{error_instruction}Position error: In {self.place},not {origin}')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1
        if departure_time < self.time:
            self.state['error'].append(f'{error_instruction}Time error: already {self.time}, beyond the departure time')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1

        duration = get_place_duration(origin=origin, destination=destination)
        if duration is not None and arrival_time - departure_time == timedelta(minutes=duration):
            self.elementary_right += 1
        else:
            self.state['error'].append(
                f'{error_instruction}Duration error: duration from {origin} to {destination} should be {duration} minutes.')
            self.elementary_wrong += 1

        if self.time != departure_time:
            self.visit(place=self.place, begin_time=self.time, end_time=departure_time)

        # for constraint in self.constraints:
        #     if isinstance(constraint, SpotDurationConstraint):
        #         constraint.check(state=self.state, error_instruction=error_instruction)
        self.time = arrival_time
        self.place = destination
        # self.check_time_money(error_instruction)

        self.state['track'].append({'begin_time': departure_time, 'end_time': arrival_time, 'action': 'go_to_place'})

    def stay_in(self, city: str, begin_time, end_time):
        if self.type == 3:
            pass

        error_instruction = f'Error in \"stay_in({city},{begin_time},{end_time})\"\n'

        if isinstance(begin_time, str):
            begin_time = parse_datetime(begin_time)
            # begin_time = datetime.strptime(begin_time, time_format)
        if isinstance(end_time, str):
            end_time = parse_datetime(end_time)
            # end_time = datetime.strptime(end_time, time_format)

        if begin_time < self.time:
            self.state['error'].append(f'{error_instruction}Time error: already {self.time}, beyond the begin_time')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1

        if self.city != city:
            self.state['error'].append(f'{error_instruction}Position error: In {self.city},not {city}')
            self.city = city
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1
        self.time = end_time
        self.check_time_money(error_instruction)

        # check sleeping time
        # sleeping_hours_begin, sleeping_hours_end = 0, 7
        # t1 = datetime.strptime(f"{sleeping_hours_begin}:00", "%H:%M").time()
        # t2 = datetime.strptime(f"{sleeping_hours_end}:00", "%H:%M").time()
        # if begin_time.time() >= t1 and end_time.time() <= t2:
        #     self.intermediate_right += 1
        # else:
        #     self.state['error'].append(f'{error_instruction}Sleeping hours error: goto somewhere during sleeping hours')
        #     self.intermediate_wrong += 1

        duration = end_time - begin_time

        if self.one_day == 1 and begin_time.hour < 12:
            duration = duration + timedelta(hours=12)

        if f'days_{city}' in self.state.keys():
            self.state[f'days_{city}'] += duration.days
        else:
            self.state[f'days_{city}'] = duration.days

        self.state['track'].append({'begin_time': begin_time, 'end_time': end_time, 'action': 'stay_in'})

    def visit(self, place: str, begin_time, end_time):

        error_instruction = f'Error in \"visit({place},{begin_time},{end_time})\"\n'
        if isinstance(begin_time, str):
            begin_time = parse_datetime(begin_time)
            # begin_time = datetime.strptime(begin_time, time_format)
        if isinstance(end_time, str):
            end_time = parse_datetime(end_time)
            # end_time = datetime.strptime(end_time, time_format)
        if begin_time < self.time:
            self.state['error'].append(f'{error_instruction}Time error: already {self.time}, beyond the begin_time')
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1
        if self.place != place:
            self.state['error'].append(f'{error_instruction}Position error: In {self.place},not {place}')
            self.place = place
            self.elementary_wrong += 1
        else:
            self.elementary_right += 1
        self.time = end_time
        self.check_time_money(error_instruction)

        def check_in_period(t,period_begin, period_end):
            t1 = datetime.strptime(f"{period_begin}", "%H:%M").time()
            t2 = datetime.strptime(f"{period_end}", "%H:%M").time()
            if t1 < t < t2:
                return True
            else:
                return False

        if self.check_opening_hours:
            opening_hours_begin, opening_hours_end = get_opening_hours(spot=self.place)
            t1 = datetime.strptime(f"{opening_hours_begin}:00", "%H:%M").time()
            if opening_hours_end == 24:
                t2 = datetime.strptime(f"23:59", "%H:%M").time()
            else:
                t2 = datetime.strptime(f"{opening_hours_end}:00", "%H:%M").time()

            if begin_time.time() >= t1 and end_time.time() <= t2:
                self.intermediate_right += 1
            else:
                self.state['error'].append(f'{error_instruction}Opening hours error: visit outside of opening hours')
                self.intermediate_wrong += 1


        if self.check_sleep and not self.check_opening_hours:
            if check_in_period(begin_time.time(),"00:00","07:00")\
                    or check_in_period(begin_time.time(),"22:00","23:59")\
                    or check_in_period(end_time.time(),"00:00","07:00")\
                    or check_in_period(end_time.time(),"22:00","23:59"):
                self.state['error'].append(f'{error_instruction}Sleeping hours error: visit during sleeping hours')
                self.intermediate_wrong += 1
            else:
                self.intermediate_right += 1

        duration = end_time - begin_time

        if f'minutes_{place}' in self.state.keys():
            self.state[f'minutes_{place}'] += duration.total_seconds() / 60
        else:
            self.state[f'minutes_{place}'] = int(duration.total_seconds() / 60)

        # for constraint in self.constraints:
        #     if isinstance(constraint, SpotDurationConstraint):
        #         constraint.check(state=self.state, error_instruction=error_instruction)

        self.state['track'].append({'begin_time': begin_time, 'end_time': end_time, 'action': 'visit'})

    def over(self):
        for constraint in self.constraints:
            if isinstance(constraint, CityDurationConstraint) or isinstance(constraint, SpotDurationConstraint):
                result = constraint.check(state=self.state, error_instruction='')
                if result == 0 or result == 2:
                    self.state['error'].append(constraint.get_err_msg())
                    self.intermediate_wrong += 1
                else:
                    self.intermediate_right += 1

        if self.type==1:
            if self.city==self.origin_city:
                self.intermediate_right += 1
            else:
                self.intermediate_wrong += 1
                self.state['error'].append(
                    f'City error: Do not return to {self.origin_city}')

        def is_overlapping(begin1, end1, begin2, end2):
            return not (end1 <= begin2 or end2 <= begin1)

        if self.limit == 'time':
            seconds = (self.time - self.begin_time).total_seconds()
            if seconds <= self.time_min:
                self.advanced_score = 20
            elif seconds >= self.time_max:
                self.advanced_score = 0
            else:
                self.advanced_score = 20 * (seconds - self.time_min) / (self.time_max - self.time_min)
        elif self.limit == 'money':
            cost = (self.budget - self.money)
            if cost <= self.money_min:
                self.advanced_score = 20
            elif cost >= self.money_max:
                self.advanced_score = 0
            else:
                self.advanced_score = 20 * (cost - self.money_min) / (self.money_max - self.money_min)

        if self.check_meal:
            meal_times = [['12:00', '13:00'], ['18:30', '19:30']]
            for meal_time in meal_times:
                meal_begin = datetime.strptime(meal_time[0], "%H:%M").time()
                meal_end = datetime.strptime(meal_time[1], "%H:%M").time()
                is_satisfied = True
                for t in self.state['track']:
                    if t['action'] in ['go_to_place', 'visit']:
                        if is_overlapping(meal_begin, meal_end, t['begin_time'].time(), t['end_time'].time()):
                            is_satisfied = False
                if is_satisfied:
                    self.intermediate_right += 1
                else:
                    self.intermediate_wrong += 1
                    self.state['error'].append(
                        f'Meal error: No meal time reserved from {meal_time[0]} to {meal_time[1]}')

    def get_errors(self):
        return self.state['error']

    def get_score(self, progressive=True):
        print(f'e_right={self.elementary_right}')
        print(f'e_wrong={self.elementary_wrong}')
        print(f'i_right={self.intermediate_right}')
        print(f'i_wrong={self.intermediate_wrong}')
        self.state['e_right'] = self.elementary_right
        self.state['e_wrong'] = self.elementary_wrong
        self.state['i_right'] = self.intermediate_right
        self.state['i_wrong'] = self.intermediate_wrong
        if (self.elementary_right + self.elementary_wrong) == 0:
            self.elementary_wrong = 1
        if (self.intermediate_right + self.intermediate_wrong) == 0:
            self.intermediate_wrong = 1

        elementary_score = self.elementary_right / (self.elementary_right + self.elementary_wrong) * 60
        intermediate_score = self.intermediate_right / (self.intermediate_right + self.intermediate_wrong) * 20
        advanced_score = self.advanced_score
        if not progressive:
            score = elementary_score + intermediate_score
            if score == 80:
                score += advanced_score
            return score

        score = elementary_score
        if score == 60:
            score += intermediate_score
        if score == 80:
            score += advanced_score
        return score

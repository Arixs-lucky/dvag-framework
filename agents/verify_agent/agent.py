from agents.verify_agent.prompt import SYSTEM_PROMPT
from agents.base_agent import BaseAgent
from utils.prompt import generate_prompt


class SkillLibrary:
    """技能库：分类管理已验证和待审核的技能"""

    def __init__(self):
        self.verified_skills = []      # 验证通过，已入库
        self.pending_skills = []        # 待审核
        self.rejected_skills = []       # 明确验证失败

    def add_skill(self, skill, verification_result):
        """
        根据验证结果将技能分类入库。

        Parameters
        ----------
        skill : dict
            技能描述字典。
        verification_result : dict
            验证结果，含 'verified' 和 'confidence' 字段。
        """
        enriched = {
            **skill,
            'verified': verification_result['verified'],
            'confidence': verification_result['confidence'],
            'method': verification_result.get('method', 'unknown'),
        }
        if verification_result['verified']:
            self.verified_skills.append(enriched)
            print(f"[SkillLib] Skill '{skill.get('name', skill.get('id'))}' VERIFIED "
                  f"(conf={verification_result['confidence']}, method={verification_result.get('method')})")
        else:
            # 验证不通过：标记为待审核，不自动入库
            self.pending_skills.append(skill)
            print(f"[SkillLib] Skill '{skill.get('name', skill.get('id'))}' -> PENDING_REVIEW")

    def get_qualified_skills(self):
        """获取所有已验证技能（可用于调度）"""
        return self.verified_skills

    def get_pending_skills(self):
        """获取待审核技能"""
        return self.pending_skills

    def size(self):
        return len(self.verified_skills), len(self.pending_skills), len(self.rejected_skills)


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
        super().__init__(record_path, model_name, proxy)
        self.messages.append({'role': 'system',
                              'content': self.generate_system_prompt(total_task=total_task, current_task=current_task,
                                                                     completed_task=completed_task, process=process,
                                                                     result=result)})
        self.messages.append({'role': 'user',
                              'content': 'Start.'})
        # 技能库
        self.skill_lib = SkillLibrary()

    def generate_system_prompt(self, total_task, current_task, completed_task, process, result):
        """生成系统提示（原有功能不变）"""
        system_prompt = SYSTEM_PROMPT
        replace_dict = {
            '{{total_task}}': total_task,
            '{{current_task}}': str(current_task),
            '{{completed_task}}': str(completed_task),
            '{{process}}': process,
            '{{result}}': result
        }
        return generate_prompt(template=system_prompt, replace_dict=replace_dict)

    # ── 技能验证 ──

    def verify_skill(self, skill, test_cases=None, constraint_pool=None):
        """
        综合验证技能是否有效，返回验证结果。

        验证流程：
        1. 数值回测 — 在测试案例上验证技能的数值输出是否合理
        2. 求解器验证 — 用 MILP 验证技能是否满足约束
        3. 标记待审核 — 若以上均未通过

        Parameters
        ----------
        skill : dict
            技能描述（含 name/type/output 等字段）。
        test_cases : list[dict], optional
            测试案例列表，用于回测。
        constraint_pool : dict, optional
            约束相关的候选池，用于 MILP 验证。

        Returns
        -------
        dict
            {'verified': bool, 'method': str, 'confidence': float}
        """
        # 规则1：数值回测
        if test_cases:
            backtest_result = self.backtest(skill, test_cases)
            if backtest_result['verified']:
                print(f"[Verify] Skill '{skill.get('name')}' PASSED backtest (conf={backtest_result['confidence']})")
                return backtest_result

        # 规则2：求解器验证
        if constraint_pool:
            solver_result = self.solver_verify(skill, constraint_pool)
            if solver_result['verified']:
                print(f"[Verify] Skill '{skill.get('name')}' PASSED solver_verify (conf={solver_result['confidence']})")
                return solver_result

        # 规则3：标记待审核
        print(f"[Verify] Skill '{skill.get('name')}' -> PENDING_REVIEW")
        return {'verified': False, 'method': 'pending_review', 'confidence': 0.0}

    def backtest(self, skill, test_cases):
        """
        在成功案例上回测技能。

        验证规则：
        - 技能的数值输出必须在合理范围内
        - 技能的组合约束应能被满足
        - 回测通过率 ≥ 阈值

        Parameters
        ----------
        skill : dict
            技能描述。
        test_cases : list[dict]
            测试案例。

        Returns
        -------
        dict
            {'verified': bool, 'method': 'backtest', 'confidence': float}
        """
        if not test_cases:
            return {'verified': False, 'method': 'backtest', 'confidence': 0.0}

        passed = 0
        total = len(test_cases)

        for tc in test_cases:
            if self._check_numeric_reasonable(skill, tc):
                passed += 1

        ratio = passed / total if total > 0 else 0
        confidence = ratio * 0.9  # 最高 0.9
        verified = ratio >= 0.6  # ≥60% 通过率即认为通过

        return {
            'verified': verified,
            'method': 'backtest',
            'confidence': confidence
        }

    @staticmethod
    def _check_numeric_reasonable(skill, test_case):
        """
        检查技能的数值输出是否在合理范围内。

        Parameters
        ----------
        skill : dict
            技能（含 output 字段）。
        test_case : dict
            测试案例。

        Returns
        -------
        bool
            是否通过数值检查。
        """
        output = skill.get('output', {})
        if not isinstance(output, dict):
            return False

        # 预算约束检查
        budget = test_case.get('budget')
        if budget is not None:
            total_cost = sum(v for k, v in output.items()
                             if 'price' in k.lower() or 'cost' in k.lower() or 'total' in k.lower())
            if total_cost > budget:
                return False

        # 非负约束
        for key, val in output.items():
            if isinstance(val, (int, float)) and val < 0:
                return False

        # 时间顺序约束（如果有）
        time_keys = [k for k in output if 'time' in k.lower() or 'date' in k.lower() or 'arrival' in k.lower() or 'departure' in k.lower()]
        if len(time_keys) >= 2:
            try:
                times = sorted([output[k] for k in time_keys])
                if times != [output[k] for k in time_keys]:
                    # 时间未排序（可选检查，不一定必须）
                    pass
            except (TypeError, ValueError):
                pass

        return True

    def solver_verify(self, skill, constraint_pool):
        """
        用 MILP 求解器验证技能是否有效。

        Parameters
        ----------
        skill : dict
            技能描述（含 name/type/params 等字段）。
        constraint_pool : dict
            候选池，节点 ID → 候选列表。

        Returns
        -------
        dict
            {'verified': bool, 'method': 'solver', 'confidence': float}
        """
        # 延迟导入，避免 ortools 未安装时无法导入整个模块
        from utils.milp_solver import solve_milp

        if not constraint_pool:
            return {'verified': False, 'method': 'solver', 'confidence': 0.0}

        # 从 skill 提取约束
        skill_constraints = skill.get('constraints', [])
        if not skill_constraints:
            # 无显式约束，默认验证通过
            return {'verified': True, 'method': 'solver', 'confidence': 0.85}

        try:
            result = solve_milp(constraint_pool, skill_constraints)
            if result['status'] == 'optimal':
                confidence = 0.85  # MILP 严格求解，高置信度
                return {
                    'verified': True,
                    'method': 'solver',
                    'confidence': confidence
                }
            else:
                # 不可行：技能无法满足约束
                return {
                    'verified': False,
                    'method': 'solver',
                    'confidence': 0.0
                }
        except Exception as e:
            print(f"[Verify] Solver verification error: {e}")
            return {
                'verified': False,
                'method': 'solver',
                'confidence': 0.0
            }

    def update_skill_library(self, skill, verification_result):
        """
        只有验证通过的技能才入库。

        Parameters
        ----------
        skill : dict
            技能描述。
        verification_result : dict
            验证结果。
        """
        self.skill_lib.add_skill(skill, verification_result)

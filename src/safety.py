"""
安全与健康风险控制模块
负责医疗边界声明、过敏原校验、危险饮食检测
"""

import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

MEDICAL_DISCLAIMERS = [
    "本回答仅供参考，不能替代专业医疗建议",
    "如有疾病请咨询医生",
    "本建议不构成医疗诊断或治疗方案",
]

DANGEROUS_DIET_PATTERNS = [
    (r"每天只吃.{0,5}(?:水果|蔬菜|苹果|黄瓜)", "极端节食", "长期极低热量摄入会导致营养不良和代谢降低"),
    (r"(?:不吃|杜绝|完全戒掉).{0,5}(?:碳水|主食|米饭|面食)", "完全戒断碳水", "碳水是大脑主要能量来源，不建议完全戒断"),
    (r"(?:每天|每日).{0,5}(?:跑步|运动|训练).{0,5}(?:3|4|5|6|7|8|9|10).{0,3}小时", "过度运动", "过量运动可能导致横纹肌溶解和关节损伤"),
    (r"(?:奶昔|代餐).{0,5}(?:代替|替代).{0,5}(?:所有|全部|三餐)", "代餐替代所有正餐", "长期只喝代餐会导致营养不均衡"),
    (r"(?:减肥药|泻药|催吐)", "危险减肥方法", "药物减肥和催吐会对身体造成严重伤害"),
]

CALORIE_SAFETY = {
    "min": 1000,
    "max": 4000,
    "min_warning": 1200,
}


class SafetyValidator:
    """安全校验器"""

    def __init__(self):
        self.disclaimers = MEDICAL_DISCLAIMERS
        self.dangerous_patterns = DANGEROUS_DIET_PATTERNS

    def validate_query(self, query: str) -> Dict:
        result = {
            "is_safe": True,
            "warnings": [],
            "disclaimers": [],
            "risk_level": "low",
        }

        for pattern, name, desc in self.dangerous_patterns:
            if re.search(pattern, query):
                result["warnings"].append({"type": name, "description": desc})
                result["risk_level"] = "high"
                result["is_safe"] = False

        medical_keywords = ["糖尿病", "高血压", "肾病", "痛风", "孕妇", "哺乳期", "心脏病"]
        for kw in medical_keywords:
            if kw in query:
                result["disclaimers"].append(f"检测到疾病/特殊状态「{kw}」，建议咨询医生后执行")
                if result["risk_level"] == "low":
                    result["risk_level"] = "medium"
                break

        return result

    def validate_recommendation(
        self,
        calories: float,
        allergies: List[str] = None,
        allergens_in_food: List[str] = None,
    ) -> Dict:
        result = {"is_safe": True, "warnings": [], "risk_level": "low"}

        if calories < CALORIE_SAFETY["min_warning"]:
            result["warnings"].append(f"热量偏低({calories}kcal)，建议不低于{CALORIE_SAFETY['min_warning']}kcal")
            result["risk_level"] = "medium"
        elif calories > CALORIE_SAFETY["max"]:
            result["warnings"].append(f"热量偏高({calories}kcal)，建议不超过{CALORIE_SAFETY['max']}kcal")
            result["risk_level"] = "medium"

        if allergies and allergens_in_food:
            overlap = set(allergies) & set(allergens_in_food)
            if overlap:
                result["warnings"].append(f"检测到过敏原冲突: {overlap}")
                result["risk_level"] = "critical"
                result["is_safe"] = False

        return result

    def get_disclaimers(self) -> List[str]:
        return self.disclaimers

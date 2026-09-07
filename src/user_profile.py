"""
用户画像模块
负责用户信息管理、营养目标计算、偏好学习
本文件保留旧版 UserProfileManager 以兼容已有调用，
并提供纯函数 calculate_targets_from_profile 供“真实账号”数据使用。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

PROFILES_PATH = Path(__file__).parent.parent / "data" / "raw" / "user_profiles.json"

DEFAULT_PROFILE = {
    "user_id": "default",
    "basic_info": {
        "age": 25,
        "gender": "male",
        "height_cm": 175,
        "weight_kg": 70,
        "activity_level": "moderate",
        "body_fat_pct": None,
        "goal": "maintain",
    },
    "health_conditions": [],
    "allergies": [],
    "dietary_preferences": {
        "goal": "maintain",
        "vegetarian": False,
        "dietary_type": "omnivore",
        "disliked_foods": [],
        "meal_times": {"breakfast": "07:30", "lunch": "12:00", "dinner": "18:30"},
    },
    "lifestyle": {
        "exercise_frequency": "3-4次/周",
        "exercise_types": [],
        "sleep_hours": 7,
        "water_goal_ml": 2000,
    },
    "nutrition_targets": {
        "calories": 2000,
        "protein_g": 60,
        "fat_g": 55,
        "carbs_g": 225,
    },
    "meal_schedule": {
        "breakfast": "07:30",
        "lunch": "12:00",
        "dinner": "18:30",
    },
    "chat_history": [],
}

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

GOAL_PROTEIN_RATIO = {"lose": 0.35, "gain": 0.3, "maintain": 0.25, "healthy": 0.25}


def calculate_targets_from_profile(profile: dict) -> dict:
    """根据个人资料计算每日营养目标（BMR -> TDEE -> 三大营养素）"""
    basic = profile.get("basic_info", {}) or {}
    prefs = profile.get("dietary_preferences", {}) or {}
    goal = prefs.get("goal") or basic.get("goal") or "maintain"

    age = basic.get("age") or 25
    gender = basic.get("gender") or "male"
    height = basic.get("height_cm") or 170
    weight = basic.get("weight_kg") or 60
    activity = basic.get("activity_level") or "moderate"

    if gender == "female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5

    tdee = bmr * ACTIVITY_MULTIPLIERS.get(activity, 1.55)

    if goal == "lose":
        calories = tdee * 0.8
    elif goal == "gain":
        calories = tdee * 1.12
    elif goal == "healthy":
        calories = tdee * 0.92
    else:
        calories = tdee

    protein_ratio = GOAL_PROTEIN_RATIO.get(goal, 0.25)
    protein_g = (calories * protein_ratio) / 4
    fat_g = (calories * 0.25) / 9
    carbs_g = (calories - protein_g * 4 - fat_g * 9) / 4

    bmi = round(weight / ((height / 100) ** 2), 1) if height and weight else None

    return {
        "bmr": round(bmr),
        "tdee": round(tdee),
        "bmi": bmi,
        "calories": round(calories),
        "protein_g": round(protein_g),
        "fat_g": round(fat_g),
        "carbs_g": round(carbs_g),
        "water_goal_ml": (profile.get("lifestyle") or {}).get("water_goal_ml")
        or 2000,
    }


class UserProfileManager:
    """用户画像管理器（旧版兼容：从 JSON 模板读取默认画像）"""

    def __init__(self, profiles_path: Optional[str] = None):
        self.profiles_path = Path(profiles_path) if profiles_path else PROFILES_PATH
        self._profiles: Dict[str, dict] = {}
        self._load_profiles()

    def _load_profiles(self):
        if self.profiles_path.exists():
            try:
                data = json.loads(self.profiles_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for p in data:
                        uid = p.get("user_id", "unknown")
                        self._profiles[uid] = p
                elif isinstance(data, dict):
                    self._profiles = data
            except Exception as e:
                logger.warning(f"加载用户画像失败: {e}")

    def get_profile(self, user_id: str) -> dict:
        if user_id in self._profiles:
            return self._profiles[user_id]
        profile = DEFAULT_PROFILE.copy()
        profile["user_id"] = user_id
        self._profiles[user_id] = profile
        return profile

    def update_profile(self, user_id: str, updates: dict) -> dict:
        profile = self.get_profile(user_id)
        self._deep_update(profile, updates)
        profile["last_updated"] = datetime.now().isoformat()
        self._profiles[user_id] = profile
        return profile

    def calculate_nutrition_targets(self, user_id: str) -> dict:
        profile = self.get_profile(user_id)
        targets = calculate_targets_from_profile(profile)
        self.update_profile(user_id, {"nutrition_targets": targets})
        return targets

    def extract_constraints_from_query(self, query: str) -> dict:
        constraints = {}
        goal_map = {
            "减脂": "lose", "减肥": "lose", "瘦身": "lose", "瘦": "lose",
            "增肌": "gain", "增重": "gain", "健身": "gain", "壮": "gain",
            "维持": "maintain", "保持": "maintain",
        }
        for cn, en in goal_map.items():
            if cn in query:
                constraints["goal"] = en
                break

        allergy_keywords = {
            "乳糖不耐": "乳制品", "牛奶过敏": "乳制品",
            "海鲜过敏": "海鲜", "虾过敏": "虾",
            "花生过敏": "花生", "坚果过敏": "坚果",
            "麸质过敏": "麸质", "鸡蛋过敏": "鸡蛋",
        }
        allergies = []
        for kw, allergen in allergy_keywords.items():
            if kw in query:
                allergies.append(allergen)
        if allergies:
            constraints["allergies"] = allergies

        disease_keywords = {
            "糖尿病": "diabetes", "高血压": "hypertension",
            "肾病": "kidney", "痛风": "gout",
            "高血脂": "hyperlipidemia",
        }
        diseases = []
        for cn, en in disease_keywords.items():
            if cn in query:
                diseases.append(en)
        if diseases:
            constraints["health_conditions"] = diseases

        return constraints

    @staticmethod
    def _deep_update(base: dict, updates: dict):
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                UserProfileManager._deep_update(base[key], value)
            else:
                base[key] = value
# 知识库与RAG设计重构

## 一、动态分块策略

### 1.1 分块原则

**核心思想：** 语义分块优于固定长度分块

| 原则 | 说明 |
|------|------|
| 语义完整性 | 每个块应包含完整语义单元 |
| 长度灵活性 | 不再硬性限制500-800字符 |
| 重叠合理性 | 按段落/语义重叠，不按字符 |
| 上下文保留 | 保留必要的上下文信息 |

### 1.2 菜谱分块策略

**分块类型：**
```python
class RecipeChunkingStrategy:
    """菜谱分块策略"""
    
    def chunk_recipe(self, recipe):
        """将菜谱分割为多个语义块"""
        chunks = []
        
        # 1. 基础信息块（必选）
        chunks.append(self.create_basic_chunk(recipe))
        
        # 2. 食材块（必选）
        chunks.append(self.create_ingredients_chunk(recipe))
        
        # 3. 步骤块（可选，长菜谱拆分）
        chunks.extend(self.create_step_chunks(recipe))
        
        # 4. 营养块（必选）
        chunks.append(self.create_nutrition_chunk(recipe))
        
        return chunks
    
    def create_basic_chunk(self, recipe):
        """创建基础信息块"""
        return {
            "chunk_type": "basic",
            "content": f"""
菜名：{recipe['name']}
分类：{recipe['category']}
餐次：{recipe['meal_type']}
难度：{recipe['difficulty']}
烹饪时间：{recipe['cook_time']}分钟
热量：{recipe['calories']}kcal
            """,
            "metadata": {
                "recipe_id": recipe['id'],
                "chunk_type": "basic"
            }
        }
    
    def create_ingredients_chunk(self, recipe):
        """创建食材块"""
        ingredients_text = "、".join(recipe['ingredients'])
        return {
            "chunk_type": "ingredients",
            "content": f"""
食材：{ingredients_text}
过敏原：{recipe.get('allergens', '未知')}
            """,
            "metadata": {
                "recipe_id": recipe['id'],
                "chunk_type": "ingredients",
                "allergens": recipe.get('allergens')
            }
        }
    
    def create_step_chunks(self, recipe):
        """创建步骤块（长菜谱拆分）"""
        steps = recipe.get('steps', [])
        chunks = []
        
        if len(steps) <= 3:
            # 步骤少，合并为一个块
            chunks.append({
                "chunk_type": "steps",
                "content": "步骤：\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps)),
                "metadata": {
                    "recipe_id": recipe['id'],
                    "chunk_type": "steps"
                }
            })
        else:
            # 步骤多，按3步一组拆分
            for i in range(0, len(steps), 3):
                batch = steps[i:i+3]
                chunks.append({
                    "chunk_type": "steps",
                    "content": "步骤：\n" + "\n".join(f"{i+j+1}. {step}" for j, step in enumerate(batch)),
                    "metadata": {
                        "recipe_id": recipe['id'],
                        "chunk_type": "steps",
                        "step_range": f"{i+1}-{i+len(batch)}"
                    }
                })
        
        return chunks
    
    def create_nutrition_chunk(self, recipe):
        """创建营养块"""
        return {
            "chunk_type": "nutrition",
            "content": f"""
营养成分（每100g）：
热量：{recipe['calories']}kcal
蛋白质：{recipe['protein']}g
脂肪：{recipe['fat']}g
碳水：{recipe['carbs']}g
膳食纤维：{recipe.get('fiber', '未知')}g
            """,
            "metadata": {
                "recipe_id": recipe['id'],
                "chunk_type": "nutrition"
            }
        }
```

### 1.3 分块示例

**原始菜谱：**
```json
{
  "id": "recipe_001",
  "name": "柠檬鸡胸肉",
  "category": "减脂餐",
  "meal_type": "午餐",
  "difficulty": "简单",
  "cook_time": 25,
  "ingredients": ["鸡胸肉150g", "柠檬1个", "蒜末5g", "生抽10ml"],
  "steps": [
    "鸡胸肉切片，用蒜末、生抽腌制20分钟",
    "柠檬切片，铺在空气炸锅底部",
    "放入鸡胸肉，180度烤8分钟",
    "翻面刷少许油，再烤10分钟"
  ],
  "calories": 189,
  "protein": 31.2,
  "fat": 5.8,
  "carbs": 2.1,
  "allergens": []
}
```

**分块结果：**

块1（基础信息）：
```
菜名：柠檬鸡胸肉
分类：减脂餐
餐次：午餐
难度：简单
烹饪时间：25分钟
热量：189kcal
```

块2（食材）：
```
食材：鸡胸肉150g、柠檬1个、蒜末5g、生抽10ml
过敏原：无
```

块3（步骤）：
```
步骤：
1. 鸡胸肉切片，用蒜末、生抽腌制20分钟
2. 柠檬切片，铺在空气炸锅底部
3. 放入鸡胸肉，180度烤8分钟
4. 翻面刷少许油，再烤10分钟
```

块4（营养）：
```
营养成分（每100g）：
热量：189kcal
蛋白质：31.2g
脂肪：5.8g
碳水：2.1g
膳食纤维：0.3g
```

---

## 二、公私知识库分离

### 2.1 知识库架构

```
knowledge_base/
├── public_knowledge/              # 公共知识库（全局共享）
│   ├── recipes/                  # 菜谱库
│   │   ├── fat_loss/            # 减脂餐
│   │   ├── muscle_gain/         # 增肌餐
│   │   └── maintenance/         # 维持餐
│   ├── nutrition/                # 营养知识库
│   │   ├── food_composition.json
│   │   └── nutrition_guide.json
│   └── health/                   # 健康知识库
│       ├── diet_for_conditions.json
│       └── common_misconceptions.json
│
└── user_private/                  # 用户私有库
    ├── user_001/
    │   ├── profile.json          # 用户画像
    │   ├── meal_records/         # 饮食记录
    │   ├── weight_records.json   # 体重记录
    │   ├── feedback_history.json # 反馈历史
    │   └── insights.json         # 聊天洞察
    ├── user_002/
    └── ...
```

### 2.2 公共知识库设计

```python
class PublicKnowledgeBase:
    """公共知识库"""
    
    def __init__(self):
        self.recipe_index = None  # FAISS索引
        self.nutrition_data = None  # 营养数据
        self.health_knowledge = None  # 健康知识
    
    def search_recipes(self, query, top_k=20, filters=None):
        """搜索菜谱"""
        # 1. 向量检索
        query_embedding = self.encode_query(query)
        similar_recipes = self.recipe_index.search(query_embedding, top_k)
        
        # 2. 应用过滤器
        if filters:
            similar_recipes = self.apply_filters(similar_recipes, filters)
        
        return similar_recipes
    
    def apply_filters(self, recipes, filters):
        """应用过滤器"""
        filtered = []
        
        for recipe in recipes:
            # 过敏原过滤
            if 'exclude_allergens' in filters:
                if set(recipe['allergens']) & set(filters['exclude_allergens']):
                    continue
            
            # 分类过滤
            if 'category' in filters:
                if recipe['category'] != filters['category']:
                    continue
            
            # 餐次过滤
            if 'meal_type' in filters:
                if recipe['meal_type'] != filters['meal_type']:
                    continue
            
            # 热量范围过滤
            if 'max_calories' in filters:
                if recipe['calories'] > filters['max_calories']:
                    continue
            
            filtered.append(recipe)
        
        return filtered
```

### 2.3 用户私有库设计

```python
class UserPrivateKnowledgeBase:
    """用户私有知识库"""
    
    def __init__(self, user_id):
        self.user_id = user_id
        self.profile = None
        self.meal_records = []
        self.feedback_history = []
    
    def load_profile(self):
        """加载用户画像"""
        # 从文件或数据库加载
        pass
    
    def save_meal_record(self, record):
        """保存饮食记录"""
        self.meal_records.append(record)
        self.save_to_disk()
    
    def get_user_preferences(self):
        """获取用户偏好"""
        return {
            "taste": self.profile.get("taste_preferences"),
            "disliked_foods": self.profile.get("blacklist", {}).get("ingredients", []),
            "calorie_target": self.profile.get("nutrition_targets", {}).get("calorie_target"),
        }
    
    def get_recommendation_context(self):
        """获取推荐上下文"""
        return {
            "user_profile": self.profile,
            "recent_meals": self.get_recent_meals(days=7),
            "preference_summary": self.get_preference_summary(),
            "blacklist": self.profile.get("blacklist", {})
        }
```

### 2.4 检索流程

```python
class HybridRetriever:
    """混合检索器"""
    
    def __init__(self, public_kb, private_kb):
        self.public_kb = public_kb
        self.private_kb = private_kb
    
    def retrieve(self, query, top_k=5):
        """混合检索"""
        # 1. 公共库检索（召回）
        candidates = self.public_kb.search_recipes(
            query, 
            top_k=top_k * 4,  # 多召回一些
            filters=self.get_filters()
        )
        
        # 2. 私有库过滤
        filtered = self.filter_by_private(candidates)
        
        # 3. 重排序
        reranked = self.rerank(filtered, query)
        
        # 4. 返回Top-K
        return reranked[:top_k]
    
    def get_filters(self):
        """获取过滤条件"""
        user_prefs = self.private_kb.get_user_preferences()
        
        return {
            "exclude_allergens": user_prefs.get("disliked_foods", []),
            "max_calories": user_prefs.get("calorie_target", 2000) * 0.4  # 单餐不超过40%
        }
    
    def filter_by_private(self, recipes):
        """使用私有库过滤"""
        user_prefs = self.private_kb.get_user_preferences()
        blacklist = user_prefs.get("blacklist", {})
        
        filtered = []
        for recipe in recipes:
            # 检查是否在黑名单中
            if recipe['id'] in blacklist.get("recipes", []):
                continue
            
            # 检查食材是否在黑名单中
            recipe_ingredients = set(recipe.get('ingredients', []))
            if recipe_ingredients & set(blacklist.get("ingredients", [])):
                continue
            
            filtered.append(recipe)
        
        return filtered
    
    def rerank(self, recipes, query):
        """重排序"""
        user_prefs = self.private_kb.get_user_preferences()
        
        scored = []
        for recipe in recipes:
            score = self.calculate_score(recipe, user_prefs)
            scored.append((recipe, score))
        
        # 按分数排序
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [recipe for recipe, score in scored]
    
    def calculate_score(self, recipe, user_prefs):
        """计算推荐分数"""
        score = 0
        
        # 热量匹配度
        target_calories = user_prefs.get("calorie_target", 2000)
        calorie_diff = abs(recipe['calories'] - target_calories * 0.35)
        score += max(0, 100 - calorie_diff)
        
        # 口味匹配度
        taste_prefs = user_prefs.get("taste", {})
        if taste_prefs:
            # 根据口味偏好评分
            pass
        
        # 营养匹配度
        if recipe.get('protein', 0) > 20:  # 高蛋白加分
            score += 20
        
        return score
```

---

## 三、质量过滤机制

### 3.1 数据可信度分级

```python
class DataCredibility:
    """数据可信度"""
    
    OFFICIAL = "official"  # 官方数据
    USER_VERIFIED = "user_verified"  # 用户验证
    USER_GENERATED = "user_generated"  # 用户生成
    SUSPICIOUS = "suspicious"  # 可疑数据
    
    # 可信度分数
    CREDIBILITY_SCORES = {
        OFFICIAL: 1.0,
        USER_VERIFIED: 0.8,
        USER_GENERATED: 0.6,
        SUSPICIOUS: 0.2
    }
```

### 3.2 质量校验规则

```python
class RecipeQualityChecker:
    """菜谱质量校验器"""
    
    def check_recipe(self, recipe):
        """校验菜谱质量"""
        issues = []
        
        # 1. 营养值校验
        nutrition_issues = self.check_nutrition_values(recipe)
        issues.extend(nutrition_issues)
        
        # 2. 食材合理性校验
        ingredient_issues = self.check_ingredients(recipe)
        issues.extend(ingredient_issues)
        
        # 3. 步骤完整性校验
        step_issues = self.check_steps(recipe)
        issues.extend(step_issues)
        
        # 4. 计算可信度
        credibility = self.calculate_credibility(recipe, issues)
        
        return {
            "recipe_id": recipe['id'],
            "issues": issues,
            "credibility": credibility,
            "is_safe": credibility >= 0.5
        }
    
    def check_nutrition_values(self, recipe):
        """校验营养值"""
        issues = []
        
        # 热量范围检查（0-2000kcal/100g）
        if recipe.get('calories', 0) < 0 or recipe.get('calories', 0) > 2000:
            issues.append({
                "type": "nutrition_error",
                "field": "calories",
                "value": recipe.get('calories'),
                "message": "热量值异常"
            })
        
        # 蛋白质范围检查（0-100g/100g）
        if recipe.get('protein', 0) < 0 or recipe.get('protein', 0) > 100:
            issues.append({
                "type": "nutrition_error",
                "field": "protein",
                "value": recipe.get('protein'),
                "message": "蛋白质值异常"
            })
        
        # 营养素总和检查
        total_macros = (
            recipe.get('protein', 0) * 4 +
            recipe.get('fat', 0) * 9 +
            recipe.get('carbs', 0) * 4
        )
        
        if abs(total_macros - recipe.get('calories', 0)) > 20:
            issues.append({
                "type": "nutrition_mismatch",
                "message": "营养素总和与热量不匹配"
            })
        
        return issues
    
    def check_ingredients(self, recipe):
        """校验食材"""
        issues = []
        
        ingredients = recipe.get('ingredients', [])
        
        # 食材数量检查
        if len(ingredients) < 2:
            issues.append({
                "type": "ingredient_warning",
                "message": "食材数量过少"
            })
        
        # 食材分量检查
        for ingredient in ingredients:
            if not self.has_valid_amount(ingredient):
                issues.append({
                    "type": "ingredient_warning",
                    "ingredient": ingredient,
                    "message": "食材分量信息缺失"
                })
        
        return issues
    
    def check_steps(self, recipe):
        """校验步骤"""
        issues = []
        
        steps = recipe.get('steps', [])
        
        # 步骤数量检查
        if len(steps) < 1:
            issues.append({
                "type": "step_error",
                "message": "烹饪步骤缺失"
            })
        
        # 步骤完整性检查
        for i, step in enumerate(steps):
            if len(step) < 5:
                issues.append({
                    "type": "step_warning",
                    "step": i + 1,
                    "message": "步骤描述过于简短"
                })
        
        return issues
    
    def calculate_credibility(self, recipe, issues):
        """计算可信度"""
        # 基础可信度
        base_credibility = DataCredibility.CREDIBILITY_SCORES.get(
            recipe.get('credibility_level', DataCredibility.USER_GENERATED),
            0.6
        )
        
        # 根据问题数量扣分
        error_count = sum(1 for issue in issues if issue['type'].endswith('error'))
        warning_count = sum(1 for issue in issues if issue['type'].endswith('warning'))
        
        penalty = error_count * 0.2 + warning_count * 0.1
        
        return max(0, base_credibility - penalty)
```

### 3.3 数据来源标记

```python
class DataSourceMarker:
    """数据来源标记器"""
    
    def mark_source(self, recipe, source_info):
        """标记数据来源"""
        recipe['data_source'] = {
            "source": source_info.get('source', 'unknown'),
            "credibility": source_info.get('credibility', 'user_generated'),
            "last_verified": source_info.get('last_verified'),
            "verification_count": source_info.get('verification_count', 0)
        }
        
        return recipe
    
    def get_source_priority(self):
        """获取来源优先级"""
        return [
            {"source": "中国食物成分表", "credibility": "official", "priority": 1},
            {"source": "USDA", "credibility": "official", "priority": 2},
            {"source": "薄荷营养", "credibility": "user_verified", "priority": 3},
            {"source": "下厨房", "credibility": "user_generated", "priority": 4},
            {"source": "小红书", "credibility": "user_generated", "priority": 5},
        ]
```

---

## 四、元数据补全

### 4.1 菜谱元数据完整定义

```json
{
  "recipe_id": "string - 唯一标识",
  "name": "string - 菜名",
  "category": "enum - 减脂/增肌/维持/素食/低碳水",
  "meal_type": "enum - 早餐/午餐/晚餐/加餐",
  "cuisine": "string - 菜系",
  "difficulty": "int - 难度等级(1-5)",
  "cook_time": "int - 烹饪时间(分钟)",
  "prep_time": "int - 准备时间(分钟)",
  "total_time": "int - 总时间(分钟)",
  
  "calories": "float - 热量(kcal/100g)",
  "protein": "float - 蛋白质(g/100g)",
  "fat": "float - 脂肪(g/100g)",
  "carbs": "float - 碳水(g/100g)",
  "fiber": "float - 膳食纤维(g/100g)",
  
  "ingredients": ["array - 食材列表"],
  "allergens": ["array - 过敏原列表"],
  "steps": ["array - 烹饪步骤"],
  
  "tags": ["array - 标签"],
  "suitable_for": ["array - 适用人群"],
  
  "ingredient_availability": "enum - 常见/一般/稀有",
  "is_takeout_friendly": "boolean - 是否适合外卖替代",
  "is_vegetarian": "boolean - 是否素食",
  "is_halal": "boolean - 是否清真",
  "cost_level": "int - 成本等级(1-5)",
  
  "data_source": {
    "source": "string - 数据来源",
    "credibility": "enum - 官方/用户验证/用户生成",
    "last_verified": "date - 最后验证时间"
  },
  
  "created_at": "datetime - 创建时间",
  "updated_at": "datetime - 更新时间"
}
```

### 4.2 用户画像元数据完整定义

```json
{
  "user_id": "string - 用户唯一标识",
  "created_at": "datetime - 创建时间",
  "last_updated": "datetime - 最后更新时间",
  
  "basic_info": {
    "gender": {"value": "enum", "confidence": "float", "source": "string"},
    "age": {"value": "int", "confidence": "float", "source": "string"},
    "height": {"value": "float", "confidence": "float", "source": "string"},
    "weight": {"value": "float", "confidence": "float", "source": "string"},
    "birth_date": {"value": "date", "confidence": "float", "source": "string"}
  },
  
  "health_info": {
    "medical_conditions": {"value": ["array"], "confidence": "float", "source": "string"},
    "food_allergies": {"value": ["array"], "confidence": "float", "source": "string"},
    "food_intolerances": {"value": ["array"], "confidence": "float", "source": "string"},
    "current_medications": {"value": ["array"], "confidence": "float", "source": "string"},
    "pregnancy_status": {"value": "enum", "confidence": "float", "source": "string"}
  },
  
  "fitness_info": {
    "fitness_goal": {"value": "enum", "confidence": "float", "source": "string"},
    "target_weight": {"value": "float", "confidence": "float", "source": "string"},
    "activity_level": {"value": "enum", "confidence": "float", "source": "string"},
    "exercise_frequency": {"value": "enum", "confidence": "float", "source": "string"},
    "exercise_types": {"value": ["array"], "confidence": "float", "source": "string"}
  },
  
  "preference_info": {
    "taste_preferences": {
      "spicy_level": {"value": "float", "confidence": "float", "source": "string"},
      "sweet_level": {"value": "float", "confidence": "float", "source": "string"},
      "salt_level": {"value": "float", "confidence": "float", "source": "string"},
      "sour_level": {"value": "float", "confidence": "float", "source": "string"}
    },
    "cooking_skill": {"value": "enum", "confidence": "float", "source": "string"},
    "cooking_time_preference": {"value": "enum", "confidence": "float", "source": "string"},
    "budget_level": {"value": "int", "confidence": "float", "source": "string"}
  },
  
  "nutrition_targets": {
    "calorie_target": "int - 每日热量目标",
    "protein_target": "float - 每日蛋白质目标",
    "fat_target": "float - 每日脂肪目标",
    "carbs_target": "float - 每日碳水目标"
  },
  
  "blacklist": {
    "ingredients": ["array - 禁用食材"],
    "recipes": ["array - 禁用菜谱"],
    "taste": ["array - 禁用口味"]
  },
  
  "feedback_summary": {
    "total_accepted": "int - 接受总数",
    "total_rejected": "int - 拒绝总数",
    "acceptance_rate": "float - 接受率",
    "favorite_recipes": ["array - 最喜欢的菜谱"],
    "disliked_recipes": ["array - 最不喜欢的菜谱"]
  }
}
```

### 4.3 饮食记录元数据

```json
{
  "record_id": "string - 记录唯一标识",
  "user_id": "string - 用户标识",
  "date": "date - 日期",
  
  "meal_type": "enum - 早餐/午餐/晚餐/加餐",
  "time": "time - 进食时间",
  
  "foods": [
    {
      "recipe_id": "string - 菜谱ID（如果有）",
      "name": "string - 食物名称",
      "amount": "float - 分量(g)",
      "calories": "float - 热量(kcal)",
      "protein": "float - 蛋白质(g)",
      "fat": "float - 脂肪(g)",
      "carbs": "float - 碳水(g)",
      "source": "enum - 自己做/外卖/餐厅"
    }
  ],
  
  "total_calories": "float - 本餐总热量",
  "total_protein": "float - 本餐总蛋白质",
  "total_fat": "float - 本餐总脂肪",
  "total_carbs": "float - 本餐总碳水",
  
  "satisfaction": "enum - 满意/一般/不满意",
  "notes": "string - 备注",
  
  "created_at": "datetime - 创建时间"
}
```

---

## 五、实现代码

### 5.1 完整的知识库管理器

```python
class KnowledgeBaseManager:
    """知识库管理器"""
    
    def __init__(self):
        self.public_kb = PublicKnowledgeBase()
        self.private_kbs = {}  # user_id -> UserPrivateKnowledgeBase
        self.quality_checker = RecipeQualityChecker()
    
    def initialize(self):
        """初始化知识库"""
        # 加载公共知识库
        self.public_kb.load_recipes()
        self.public_kb.load_nutrition_data()
        
        # 构建向量索引
        self.public_kb.build_index()
    
    def add_user(self, user_id):
        """添加用户"""
        self.private_kbs[user_id] = UserPrivateKnowledgeBase(user_id)
    
    def search(self, query, user_id, top_k=5):
        """搜索"""
        # 获取用户私有库
        private_kb = self.private_kbs.get(user_id)
        if not private_kb:
            return self.public_kb.search_recipes(query, top_k)
        
        # 混合检索
        retriever = HybridRetriever(self.public_kb, private_kb)
        return retriever.retrieve(query, top_k)
    
    def add_recipe(self, recipe):
        """添加菜谱"""
        # 质量校验
        quality_check = self.quality_checker.check_recipe(recipe)
        
        if not quality_check['is_safe']:
            return {
                "success": False,
                "reason": "菜谱质量不达标",
                "issues": quality_check['issues']
            }
        
        # 添加到公共知识库
        self.public_kb.add_recipe(recipe)
        
        return {"success": True}
    
    def update_index(self, update_type="incremental"):
        """更新索引"""
        if update_type == "incremental":
            self.public_kb.update_index_incremental()
        else:
            self.public_kb.rebuild_index()
```

import json
import hashlib
from datetime import datetime

# ============== 1. 读取菜谱数据 ==============
with open('data/raw/recipes.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
recipes = data['recipes']

# ============== 2. 分块函数 ==============
def chunk_recipe(recipe):
    """把一个菜谱分成多个块"""
    chunks = []

    # 块0：基础信息块
    basic_info = f"菜名：{recipe['name']}\n分类：{recipe['category']}\n餐次：{recipe['meal_type']}\n难度：{recipe['difficulty']}\n烹饪时间：{recipe['cook_time']}分钟\n热量：{recipe['calories']}kcal"
    chunks.append({
        'chunk_id': hashlib.md5(basic_info.encode()).hexdigest()[:8],
        'type': '基础信息',
        'title': f"{recipe['name']}>基础信息",
        'content': basic_info,
        'char_count': len(basic_info)
    })

    # 块1：食材块
    ingredients_str = '食材：' + '、'.join([f"{i['name']}{i['amount']}{i['unit']}" for i in recipe['ingredients']])
    allergens_str = f"\n过敏原：{'、'.join(recipe['allergens']) if recipe['allergens'] else '无'}"
    ingredients_content = ingredients_str + allergens_str
    chunks.append({
        'chunk_id': hashlib.md5(ingredients_content.encode()).hexdigest()[:8],
        'type': '食材',
        'title': f"{recipe['name']}>食材",
        'content': ingredients_content,
        'char_count': len(ingredients_content)
    })

    # 块2：步骤块
    steps_content = '步骤：\n' + '\n'.join([f"{i+1}.{step}" for i, step in enumerate(recipe['steps'])])
    chunks.append({
        'chunk_id': hashlib.md5(steps_content.encode()).hexdigest()[:8],
        'type': '步骤',
        'title': f"{recipe['name']}>步骤",
        'content': steps_content,
        'char_count': len(steps_content)
    })

    # 块3：营养块
    nutrition_content = f"热量：{recipe['calories']}kcal\n蛋白质：{recipe['protein']}g\n脂肪：{recipe['fat']}g\n碳水：{recipe['carbs']}g\n膳食纤维：{recipe['fiber']}g"
    chunks.append({
        'chunk_id': hashlib.md5(nutrition_content.encode()).hexdigest()[:8],
        'type': '营养',
        'title': f"{recipe['name']}>营养",
        'content': nutrition_content,
        'char_count': len(nutrition_content)
    })

    return chunks

# ============== 3. 对所有菜谱进行分块 ==============
all_chunks = {}
total_chars = 0
min_chars = float('inf')
max_chars = 0

for recipe in recipes:
    chunks = chunk_recipe(recipe)
    all_chunks[recipe['name']] = {
        'recipe': recipe,
        'chunks': chunks
    }
    for chunk in chunks:
        total_chars += chunk['char_count']
        min_chars = min(min_chars, chunk['char_count'])
        max_chars = max(max_chars, chunk['char_count'])

# ============== 4. 统计信息 ==============
total_docs = len(recipes)
total_chunks = sum(len(v['chunks']) for v in all_chunks.values())
avg_chars = total_chars // total_chunks

# 分类统计
categories = {}
for recipe in recipes:
    cat = recipe['category']
    categories[cat] = categories.get(cat, 0) + 1

# ============== 5. 输出结果 ==============
print("=" * 60)
print("           知识库分块总览")
print("=" * 60)
print(f"文档总数: {total_docs}篇")
print(f"分块总数: {total_chunks}块")
print(f"平均块大小: {avg_chars}字")
print(f"块大小范围: {min_chars}~{max_chars}字")
print()
print("分类分布:")
for cat, count in categories.items():
    print(f"  {cat}: {count}篇")
print()
print("文档清单:")
for i, recipe in enumerate(recipes, 1):
    name = recipe['name']
    cat = recipe['category']
    chunks = all_chunks[name]['chunks']
    total = sum(c['char_count'] for c in chunks)
    print(f"[{i}] 《{name}》 ({cat}) 全文{total}字→{len(chunks)}块")

# ============== 6. 交互：查看详情 ==============
print()
print("=" * 60)
print("输入编号查看分块详情，或输入 'all' 查看全部")
print("=" * 60)

user_input = input("> ").strip()

if user_input == 'all':
    # 显示所有菜谱详情
    for i, recipe in enumerate(recipes, 1):
        print()
        print(f"【{i}】《{recipe['name']}》的分块详情")
        print(f"来源文件: data/raw/recipes.json")
        print(f"recipe_id: {recipe['recipe_id']}")
        chunks = all_chunks[recipe['name']]['chunks']
        total = sum(c['char_count'] for c in chunks)
        print(f"全文 {total}字 → 切成 {len(chunks)} 块")
        print()
        for j, chunk in enumerate(chunks):
            preview = chunk['content'][:50] + '...' if len(chunk['content']) > 50 else chunk['content']
            print(f"第{j}块 chunk_id:{chunk['chunk_id']}... {chunk['char_count']}字")
            print(f"  标题路径:{chunk['title']}")
            print(f"  内容预览:{preview}")
            print()

elif user_input.isdigit():
    idx = int(user_input) - 1
    if 0 <= idx < len(recipes):
        recipe = recipes[idx]
        print()
        print(f"【{idx+1}】《{recipe['name']}》的分块详情")
        print(f"来源文件: data/raw/recipes.json")
        print(f"recipe_id: {recipe['recipe_id']}")
        chunks = all_chunks[recipe['name']]['chunks']
        total = sum(c['char_count'] for c in chunks)
        print(f"全文 {total}字 → 切成 {len(chunks)} 块")
        print()
        for j, chunk in enumerate(chunks):
            preview = chunk['content'][:80] + '...' if len(chunk['content']) > 80 else chunk['content']
            print(f"第{j}块 chunk_id:{chunk['chunk_id']}... {chunk['char_count']}字")
            print(f"  标题路径:{chunk['title']}")
            print(f"  内容预览:{preview}")
            print()
    else:
        print("编号超出范围！")
else:
    print("无效输入！")

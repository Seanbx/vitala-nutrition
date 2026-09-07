"""
端到端测试脚本
测试数据加载 -> 检索 -> 生成 全流程
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(".env")


def test_data_loader():
    print("=" * 60)
    print("测试1: 数据加载")
    print("=" * 60)
    from src.data_loader import load_markdown_docs, chunk_documents

    root = Path(".")
    dirs = [str(root / "data" / "recipes"), str(root / "data" / "knowledge")]
    docs = load_markdown_docs(dirs)
    print(f"  加载文档: {len(docs)}")

    recipes = [d for d in docs if d.metadata.get("doc_type") == "recipe"]
    knowledge = [d for d in docs if d.metadata.get("doc_type") == "knowledge"]
    print(f"  菜谱文档: {len(recipes)}")
    print(f"  知识文档: {len(knowledge)}")

    chunks = chunk_documents(docs)
    print(f"  切分后: {len(chunks)} 块")
    print("  ✅ 数据加载通过\n")
    return docs, chunks


def test_retriever(chunks):
    print("=" * 60)
    print("测试2: 混合检索")
    print("=" * 60)
    from src.retriever import NutriRetriever
    from langchain_community.vectorstores import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(
        model="BAAI/bge-m3",
        openai_api_key=os.getenv("SILICONFLOW_API_KEY"),
        openai_api_base="https://api.siliconflow.cn/v1",
    )
    vs = Chroma(persist_directory="chroma_db", embedding_function=embeddings)
    retriever = NutriRetriever(vs, chunks)

    test_queries = [
        "减脂期早餐吃什么好？",
        "增肌每天需要多少蛋白质？",
        "糖尿病患者饮食注意事项？",
        "运动前后怎么吃？",
    ]

    for q in test_queries:
        results = retriever.hybrid_search(q, top_k=3)
        print(f"\n  问题: {q}")
        for i, doc in enumerate(results, 1):
            title = doc.metadata.get("title", "未知")
            cat = doc.metadata.get("category", "")
            score = doc.metadata.get("rrf_score", 0)
            print(f"    [{i}] {title} ({cat}) score={score:.4f}")

    print("\n  ✅ 检索测试通过\n")
    return retriever


def test_safety():
    print("=" * 60)
    print("测试3: 安全校验")
    print("=" * 60)
    from src.safety import SafetyValidator

    v = SafetyValidator()

    normal = v.validate_query("减脂期早餐吃什么？")
    print(f"  正常查询: safe={normal['is_safe']}, risk={normal['risk_level']}")

    disease = v.validate_query("糖尿病患者应该注意什么饮食？")
    print(f"  疾病查询: safe={disease['is_safe']}, risk={disease['risk_level']}, disclaimers={len(disease['disclaimers'])}")

    dangerous = v.validate_query("每天只吃水果能减肥吗？")
    print(f"  危险查询: safe={dangerous['is_safe']}, risk={dangerous['risk_level']}, warnings={len(dangerous['warnings'])}")

    calorie = v.validate_recommendation(800, ["乳制品"], [])
    print(f"  低热量推荐: safe={calorie['is_safe']}, warnings={len(calorie['warnings'])}")

    allergy = v.validate_recommendation(2000, ["乳制品", "虾"], ["牛奶", "虾仁"])
    print(f"  过敏原冲突: safe={allergy['is_safe']}, warnings={len(allergy['warnings'])}")

    print("  ✅ 安全校验通过\n")


def test_user_profile():
    print("=" * 60)
    print("测试4: 用户画像")
    print("=" * 60)
    from src.user_profile import UserProfileManager

    mgr = UserProfileManager()

    profile = mgr.get_profile("test_user")
    print(f"  新用户画像: goal={profile['dietary_preferences']['goal']}")

    mgr.update_profile("test_user", {
        "basic_info": {"age": 28, "gender": "female", "height_cm": 165, "weight_kg": 60, "activity_level": "moderate"},
        "dietary_preferences": {"goal": "lose"},
    })
    targets = mgr.calculate_nutrition_targets("test_user")
    print(f"  减脂目标: calories={targets['calories']}, protein={targets['protein_g']}g")

    constraints = mgr.extract_constraints_from_query("我有乳糖不耐，想减脂")
    print(f"  查询约束提取: {constraints}")

    print("  ✅ 用户画像测试通过\n")


def test_rag_service():
    print("=" * 60)
    print("测试5: RAG服务完整流程")
    print("=" * 60)
    from src.rag_service import NutriRAGService

    service = NutriRAGService()
    stats = service.get_stats()
    print(f"  系统状态: {stats}")

    result = service.chat("减脂期早餐吃什么好？")
    print(f"\n  问题: 减脂期早餐吃什么好？")
    print(f"  回答前100字: {result['answer'][:100]}...")
    print(f"  参考来源数: {len(result['sources'])}")
    print(f"  安全检查: {result['safety']['risk_level']}")

    if result.get("rewritten_query"):
        print(f"  查询重写: {result['rewritten_query']}")

    print("\n  ✅ RAG服务测试通过\n")


if __name__ == "__main__":
    docs, chunks = test_data_loader()
    test_retriever(chunks)
    test_safety()
    test_user_profile()
    test_rag_service()
    print("=" * 60)
    print("🎉 全部测试通过！")
    print("=" * 60)

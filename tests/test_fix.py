import os, sys
os.chdir(r'C:\Users\Sean.bx\Desktop\project_based_training\nutri_assistant')
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

print("正在重建向量库...")
from src.rag_service import NutriRAGService
svc = NutriRAGService()

print("\n测试检索...")
r = svc.chat("减脂期早餐吃什么好？")
print(f"\n回答前150字:\n{r['answer'][:150]}")
print(f"\n参考来源:")
for s in r['sources']:
    print(f"  - {s['title']} ({s.get('category','')}) [{s.get('doc_type','')}]")
print(f"安全: {r['safety']['risk_level']}")

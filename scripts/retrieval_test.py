"""
营养助手RAG检索模块
流程：
  1. 读取菜谱和营养知识markdown文档
  2. 切成小块（chunk_size=500, overlap=50）
  3. 调用SiliconFlow的BGE-M3接口，把每块变成向量
  4. 存入Chroma（本地持久化）
  5. 输入问题，检索Top-K，观察返回块是否相关

运行前：确认 .env 里有 SILICONFLOW_API_KEY。
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

# 数据目录
BASE_DIR = Path(__file__).resolve().parents[1]
RECIPES_DIR = BASE_DIR / "data" / "recipes"
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
PERSIST_DIR = str(BASE_DIR / "chroma_db")  # 向量库落盘位置

# ============ 1. 通过 SiliconFlow 调用 BGE-M3 嵌入模型 ============
api_key = os.getenv("SILICONFLOW_API_KEY")
if not api_key or api_key.startswith("sk-xxx"):
    print("错误：请在 .env 文件中配置 SILICONFLOW_API_KEY")
    print("步骤：")
    print("1. 注册 https://cloud.siliconflow.cn/ 获取API Key")
    print("2. 复制 .env.example 为 .env")
    print("3. 在 .env 中填入你的API Key")
    exit(1)

embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    api_key=api_key,
    base_url="https://api.siliconflow.cn/v1",
)

# ============ 2. 加载菜谱文档 ============
print("=" * 60)
print("正在加载文档...")
print("=" * 60)

documents = []

# 加载减脂餐
print(f"加载减脂餐...")
loader = DirectoryLoader(
    str(RECIPES_DIR / "减脂餐"),
    glob="*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,
)
docs = loader.load()
documents.extend(docs)
print(f"  减脂餐：{len(docs)} 篇")

# 加载增肌餐
print(f"加载增肌餐...")
loader = DirectoryLoader(
    str(RECIPES_DIR / "增肌餐"),
    glob="*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,
)
docs = loader.load()
documents.extend(docs)
print(f"  增肌餐：{len(docs)} 篇")

# 加载维持餐
print(f"加载维持餐...")
loader = DirectoryLoader(
    str(RECIPES_DIR / "维持餐"),
    glob="*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,
)
docs = loader.load()
documents.extend(docs)
print(f"  维持餐：{len(docs)} 篇")

# 加载营养知识
print(f"加载营养知识...")
loader = DirectoryLoader(
    str(KNOWLEDGE_DIR),
    glob="*.md",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"},
    show_progress=True,
)
docs = loader.load()
documents.extend(docs)
print(f"  营养知识：{len(docs)} 篇")

print(f"\n共加载 {len(documents)} 个文档")

# ============ 3. 切分文档 ============
print("\n正在切分文档...")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
texts = text_splitter.split_documents(documents)
print(f"切分后共 {len(texts)} 块")

# ============ 4. 生成向量并持久化到 Chroma ============
print("\n正在生成向量（调用SiliconFlow BGE-M3）...")
db = Chroma.from_documents(
    documents=texts,
    embedding=embeddings,
    persist_directory=PERSIST_DIR,
)
print(f"已存入 Chroma：{db._collection.count()} 条向量")
print(f"存储目录：{PERSIST_DIR}")

# ============ 5. 检索测试 ============
print("\n" + "=" * 60)
print("检索测试")
print("=" * 60)

retriever = db.as_retriever(search_kwargs={"k": 3})

test_questions = [
    "减脂期早餐吃什么好？",
    "增肌期每天需要多少蛋白质？",
    "乳糖不耐受的人能吃什么高蛋白食物？",
    "红烧肉怎么做才不腻？",
    "糖尿病患者应该注意什么饮食？",
    "运动前后应该怎么吃？",
    "哪些食物蛋白质含量最高？",
    "减脂期晚餐吃什么？",
    "孕妇需要补充哪些营养？",
    "怎么计算每天需要多少热量？",
]

for question in test_questions:
    print("\n" + "=" * 60)
    print(f"问题：{question}")
    docs = retriever.invoke(question)
    print("-" * 60)
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知")
        # 提取文件名
        source_name = Path(source).name
        preview = doc.page_content[:100].replace("\n", " ")
        print(f"[Top{i}] 来源：{source_name}")
        print(f"       内容：{preview}...")

print("\n" + "=" * 60)
print("检索测试完成！")
print("=" * 60)

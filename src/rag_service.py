"""
RAG 服务层 —— 核心入口
整合数据加载、检索、生成、用户画像、安全校验
v2：索引复用（不再每次删除重建）、向量服务不可用时自动降级 BM25、
支持真实登录用户的个性化画像、流式回答
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

from langchain_core.documents import Document

from .data_loader import load_markdown_docs, chunk_documents
from .retriever import NutriRetriever
from .generator import NutriGenerator
from .user_profile import UserProfileManager, calculate_targets_from_profile
from .safety import SafetyValidator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIRS = [
    str(PROJECT_ROOT / "data" / "recipes"),
    str(PROJECT_ROOT / "data" / "knowledge"),
]
CHROMA_DIR = str(PROJECT_ROOT / "chroma_db")


class NutriRAGService:
    """营养助手 RAG 服务 —— 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.vectorstore = None
        self.retriever = None
        self.generator = None
        self.user_manager = UserProfileManager()
        self.safety = SafetyValidator()
        self._chunks: List[Document] = []

        self._build_index()
        self._init_generator()
        logger.info("NutriRAGService 初始化完成")

    def _build_index(self):
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
            openai_api_key=os.getenv("SILICONFLOW_API_KEY"),
            openai_api_base=os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"),
        )

        docs = load_markdown_docs(DATA_DIRS)
        logger.info(f"加载了 {len(docs)} 个文档")
        self._chunks = chunk_documents(docs)
        logger.info(f"切分后共 {len(self._chunks)} 块")

        force_rebuild = os.getenv("FORCE_REBUILD") == "1" or not Path(CHROMA_DIR).exists()
        if force_rebuild:
            logger.info("正在重建向量索引（首次运行或 FORCE_REBUILD=1）...")
            import shutil
            shutil.rmtree(CHROMA_DIR, ignore_errors=True)
            try:
                self.vectorstore = Chroma.from_documents(
                    documents=self._chunks,
                    embedding=embeddings,
                    persist_directory=CHROMA_DIR,
                )
            except Exception as e:
                logger.error(f"向量索引构建失败: {e}，将使用纯 BM25 检索")
                self.vectorstore = None
        else:
            try:
                self.vectorstore = Chroma(
                    persist_directory=CHROMA_DIR,
                    embedding_function=embeddings,
                )
                logger.info("已加载已有向量索引")
            except Exception as e:
                logger.error(f"加载向量索引失败: {e}，将使用纯 BM25 检索")
                self.vectorstore = None

        self.retriever = NutriRetriever(self.vectorstore, self._chunks)
        logger.info("检索器就绪")

    def _init_generator(self):
        try:
            self.generator = NutriGenerator()
        except Exception as e:
            logger.warning(f"LLM 初始化失败: {e}，将仅返回检索结果")

    # ------------------------------------------------------------------
    # 画像摘要（用于告诉大模型用户是谁，让回答真正个性化）
    # ------------------------------------------------------------------

    @staticmethod
    def build_profile_summary(profile: Optional[dict]) -> str:
        if not profile:
            return ""
        parts = []
        basic = profile.get("basic_info") or {}
        gender = basic.get("gender")
        age = basic.get("age")
        height = basic.get("height_cm")
        weight = basic.get("weight_kg")
        bf = basic.get("body_fat_pct")
        if gender:
            parts.append(f"性别:{gender}")
        if age:
            parts.append(f"年龄:{age}岁")
        if height:
            parts.append(f"身高:{height}cm")
        if weight:
            parts.append(f"体重:{weight}kg")
        if bf:
            parts.append(f"体脂率:{bf}%")
        if basic.get("activity_level"):
            parts.append(f"日常活动量:{basic['activity_level']}")

        prefs = profile.get("dietary_preferences") or {}
        if prefs.get("goal"):
            parts.append(f"目标:{prefs['goal']}")
        if prefs.get("dietary_type"):
            parts.append(f"饮食类型:{prefs['dietary_type']}")
        if prefs.get("disliked_foods"):
            parts.append(f"不喜欢的食物:{'、'.join(prefs['disliked_foods'])}")

        allergies = profile.get("allergies") or []
        if allergies:
            parts.append(f"过敏原:{'、'.join(allergies)}")
        conditions = profile.get("health_conditions") or []
        if conditions:
            parts.append(f"健康状况:{'、'.join(conditions)}")

        life = profile.get("lifestyle") or {}
        if life.get("exercise_types"):
            parts.append(f"运动类型:{'、'.join(life['exercise_types'])}")
        if life.get("water_goal_ml"):
            parts.append(f"每日饮水目标:{life['water_goal_ml']}ml")

        targets = profile.get("nutrition_targets") or {}
        if targets.get("calories"):
            parts.append(
                f"每日目标:热量{targets['calories']}kcal,"
                f"蛋白质{targets.get('protein_g', '-')}g,"
                f"脂肪{targets.get('fat_g', '-')}g,"
                f"碳水{targets.get('carbs_g', '-')}g"
            )

        if not parts:
            return ""
        return "用户画像: " + "；".join(parts) + "。请在建议中尽量贴合该用户的画像。"

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def _retrieve_docs(self, query: str, profile: Optional[dict], chat_history, use_rewrite: bool):
        constraints = self.user_manager.extract_constraints_from_query(query)

        search_query = query
        if use_rewrite and self.generator:
            try:
                search_query = self.generator.query_rewrite(query, chat_history)
            except Exception:
                pass

        filters = {}
        goal_map = {"lose": "减脂餐", "gain": "增肌餐", "maintain": "维持餐", "healthy": "维持餐"}
        prefs = (profile or {}).get("dietary_preferences") or {}
        goal = constraints.get("goal") or prefs.get("goal")
        if goal in goal_map:
            filters["category"] = goal_map[goal]

        if filters:
            docs = self.retriever.metadata_filter_search(search_query, filters)
            if not docs:
                docs = self.retriever.hybrid_search(search_query)
        else:
            docs = self.retriever.hybrid_search(search_query)
        return docs, search_query

    # ------------------------------------------------------------------
    # 对话
    # ------------------------------------------------------------------

    def chat(
        self,
        query: str,
        user_id: str = "default",
        profile: Optional[dict] = None,
        chat_history: Optional[List[dict]] = None,
        use_rewrite: bool = True,
    ) -> Dict:
        safety_result = self.safety.validate_query(query)
        if not safety_result["is_safe"]:
            return {
                "answer": self._build_safety_response(safety_result),
                "sources": [],
                "safety": safety_result,
                "rewritten_query": None,
            }

        prof = profile or self.user_manager.get_profile(user_id)
        docs, rewritten = self._retrieve_docs(query, prof, chat_history, use_rewrite)
        summary = self.build_profile_summary(prof)

        if self.generator:
            try:
                answer = self.generator.generate_answer(
                    query, docs, chat_history, profile_context=summary
                )
            except Exception as e:
                logger.error(f"生成失败: {e}")
                answer = self._build_fallback_answer(query, docs)
        else:
            answer = self._build_fallback_answer(query, docs)

        sources = self._build_sources(docs)
        return {
            "answer": answer,
            "sources": sources,
            "safety": safety_result,
            "rewritten_query": rewritten if rewritten != query else None,
        }

    async def stream_chat(
        self,
        query: str,
        user_id: str = "default",
        profile: Optional[dict] = None,
        chat_history: Optional[List[dict]] = None,
        use_rewrite: bool = True,
    ):
        safety_result = self.safety.validate_query(query)
        if not safety_result["is_safe"]:
            yield self._build_safety_response(safety_result)
            return

        prof = profile or self.user_manager.get_profile(user_id)
        docs, _ = self._retrieve_docs(query, prof, chat_history, use_rewrite)
        summary = self.build_profile_summary(prof)

        if self.generator:
            try:
                for chunk in self.generator.generate_answer_stream(
                    query, docs, chat_history, profile_context=summary
                ):
                    yield chunk
                return
            except Exception as e:
                logger.error(f"流式生成失败: {e}，回退到检索结果")

        answer = self._build_fallback_answer(query, docs)
        for piece in self._chunk_text(answer, size=12):
            yield piece

    @staticmethod
    def _chunk_text(text: str, size: int = 10):
        for i in range(0, len(text), size):
            yield text[i:i + size]

    def _build_sources(self, docs: List[Document]) -> List[dict]:
        sources = []
        seen = set()
        for doc in docs:
            meta = doc.metadata
            title = meta.get("title", "")
            if not title:
                src = meta.get("source", "")
                title = Path(src).stem if src else "未知来源"
            key = (title, meta.get("category", ""))
            if key in seen:
                continue
            seen.add(key)
            sources.append({
                "title": title,
                "category": meta.get("category", ""),
                "doc_type": meta.get("doc_type", ""),
                "score": round(meta.get("rrf_score", 0), 4),
            })
        return sources

    # ------------------------------------------------------------------
    # 兜底回答
    # ------------------------------------------------------------------

    def _build_fallback_answer(self, query: str, docs: List[Document]) -> str:
        if not docs:
            return (
                "抱歉，我在知识库里没有找到与「{q}」直接相关的资料。\n\n"
                "你可以尝试：\n"
                "- 换个说法，例如「减脂期早餐吃什么」\n"
                "- 询问具体的营养问题，例如「每天需要多少蛋白质」\n"
                "- 或者告诉我你的目标（减脂/增肌/保持健康）".format(q=query)
            )
        lines = []
        for i, doc in enumerate(docs[:4], 1):
            title = doc.metadata.get("title", Path(doc.metadata.get("source", "")).stem)
            text = doc.page_content.strip().replace("\n", " ")
            if len(text) > 220:
                text = text[:220] + "…"
            lines.append(f"### {i}. {title}\n{text}")
        return (
            "已为你找到以下相关内容（当前为知识库检索模式）：\n\n"
            + "\n\n".join(lines)
            + "\n\n> 提示：配置 LLM API Key 后，我可以为你生成更完整的个性化回答。"
        )

    def _build_safety_response(self, safety_result: dict) -> str:
        lines = ["为了你的健康安全，我需要先提醒你："]
        for w in safety_result.get("warnings", []):
            lines.append(f"- ⚠️ {w.get('type', '')}：{w.get('description', '')}")
        for d in safety_result.get("disclaimers", []):
            lines.append(f"- {d}")
        lines.append("\n建议你循序渐进，并在必要时咨询医生或营养师。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            "total_chunks": len(self._chunks),
            "has_generator": self.generator is not None,
            "has_vectorstore": self.vectorstore is not None,
            "docs": len(self._chunks),
        }
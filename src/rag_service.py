"""
RAG 服务层 —— 核心入口
整合数据加载、检索、生成、用户画像、安全校验
v2：索引复用（不再每次删除重建）、向量服务不可用时自动降级 BM25、
支持真实登录用户的个性化画像、流式回答
"""

import os
import json
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
        # 只有“模糊/口语化”问题才做 LLM 查询改写；可直接回答的明确问题直接检索，
        # 省掉一次大模型调用（速度提升一倍）
        import re as _re
        ambiguous = _re.compile(r"这个|那个|它|怎么吃|吃什么|喝什么|适合|能不能|该不|想|推荐|有什么|做法|怎样|如何|叫啥|是啥|哪种")
        if (use_rewrite and self.generator and len(query.strip()) >= 10
                and (ambiguous.search(query) or len(query.strip()) >= 30)):
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
        docs = self._prune_docs(query, docs)
        summary = self.build_profile_summary(prof)

        if self.generator:
            try:
                answer = self.generator.generate_answer(
                    query, docs, chat_history, profile_context=summary
                )
                prev_ans = self._prev_assistant(chat_history)
                if self._looks_corrupted(answer) or self._is_echo(answer, prev_ans):
                    logger.warning("检测到生成结果异常/复读，回退到检索回答")
                    answer = self._build_fallback_answer(query, docs)
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
        docs = self._prune_docs(query, docs)
        summary = self.build_profile_summary(prof)

        if self.generator:
            try:
                _buf = []
                for chunk in self.generator.generate_answer_stream(
                    query, docs, chat_history, profile_context=summary
                ):
                    _buf.append(chunk)
                    yield chunk
                full_ans = "".join(_buf)
                prev_ans = self._prev_assistant(chat_history)
                if self._looks_corrupted(full_ans) or self._is_echo(full_ans, prev_ans):
                    logger.warning("流式结果异常/复读，回退到检索回答")
                    answer = self._build_fallback_answer(query, docs)
                    for piece in self._chunk_text(answer, size=12):
                        yield piece
                yield self._src_marker(docs)
                return
            except Exception as e:
                logger.error(f"流式生成失败: {e}，回退到检索结果")

        answer = self._build_fallback_answer(query, docs)
        for piece in self._chunk_text(answer, size=12):
            yield piece
        yield self._src_marker(docs)

    @staticmethod
    def _chunk_text(text: str, size: int = 10):
        for i in range(0, len(text), size):
            yield text[i:i + size]

    @staticmethod
    def _prev_assistant(chat_history) -> str:
        if not chat_history:
            return ""
        for m in reversed(chat_history):
            if m and m.get("role") == "assistant" and m.get("content"):
                return str(m.get("content"))
        return ""

    @staticmethod
    def _is_echo(answer: str, prev: str) -> bool:
        a = (answer or "").strip()
        pv = (prev or "").strip()
        if not a or not pv:
            return False
        if a == pv:
            return True
        if len(a) >= 60 and a.startswith(pv[:60]):
            return True
        return False

    @staticmethod
    def _looks_corrupted(text: str) -> bool:
        """检测 LLM 输出是否退化/乱码（出现替换符，或中英文之间大量孤立 D 等）"""
        if not text:
            return False
        if "\ufffd" in text:
            return True
        cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        dcount = sum(1 for ch in text if ch == "D")
        if cjk > 30 and dcount > cjk * 0.2:
            return True
        # 大量重复单字（模型陷入复读）
        import re as _re
        m = _re.search(r"([\u4e00-\u9fff])\1{4,}", text)
        return bool(m)

    @staticmethod
    def _src_marker(docs: List[Document]) -> str:
        try:
            sources = []
            seen = set()
            for doc in docs:
                meta = doc.metadata
                title = meta.get("title", "")
                if not title:
                    src = meta.get("source", "")
                    title = Path(src).stem if src else "来源"
                key = (title, meta.get("category", ""))
                if key in seen:
                    continue
                seen.add(key)
                sources.append({
                    "title": title,
                    "category": meta.get("category", ""),
                    "doc_type": meta.get("doc_type", ""),
                })
            return "\n[[SRC]]" + json.dumps(sources, ensure_ascii=False)
        except Exception:
            return "\n[[SRC]][]"

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

    @staticmethod
    def _query_terms(query: str) -> List[str]:
        import jieba
        try:
            toks = [w.strip() for w in jieba.lcut(query) if len(w.strip()) >= 2]
        except Exception:
            toks = []
        return toks or [query]

    @staticmethod
    def _doc_relevance(query: str, doc: Document) -> int:
        title = doc.metadata.get("title", "") or ""
        text = doc.page_content[:200]
        hay = title + " " + text
        score = 0
        if title and title in query:
            score += 6
        for term in NutriRAGService._query_terms(query):
            if term in hay:
                score += 1
        # 特定人群条目：问题没提该人群时降权（避免把“孕妇/老人/肾病…”内容塞给普通用户）
        groups = ["孕妇", "老年", "儿童", "肾病", "糖尿病", "高血压", "痛风", "高血脂", "哺乳"]
        if any(g in title for g in groups) and not any(g in query for g in groups):
            score -= 3
        return score

    @classmethod
    def _prune_docs(cls, query: str, docs: List[Document]) -> List[Document]:
        """过滤掉与问题完全无关的资料（如把孕妇条目从普通问题里去掉）"""
        if not docs:
            return docs
        scored = [(cls._doc_relevance(query, d), i, d) for i, d in enumerate(docs)]
        relevant = [d for s, i, d in scored if s >= 2]
        if relevant:
            return relevant[:5]
        # 完全没有强相关时，保底给少量候选
        return docs[:3]

    @staticmethod
    def _doc_snippet(content: str, limit: int = 120) -> str:
        got = []
        for ln in content.splitlines():
            t = ln.strip()
            if not t or t.startswith("#") or t.startswith("```"):
                continue
            if len(t) >= 6:
                got.append(t)
            if len(got) >= 2:
                break
        if not got and content:
            got = [content.strip()[:80]]
        s = "；".join(got)
        return s if len(s) <= limit else s[:limit] + "…"

    def _build_fallback_answer(self, query: str, docs: List[Document]) -> str:
        """大模型不可用时的离线兜底：只挑与问题相关的资料，绝不乱贴无关内容"""
        if not docs:
            return (
                "抱歉，我在知识库里暂时没有找到和「{q}」直接相关的内容。\n\n"
                "你可以换一种问法，例如：\n"
                "- 减脂期早餐吃什么好？\n"
                "- 我每天需要多少蛋白质？\n"
                "- 清蒸鲈鱼怎么做？".format(q=query)
            )
        relevant = [(self._doc_relevance(query, d), i, d) for i, d in enumerate(docs)]
        relevant.sort(key=lambda x: (-x[0], x[1]))
        good = [d for s, i, d in relevant if s >= 2]
        if not good:
            return (
                "知识库里暂时没有和你这个问题直接相关的内容，我没有硬套不相关的结果给你。\n\n"
                "建议换个更具体的问法，比如带上菜名、食材或营养目标：\n"
                "- 清蒸鲈鱼怎么做？\n"
                "- 高蛋白的晚餐推荐\n"
                "- 减脂期适合喝什么汤？"
            )
        lines = []
        for d in good[:3]:
            meta = d.metadata
            title = meta.get("title", "")
            cat = meta.get("category", "")
            label = title + (f"（{cat}）" if cat and cat not in title else "")
            snippet = self._doc_snippet(d.page_content)
            lines.append(f"**{label}**：{snippet}")
        return (
            "知识库中找到这些与你问题相关的内容（当前大模型暂不可用，先给你离线简答）：\n\n"
            + "\n\n".join(lines)
            + "\n\n如果觉得不够，可以再问得具体一点（带菜名/食材/目标），或检查网络后重试完整回答。"
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
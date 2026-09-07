"""
生成模块
负责查询重写、上下文构建、LLM回答生成（支持注入用户画像）
"""

import os
import logging
from typing import List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位专业的智能营养师助手。请根据营养参考资料、用户画像和历史对话，为用户提供详细的饮食建议。

回答要求：
1. 必须基于参考资料回答，资料中没有的信息不要编造
2. 如果资料不足，请诚实说明
3. 语言通俗易懂，避免堆砌专业术语
4. 涉及疾病（糖尿病、高血压、肾病等）时，提醒用户咨询医生
5. 如果当前问题是对历史对话的追问，请结合上下文理解
6. 回答要具体实用，包含可操作的建议
7. 如果提供了用户画像，建议要贴合该用户的年龄、目标、过敏原与生活习惯；不要暴露你不知道的信息"""

HUMAN_PROMPT = """历史对话：
{chat_history}

用户画像信息：
{user_profile}

当前问题: {question}

相关营养参考资料:
{context}

请灵活组织回答，建议包含以下部分（可根据实际内容调整）：

## 营养建议
[针对用户问题的具体饮食建议]

## 推荐食材/食谱
[从参考资料中提取相关的食材或食谱推荐]

## 注意事项
[相关的饮食禁忌、过敏提醒或健康提示]

回答:"""

QUERY_REWRITE_PROMPT = PromptTemplate(
    template="""你是一个智能查询分析助手。请分析用户的查询，判断是否需要重写以提高营养文档检索效果。

历史对话：
{history}

原始查询: {query}

分析规则：
1. **具体明确的查询**（直接返回原查询）：
   - 包含具体食材或菜品名称：如"西兰花怎么做好吃"
   - 明确的营养问题：如"蛋白质每天需要多少"
   - 具体的健康场景：如"糖尿病能吃水果吗"

2. **模糊不清的查询**（需要重写）：
   - 过于宽泛：如"吃什么"、"怎么吃"
   - 口语化表达：如"想瘦"、"健身吃啥"

3. **追问或指代**（结合历史对话改写成独立查询）：
   - 当前查询含"它/这个/那种"等指代
   - 从历史对话中找到指代对象，替换成具体名称

重写原则：保持原意不变，补充具体营养术语，保持简洁

请输出最终查询（如果不需要重写就返回原查询）:""",
    input_variables=["query", "history"],
)


def _make_chain():
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])


class NutriGenerator:
    """营养助手生成器"""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.llm = None
        self._init_llm()

    def _init_llm(self):
        api_key = os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            raise ValueError("请设置 SILICONFLOW_API_KEY 环境变量")
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1"),
        )
        logger.info(f"LLM 初始化完成: {self.model_name}")

    @staticmethod
    def _make_input(context: str, history_text: str, profile_context: str):
        from langchain_core.runnables import RunnableParallel
        return RunnableParallel(
            question=RunnablePassthrough(),
            context=lambda _: context,
            chat_history=lambda _: history_text,
            user_profile=lambda _: profile_context or "暂无。",
        )

    def generate_answer(
        self,
        query: str,
        context_docs: List[Document],
        chat_history: Optional[List[dict]] = None,
        profile_context: str = "",
    ) -> str:
        context = self._build_context(context_docs)
        history_text = self._build_history(chat_history)
        chain = self._make_input(context, history_text, profile_context) | _make_chain() | self.llm | StrOutputParser()
        return chain.invoke(query)

    def generate_answer_stream(
        self,
        query: str,
        context_docs: List[Document],
        chat_history: Optional[List[dict]] = None,
        profile_context: str = "",
    ):
        context = self._build_context(context_docs)
        history_text = self._build_history(chat_history)
        chain = self._make_input(context, history_text, profile_context) | _make_chain() | self.llm | StrOutputParser()
        for chunk in chain.stream(query):
            yield chunk

    def query_rewrite(self, query: str, chat_history: Optional[List[dict]] = None) -> str:
        history_text = self._build_history(chat_history) if chat_history else "暂无历史对话。"
        chain = (
            {"query": RunnablePassthrough(), "history": lambda _: history_text}
            | QUERY_REWRITE_PROMPT
            | self.llm
            | StrOutputParser()
        )
        response = chain.invoke(query).strip()
        if response != query:
            logger.info(f"查询重写: '{query}' -> '{response}'")
        return response

    @staticmethod
    def _build_context(docs: List[Document], max_length: int = 3000) -> str:
        if not docs:
            return "暂无相关营养参考资料。"
        parts = []
        current = 0
        for i, doc in enumerate(docs, 1):
            meta_info = f"【参考{i}】"
            if "title" in doc.metadata:
                meta_info += f" {doc.metadata['title']}"
            if "category" in doc.metadata:
                meta_info += f" | {doc.metadata['category']}"
            text = f"{meta_info}\n{doc.page_content}\n"
            if current + len(text) > max_length:
                break
            parts.append(text)
            current += len(text)
        return "\n" + "=" * 50 + "\n" + "\n".join(parts)

    @staticmethod
    def _build_history(chat_history: Optional[List[dict]] = None, max_turns: int = 5) -> str:
        if not chat_history:
            return "暂无历史对话。"
        recent = chat_history[-max_turns * 2:]
        lines = []
        for msg in recent:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                lines.append(f"用户：{content}")
            elif role == "assistant":
                lines.append(f"助手：{content}")
        return "\n".join(lines) if lines else "暂无历史对话。"
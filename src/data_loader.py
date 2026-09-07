"""
数据加载与分块模块
负责加载Markdown文档，进行语义分块，构建元数据
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

RECIPE_CATEGORIES = ["减脂餐", "增肌餐", "维持餐"]


def _extract_metadata_from_content(content: str, filepath: str) -> dict:
    """从文档内容和路径提取元数据"""
    meta = {"source": filepath}
    fname = Path(filepath).stem
    meta["title"] = fname

    if "知识" in filepath or "knowledge" in filepath:
        meta["doc_type"] = "knowledge"
    elif any(cat in filepath for cat in RECIPE_CATEGORIES):
        meta["doc_type"] = "recipe"
    else:
        meta["doc_type"] = "other"

    for cat in RECIPE_CATEGORIES:
        if cat in filepath:
            meta["category"] = cat
            break

    for keyword, label in [
        ("早餐", "breakfast"), ("午餐", "lunch"),
        ("晚餐", "dinner"), ("加餐", "snack"),
    ]:
        if keyword in fname:
            meta["meal_type"] = label
            break

    tags = []
    tag_patterns = {
        "低卡": "low_cal", "高蛋白": "high_protein", "高纤": "high_fiber",
        "低脂": "low_fat", "低碳": "low_carb", "补铁": "iron_rich",
        "补钙": "calcium_rich", "控糖": "sugar_control", "快手": "quick",
    }
    for cn, en in tag_patterns.items():
        if cn in content[:200]:
            tags.append(en)
    if tags:
        meta["tags"] = tags

    return meta


def load_markdown_docs(data_dirs: List[str]) -> List[Document]:
    """从多个目录递归加载所有 .md 文件"""
    docs = []
    for data_dir in data_dirs:
        md_files = list(Path(data_dir).rglob("*.md"))
        for fp in md_files:
            try:
                content = fp.read_text(encoding="utf-8")
                if not content.strip():
                    continue
                meta = _extract_metadata_from_content(content, str(fp))
                docs.append(Document(page_content=content, metadata=meta))
            except Exception as e:
                logger.warning(f"加载失败 {fp}: {e}")
    return docs


def chunk_documents(
    docs: List[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[Document]:
    """将文档列表切分为小块"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n## ", "\n### ", "\n- ", "\n", "。", "！", "？", ".", " "],
    )
    chunks = splitter.split_documents(docs)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i
    return chunks

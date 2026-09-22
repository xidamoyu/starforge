"""
Rerank 模块：用 CrossEncoder 对候选做 query-document 交叉打分。

与向量检索的区别：
    向量检索  双塔结构，query 与 doc 各自编码后算余弦 → 快，但无交互
    Rerank    CrossEncoder，query 与 doc 拼接后过模型 → 慢，但有交叉注意力，更准

设计要点：
    - 模型：BAAI/bge-reranker-v2-m3（本地 CPU 推理）
    - 懒加载单例，避免每次请求重复加载（加载耗时约 2 秒）
    - 模型与开关由 .env 控制：RERANK_MODEL / RERANK_ENABLED
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

_model = None


def is_enabled():
    return os.getenv("RERANK_ENABLED", "true").lower() in ("1", "true", "yes")


def get_model():
    """懒加载 CrossEncoder（进程内单例）。"""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder  # 延迟导入，避免无 rerank 时也加载 torch
        _model = CrossEncoder(RERANK_MODEL)
    return _model


def rerank(query, docs, top_k=None, text_key="text"):
    """
    对 (query, doc) 对打分，按相关性降序返回。

    docs:      [{"text": "...", ...}, ...]（原结构保留）
    text_key:  取哪个字段作为 document 文本
    返回:      [{"doc": 原始项, "rerank_score": float}, ...]
    """
    if not query or not docs:
        return [{"doc": d, "rerank_score": None} for d in docs]

    model = get_model()
    pairs = [(query, d.get(text_key) or "") for d in docs]
    scores = model.predict(pairs)

    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    if top_k:
        ranked = ranked[:top_k]
    return [{"doc": d, "rerank_score": float(s)} for d, s in ranked]

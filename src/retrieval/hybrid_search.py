"""
步骤⑤：混合检索 L1-A（先 SQL 硬过滤 → 再向量检索）

链路：
    需求解析（LLM）→ 澄清拦截（一次反问/搁置）→ SQL 硬过滤 → 向量检索排序

可溯源：结果中的 matches 绑定 source_table / record_id / field 与命中原文。
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

import chromadb
import psycopg
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.core.llm import apply_coop_mode, parse_requirement  # noqa: E402
from src.retrieval.rerank import is_enabled as rerank_enabled  # noqa: E402
from src.retrieval.rerank import rerank  # noqa: E402

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "starforge_creators")

# 线上检索默认策略（可用 .env 的 SEARCH_STRATEGY 覆盖）。
# hybrid_rerank：消融实测 MRR 0.715 → 0.950、Recall@1 0.45 → 0.65（见 docs 步骤⑦评测结论）
SEARCH_STRATEGY = os.getenv("SEARCH_STRATEGY", "hybrid_rerank")

# hard_filters 字段 → creators 表列（数值范围）
RANGE_FIELDS = {
    "followers": "followers",
    "female_ratio": "female_ratio",
    "age_18_24_ratio": "age_18_24_ratio",
    "age_25_34_ratio": "age_25_34_ratio",
    "avg_views": "avg_views",
    "engagement_rate": "engagement_rate",
    "quote_embed_15s": "quote_embed_15s",
    "quote_embed_30s": "quote_embed_30s",
    "quote_embed_60s": "quote_embed_60s",
    "quote_custom": "quote_custom",
}


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def embed(text):
    r = requests.post(f"{OLLAMA_BASE}/api/embed",
                      json={"model": EMBED_MODEL, "input": [text]}, timeout=300)
    r.raise_for_status()
    return r.json()["embeddings"][0]


def build_where(hf):
    """hard_filters → (WHERE 子句, 参数列表)，字段未提及则不过滤"""
    conds, params = [], []
    for key, col in RANGE_FIELDS.items():
        v = hf.get(key)
        if isinstance(v, dict):
            if v.get("min") is not None:
                conds.append(f"{col} >= %s")
                params.append(v["min"])
            if v.get("max") is not None:
                conds.append(f"{col} <= %s")
                params.append(v["max"])
    for key, col in [("category", "category"), ("platform", "platform"), ("region", "region")]:
        v = hf.get(key)
        if v:
            arr = v if isinstance(v, list) else [v]
            conds.append(f"{col} = ANY(%s)")
            params.append(arr)
    # coop_models：数组交集过滤（对齐可靠，保留）
    v = hf.get("coop_models")
    if v:
        arr = v if isinstance(v, list) else [v]
        conds.append("coop_models && %s")
        params.append(arr)
    # 注：sub_categories 不做 SQL 硬过滤——LLM 生成词与库标签词对齐不可靠（如"成分党"vs"成分分析"），
    #     其语义由 semantic_query 向量检索覆盖。
    return (" AND ".join(conds) if conds else "TRUE"), params


def sql_filter(hf):
    """SQL 硬过滤 creators，返回结构化信息列表"""
    where, params = build_where(hf)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT creator_id, nickname, platform, category, followers, female_ratio,
                   quote_embed_15s, quote_embed_30s, quote_embed_60s, quote_custom, region
            FROM creators WHERE {where} ORDER BY followers DESC
        """, params)
        cols = [d[0] for d in cur.description]
        rows = []
        for raw in cur.fetchall():
            row = dict(zip(cols, raw))
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = float(v)
            rows.append(row)
        return rows


def vector_rank(semantic_query, creator_ids, top_k):
    """在 SQL 候选集内做向量检索，返回命中的 (creator_id, field, chunk, distance) 列表"""
    if not semantic_query or not creator_ids:
        return []
    vec = embed(semantic_query)
    client = chromadb.PersistentClient(path=str(ROOT / CHROMA_PATH))
    col = client.get_collection(CHROMA_COLLECTION)
    res = col.query(
        query_embeddings=[vec],
        n_results=top_k,
        where={"$and": [{"source_table": "creators"}, {"record_id": {"$in": creator_ids}}]},
        include=["metadatas", "documents", "distances"],
    )
    out = []
    for i in range(len(res["ids"][0])):
        m = res["metadatas"][0][i]
        out.append({
            "creator_id": m["record_id"],
            "field": m["field"],
            "chunk": res["documents"][0][i],
            "distance": res["distances"][0][i],
        })
    return out


def _collect(hf, semantic_query, recall_k, use_filter=True):
    """SQL 硬过滤 + 向量召回，返回 (候选达人列表, {creator_id: [命中块]})"""
    candidates = sql_filter(hf if use_filter else {})
    cids = [c["creator_id"] for c in candidates]
    hits = vector_rank(semantic_query, cids, recall_k)
    by_creator = {}
    for h in hits:
        by_creator.setdefault(h["creator_id"], []).append(h)
    return candidates, by_creator


def _by_distance(candidates, by_creator):
    """向量检索的默认排序：最佳命中距离优先，其次粉丝数"""
    def key(c):
        hs = by_creator.get(c["creator_id"], [])
        return (min(x["distance"] for x in hs) if hs else 1.0, -int(c["followers"] or 0))
    return sorted(candidates, key=key)


def search(requirement_text, coop_mode=None, top_k=10, strategy="hybrid"):
    """混合检索主入口。

    strategy（供消融实验切换，见 docs/V2-查询流设计.md）：
        vector_only    纯向量检索，跳过 SQL 硬过滤（基线）
        hybrid         SQL 硬过滤 → 向量检索（L1-A，默认）
        hybrid_rerank  在 hybrid 基础上加 CrossEncoder 重排
        union          hybrid ∪ 纯向量（L1-C 双路并集）

    coop_mode: "placement" / "custom" / None（None=一次反问后用户不答，搁置该字段）
    """
    parsed = parse_requirement(requirement_text)
    # 仅当解析结果确实存在「植入/定制」澄清反问时，才应用一次澄清（含搁置）
    need = parsed.get("need_clarification", [])
    if any(("植入" in q and "定制" in q) for q in need):
        parsed = apply_coop_mode(parsed, coop_mode)
    hf = parsed.get("hard_filters", {})
    semantic_query = parsed.get("semantic_query", "")

    if strategy == "vector_only":
        cand, bc = _collect(hf, semantic_query, top_k, use_filter=False)
        result = [{**c, "matches": bc.get(c["creator_id"], [])}
                  for c in _by_distance(cand, bc)[:top_k]]
        return {"parsed": parsed, "sql_count": None, "strategy": strategy, "result": result}

    if strategy == "union":
        c1, b1 = _collect(hf, semantic_query, top_k, use_filter=True)
        c2, b2 = _collect(hf, semantic_query, top_k, use_filter=False)
        merged = {c["creator_id"]: c for c in c1}
        for c in c2:
            merged.setdefault(c["creator_id"], c)
        b = {**b2, **b1}
        result = [{**c, "matches": b.get(c["creator_id"], [])}
                  for c in _by_distance(list(merged.values()), b)[:top_k]]
        return {"parsed": parsed, "sql_count": len(c1), "strategy": strategy, "result": result}

    # hybrid / hybrid_rerank
    # RERANK_ENABLED=false 时 hybrid_rerank 退化为 hybrid——让开关能真正关掉 rerank
    use_rerank = strategy == "hybrid_rerank" and rerank_enabled()
    recall_k = max(top_k * 3, 30) if use_rerank else top_k
    cand, bc = _collect(hf, semantic_query, recall_k, use_filter=True)

    if use_rerank:
        docs = []
        for c in cand:
            hs = bc.get(c["creator_id"], [])
            # 取该达人「最佳命中块」作为重排文本；无命中则退回画像文本
            text = min(hs, key=lambda x: x["distance"])["chunk"] if hs else (c.get("profile_text") or "")
            if text:
                docs.append({"creator_id": c["creator_id"], "text": text})
        ordered = rerank(semantic_query, docs, top_k=top_k)
        cmap = {c["creator_id"]: c for c in cand}
        result = [{**cmap[r["doc"]["creator_id"]],
                   "matches": bc.get(r["doc"]["creator_id"], []),
                   "rerank_score": r["rerank_score"]} for r in ordered]
    else:
        result = [{**c, "matches": bc.get(c["creator_id"], [])}
                  for c in _by_distance(cand, bc)]

    # strategy 字段如实反映实际生效的策略（rerank 被开关关闭时降级为 hybrid）
    actual = "hybrid_rerank" if use_rerank else ("hybrid" if strategy == "hybrid_rerank" else strategy)
    return {"parsed": parsed, "sql_count": len(cand), "strategy": actual, "result": result}


def get_traits(creator_id):
    """查达人已验证注意事项，按 critical > warning > info 排序"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT trait_id, trait_category, trait_content, severity, source_quote
            FROM party_traits
            WHERE party_type = 'creator' AND party_id = %s AND verified = TRUE
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, trait_id
        """, (creator_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def build_reasons(requirement_text, coop_mode=None, top_k=10, strategy=None):
    """步骤⑥：生成可溯源推荐理由。

    不做二次生成，只列事实条目：
      - match：语义命中的字段原文（绑定 field 名，可回溯到 creators 文本字段）
      - trait：达人注意事项（绑定 trait_id / source_quote，critical 优先）
      - profile：结构化字段（硬过滤佐证）
    禁止伪精度评分（不输出"匹配度 82%"这类数字）。

    strategy：默认取 SEARCH_STRATEGY（hybrid_rerank），线上路径启用 rerank。
    """
    r = search(requirement_text, coop_mode, top_k, strategy=strategy or SEARCH_STRATEGY)
    items = []
    for c in r["result"]:
        reasons = []
        for m in c["matches"]:
            reasons.append({"type": "match", "field": m["field"], "quote": m["chunk"]})
        for t in get_traits(c["creator_id"]):
            reasons.append({
                "type": "trait",
                "severity": t["severity"],
                "category": t["trait_category"],
                "content": t["trait_content"],
                "source_quote": t["source_quote"],
                "trait_id": t["trait_id"],
            })
        profile = {
            "followers": c["followers"],
            "female_ratio": c["female_ratio"],
            "quote_embed_30s": c["quote_embed_30s"],
            "quote_custom": c["quote_custom"],
            "category": c["category"],
            "platform": c["platform"],
        }
        items.append({
            "creator_id": c["creator_id"],
            "nickname": c["nickname"],
            "profile": profile,
            "reasons": reasons,
        })
    return {
        "parsed": r["parsed"],
        "sql_count": r["sql_count"],
        "items": items,
    }

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

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "starforge_creators")

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


def search(requirement_text, coop_mode=None, top_k=10):
    """混合检索主入口。

    coop_mode: "placement" / "custom" / None（None=一次反问后用户不答，搁置该字段）
    """
    parsed = parse_requirement(requirement_text)
    # 仅当解析结果确实存在「植入/定制」澄清反问时，才应用一次澄清（含搁置）
    need = parsed.get("need_clarification", [])
    if any(("植入" in q and "定制" in q) for q in need):
        parsed = apply_coop_mode(parsed, coop_mode)
    hf = parsed.get("hard_filters", {})
    semantic_query = parsed.get("semantic_query", "")

    candidates = sql_filter(hf)
    cids = [c["creator_id"] for c in candidates]
    hits = vector_rank(semantic_query, cids, top_k)

    by_creator = {}
    for h in hits:
        by_creator.setdefault(h["creator_id"], []).append(h)

    def sort_key(c):
        hs = by_creator.get(c["creator_id"], [])
        return (min(x["distance"] for x in hs) if hs else 1.0, -int(c["followers"] or 0))

    ranked = sorted(candidates, key=sort_key)
    result = [{**c, "matches": by_creator.get(c["creator_id"], [])} for c in ranked]

    return {
        "parsed": parsed,
        "sql_count": len(candidates),
        "result": result,
    }


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


def build_reasons(requirement_text, coop_mode=None, top_k=10):
    """步骤⑥：生成可溯源推荐理由。

    不做二次生成，只列事实条目：
      - match：语义命中的字段原文（绑定 field 名，可回溯到 creators 文本字段）
      - trait：达人注意事项（绑定 trait_id / source_quote，critical 优先）
      - profile：结构化字段（硬过滤佐证）
    禁止伪精度评分（不输出"匹配度 82%"这类数字）。
    """
    r = search(requirement_text, coop_mode, top_k)
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

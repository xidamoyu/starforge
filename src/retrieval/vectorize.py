"""
步骤③：向量化入 ChromaDB

把 creators / deals / deal_reviews / brands / party_traits 的文本字段切块并 embedding，
写入 ChromaDB（本地持久化）。

设计要点（可溯源）：
    - 文档 ID = "{source_table}:{record_id}:{field}:{chunk_index}"，直接绑定表+记录+字段
    - metadata 存 source_table / record_id / field 及展示字段，是可溯源理由的实现基础
    - 切块上限 2500 字符（依据 bge-m3 截断验证结论：有效输入约 3072 中文字，留余量）
    - 单 collection 存 5 张表，用 metadata.source_table 区分

用法：
    .venv\\Scripts\\python.exe src/retrieval/vectorize.py
"""
import os
from pathlib import Path

import chromadb
import psycopg
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "starforge_creators")
CHUNK_SIZE = 2500  # 块上限（字符），留余量


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def chunk_text(text, size=CHUNK_SIZE):
    """按字符切块（V1 简单定长切；种子数据字段短，不会触发）"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    return [text[i:i + size] for i in range(0, len(text), size)]


def embed_texts(texts):
    """分批调 Ollama embedding，返回与输入同序的向量列表"""
    out = []
    for i in range(0, len(texts), 32):
        batch = texts[i:i + 32]
        r = requests.post(
            f"{OLLAMA_BASE}/api/embed",
            json={"model": EMBED_MODEL, "input": batch},
            timeout=600,
        )
        r.raise_for_status()
        out.extend(r.json()["embeddings"])
    return out


def build_docs(conn):
    """从 PG 读 5 张表，产出 (doc_id, text, metadata) 三元组列表"""
    docs = []
    with conn.cursor() as cur:
        # creators
        cur.execute("""
            SELECT creator_id, nickname, platform, category,
                   profile_text, content_style, past_brands, cooperation_history
            FROM creators
        """)
        for row in cur.fetchall():
            cid, nick, platform, category = row[0], row[1], row[2], row[3]
            for field, text in zip(
                ["profile_text", "content_style", "past_brands", "cooperation_history"],
                row[4:8],
            ):
                if not text:
                    continue
                meta = {
                    "source_table": "creators", "record_id": cid, "field": field,
                    "creator_id": cid, "nickname": nick or "",
                    "platform": platform or "", "category": category or "",
                }
                for ci, chunk in enumerate(chunk_text(text)):
                    docs.append((f"creators:{cid}:{field}:{ci}", chunk, {**meta, "chunk_index": ci}))

        # deals
        cur.execute("""
            SELECT deal_id, title, brand_id, creator_id, requirement_text, negotiation_notes
            FROM deals
        """)
        for row in cur.fetchall():
            did, title, bid, cid = row[0], row[1], row[2], row[3]
            for field, text in zip(["requirement_text", "negotiation_notes"], row[4:6]):
                if not text:
                    continue
                meta = {
                    "source_table": "deals", "record_id": did, "field": field,
                    "deal_id": did, "title": title or "",
                    "brand_id": bid or "", "creator_id": cid or "",
                }
                for ci, chunk in enumerate(chunk_text(text)):
                    docs.append((f"deals:{did}:{field}:{ci}", chunk, {**meta, "chunk_index": ci}))

        # deal_reviews
        cur.execute("""
            SELECT review_id, deal_id, reviewer_role, content FROM deal_reviews
        """)
        for row in cur.fetchall():
            rid, did, role, content = row[0], row[1], row[2], row[3]
            if not content:
                continue
            meta = {
                "source_table": "deal_reviews", "record_id": rid, "field": "content",
                "review_id": rid, "deal_id": did or "", "reviewer_role": role or "",
            }
            for ci, chunk in enumerate(chunk_text(content)):
                docs.append((f"deal_reviews:{rid}:content:{ci}", chunk, {**meta, "chunk_index": ci}))

        # brands
        cur.execute("""
            SELECT brand_id, brand_name, cooperation_notes FROM brands
        """)
        for row in cur.fetchall():
            bid, name, notes = row[0], row[1], row[2]
            if not notes:
                continue
            meta = {
                "source_table": "brands", "record_id": bid, "field": "cooperation_notes",
                "brand_id": bid, "brand_name": name or "",
            }
            for ci, chunk in enumerate(chunk_text(notes)):
                docs.append((f"brands:{bid}:cooperation_notes:{ci}", chunk, {**meta, "chunk_index": ci}))

        # party_traits（仅 verified=TRUE）
        cur.execute("""
            SELECT trait_id, party_type, party_id, trait_category, trait_content, severity
            FROM party_traits WHERE verified = TRUE
        """)
        for row in cur.fetchall():
            tid, ptype, pid, cat, content, sev = row
            if not content:
                continue
            meta = {
                "source_table": "party_traits", "record_id": tid, "field": "trait_content",
                "trait_id": tid, "party_type": ptype or "", "party_id": pid or "",
                "trait_category": cat or "", "severity": sev or "",
            }
            for ci, chunk in enumerate(chunk_text(content)):
                docs.append((f"party_traits:{tid}:trait_content:{ci}", chunk, {**meta, "chunk_index": ci}))

    return docs


def main():
    print("=" * 78)
    print(f"向量化入 ChromaDB　collection={CHROMA_COLLECTION}　模型={EMBED_MODEL}")
    print("=" * 78)

    conn = get_conn()
    docs = build_docs(conn)
    conn.close()
    print(f"从数据库构造 {len(docs)} 个文本块（切块上限 {CHUNK_SIZE} 字符）")

    if not docs:
        print("[FAIL] 没有可向量化的文本")
        return

    ids = [d[0] for d in docs]
    texts = [d[1] for d in docs]
    metadatas = [d[2] for d in docs]

    print("开始 embedding（分批调 Ollama）...")
    embeddings = embed_texts(texts)
    print(f"embedding 完成：{len(embeddings)} 个向量，维度 {len(embeddings[0])}")

    client = chromadb.PersistentClient(path=str(ROOT / CHROMA_PATH))
    col = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)

    print(f"\n[完成] 写入 {col.count()} 条向量到 collection '{CHROMA_COLLECTION}'")
    print(f"持久化路径：{ROOT / CHROMA_PATH}")


if __name__ == "__main__":
    main()

"""
步骤③验证：向量库检索可用性 + 可溯源 metadata

用几个查询验证 ChromaDB 能返回语义相关结果，且每条结果带溯源 metadata。

用法：
    .venv\\Scripts\\python.exe eval/verify_vector.py
"""
import os
from pathlib import Path

import chromadb
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "starforge_creators")


def embed(text):
    r = requests.post(f"{OLLAMA_BASE}/api/embed",
                      json={"model": EMBED_MODEL, "input": [text]}, timeout=300)
    r.raise_for_status()
    return r.json()["embeddings"][0]


def main():
    client = chromadb.PersistentClient(path=str(ROOT / CHROMA_PATH))
    col = client.get_collection(CHROMA_COLLECTION)
    print(f"collection '{CHROMA_COLLECTION}' 共 {col.count()} 条\n")

    queries = [
        "找一个美妆达人做平价敏感肌护肤品的真实测评",
        "达人要求先试用产品才决定接不接单",
        "甲方要求素材可二次用于电商详情页",
    ]
    for q in queries:
        v = embed(q)
        res = col.query(query_embeddings=[v], n_results=3,
                        include=["metadatas", "documents", "distances"])
        print("=" * 78)
        print("查询：", q)
        print("=" * 78)
        for i in range(len(res["ids"][0])):
            m = res["metadatas"][0][i]
            d = res["documents"][0][i]
            dist = res["distances"][0][i]
            src = f"{m['source_table']}.{m['field']}"
            rid = m.get("record_id")
            extra = m.get("nickname") or m.get("trait_content") or m.get("brand_name") or m.get("title") or ""
            print(f"  [{i + 1}] {src} | record={rid} | 距离={dist:.4f}")
            if extra:
                print(f"       {extra[:60]}")
            print(f"       原文: {d[:70]}")
        print()


if __name__ == "__main__":
    main()

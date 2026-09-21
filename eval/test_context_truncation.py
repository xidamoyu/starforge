"""
步骤③前置验证：bge-m3 embedding 的超长文本截断行为

结论（2026-09-21 实测）：
    1. /api/embed 端点忽略 options.num_ctx（4096/8192/32768 下结果一致，30 万字也不报错）
    2. 超长文本被【静默截断】：无报错、无警告，超出部分被丢弃
    3. 实际有效输入 ≈ 3072 中文字符（约 4096 token）：
         2048 字符 cos=0.958，2816 字符 cos=0.991，3072 字符起 cos=1.000000（之后恒定）
    4. 当前种子数据文本字段最长 120 字符，远低于阈值，向量化不触发截断
    5. 步骤③ 对生产级长文本（完整聊天记录/长复盘）必须切块，建议块上限 ≤ 2500 字符

方法：
    构造 4 万字长文本，取不同长度前缀分别 embed，与全文向量求余弦相似度；
    找到 cos 首次达到 1.0 的长度即截断点。

用法：
    .venv\\Scripts\\python.exe eval/test_context_truncation.py
"""
import json
import math
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODEL = os.getenv("EMBED_MODEL", "bge-m3")


def emb(t):
    r = requests.post(f"{BASE}/api/embed", json={"model": MODEL, "input": [t]}, timeout=600)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["embeddings"][0]


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else float("nan")


def build_text(n):
    data = json.loads((ROOT / "data" / "seed_data.json").read_text(encoding="utf-8"))
    base = "。".join(c["profile_text"] + (c.get("cooperation_history") or "") for c in data["creators"])
    out, i = "", 0
    while len(out) < n:
        out += f"第{i}段。" + base + "。"
        i += 1
    return out[:n]


def main():
    print("=" * 78)
    print(f"bge-m3 超长文本截断验证　服务={BASE}　模型={MODEL}")
    print("=" * 78)
    text = build_text(40000)
    full = emb(text)
    print(f"全文 {len(text)} 字符，逐前缀对比余弦相似度：\n")
    lens = [2048, 2304, 2560, 2816, 3072, 3328, 3584, 3840, 4096, 6144, 8192]
    for L in lens:
        v = emb(text[:L])
        print(f"  {L:>6} 字符 : cos={cos(v, full):.6f}", flush=True)
    print("\n判定：cos 首次达到 1.000000 的长度即截断点，其后内容被静默丢弃。")


if __name__ == "__main__":
    main()

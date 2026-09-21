"""
步骤 ②：Ollama embedding 模型可用性实测
重点：检测含 Markdown / JSON 结构的文本是否输出 NaN / Inf

用法：
    .venv\\Scripts\\python.exe eval/test_embedding.py

判定：
    4 类结构文本（+1 类真实种子数据文本）全部输出有限值向量 → 模型可用
    任一情况出现 NaN / Inf → 该模型不可用，需更换（换模型必须重建整个向量库）
"""
import json
import math
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODEL = os.getenv("EMBED_MODEL", "bge-m3")
ENV_DIM = os.getenv("EMBED_DIM", "")

TIMEOUT = 120


def build_cases():
    """构造测试样例：a 为对照组，b/c/d 为高危结构，e 为项目真实形态"""
    cases = []
    cases.append(("a", "纯中文自然语言（对照组）",
                  "帮我找一位适合做平价敏感肌护肤品测评的美妆达人，"
                  "粉丝量在五十万到两百万之间，女性粉丝占比高一些，"
                  "植入三十秒的报价不要超过八万。"))
    cases.append(("b", "含 ``` 代码块",
                  "以下是达人内容风格标签，请理解其含义：\n"
                  "```json\n"
                  '{"style": "深度科普", "tone": "理性克制"}\n'
                  "```\n"
                  "该达人适合成分分析类商单。"))
    cases.append(("c", "含 JSON 结构",
                  '达人档案：{"creator_id": "C003", "nickname": "成分党老李", '
                  '"followers": 245000, "female_ratio": 0.71, '
                  '"quote_embed_30s": 20000, "category": "美妆", '
                  '"sub_categories": ["成分分析", "护肤科普"]}，'
                  "请判断该达人与敏感肌护肤品牌的匹配度。"))
    cases.append(("d", "含 ### 标题 / | 表格",
                  "### 达人报价单\n\n"
                  "| 合作模式 | 时长 | 报价 |\n"
                  "|---|---|---|\n"
                  "| 植入 | 15s | 14000 |\n"
                  "| 植入 | 30s | 20000 |\n"
                  "| 定制 | 整条 | 38000 |\n\n"
                  "### 注意事项\n"
                  "- 要求先试用产品 7 天"))
    cases.append(("e", "真实种子数据拼接（结构化字段 + 聊天记录原话）",
                  _seed_text()))
    return cases


def _seed_text():
    """用真实种子数据拼接一份「结构化字段 + 聊天记录」文本（本项目最真实的高危形态）"""
    seed_path = ROOT / "data" / "seed_data.json"
    data = json.loads(seed_path.read_text(encoding="utf-8"))
    c = data["creators"][2]
    traits = [t for t in data["party_traits"] if t.get("party_id") == c["creator_id"]]

    lines = [
        f"# {c['nickname']}（{c['creator_id']}）达人档案",
        f"平台：{c['platform']}　垂类：{c['category']}　地区：{c.get('region')}",
        f"粉丝量：{c['followers']}　女性占比：{c['female_ratio']}",
        f"植入30s报价：{c.get('quote_embed_30s')}　定制报价：{c.get('quote_custom')}",
        "",
        "## 内容描述",
        c.get("profile_text", ""),
        c.get("content_style", ""),
        "",
        "## 合作历史原话",
        c.get("cooperation_history", ""),
    ]
    if traits:
        lines.append("")
        lines.append("## 沟通记录（原始素材）")
        for t in traits:
            lines.append(f"- [{t['trait_category']}/{t.get('severity')}] "
                         f"{t['trait_content']}；原话：「{t.get('source_quote')}」")
    lines.append("")
    lines.append("## 结构化字段（JSON）")
    lines.append(json.dumps({
        "creator_id": c["creator_id"], "sub_categories": c.get("sub_categories"),
        "coop_models": c.get("coop_models"), "past_brands": c.get("past_brands"),
    }, ensure_ascii=False))
    return "\n".join(lines)


def embed(texts):
    """调用 Ollama /api/embed；若接口不存在则回退 /api/embeddings"""
    url = f"{BASE}/api/embed"
    resp = requests.post(url, json={"model": MODEL, "input": texts}, timeout=TIMEOUT)
    if resp.status_code == 404:
        vecs = []
        for t in texts:
            r = requests.post(f"{BASE}/api/embeddings",
                              json={"model": MODEL, "prompt": t}, timeout=TIMEOUT)
            r.raise_for_status()
            vecs.append(r.json()["embedding"])
        return vecs
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    body = resp.json()
    if "embeddings" not in body:
        raise RuntimeError(f"响应缺少 embeddings 字段: {list(body.keys())}")
    return body["embeddings"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return float("nan")
    return dot / (na * nb)


def analyze(vec):
    bad = [v for v in vec if not math.isfinite(v)]
    nan_cnt = sum(1 for v in vec if isinstance(v, float) and math.isnan(v))
    inf_cnt = sum(1 for v in vec if not math.isnan(v) and not math.isfinite(v))
    norm = math.sqrt(sum(v * v for v in vec if math.isfinite(v)))
    zeros = sum(1 for v in vec if v == 0)
    return {
        "dim": len(vec),
        "bad": len(bad),
        "nan": nan_cnt,
        "inf": inf_cnt,
        "norm": norm,
        "zeros": zeros,
    }


def check_discrimination():
    """判别力校验：语义相同的句对相似度应显著高于语义无关的句对。
    仅「无 NaN」不足以证明向量可用——若向量退化（如近乎常量），相似度会失去区分度。"""
    pos = ("帮我找一位美妆达人做护肤品测评",
           "需要一位美妆垂类达人合作护肤品功效测评内容")
    neg = ("帮我找一位美妆达人做护肤品测评",
           "主机游戏直播带货，显卡与外设类产品推广")
    texts = [pos[0], pos[1], neg[0], neg[1]]
    vecs = embed(texts)
    sim_pos = cosine(vecs[0], vecs[1])
    sim_neg = cosine(vecs[2], vecs[3])
    print("\n" + "-" * 78)
    print("判别力校验（语义相近 vs 语义无关）")
    print("-" * 78)
    print(f"  相近句对 sim = {sim_pos:.4f}")
    print(f"  无关句对 sim = {sim_neg:.4f}")
    print(f"  差值        = {sim_pos - sim_neg:+.4f}")
    ok = sim_pos > sim_neg + 0.05
    print(f"  {'✅ 向量具备判别力' if ok else '❌ 向量判别力不足（疑似退化）'}")
    return ok


def main():
    print("=" * 78)
    print(f"Ollama embedding 实测　服务={BASE}　模型={MODEL}　.env 声明维度={ENV_DIM}")
    print("=" * 78)

    try:
        tags = requests.get(f"{BASE}/api/tags", timeout=15).json()
    except Exception as e:
        print(f"[FAIL] 无法连接 Ollama: {e}")
        sys.exit(2)
    installed = [m["name"] for m in tags.get("models", [])]
    print(f"已安装模型: {', '.join(installed)}\n")
    if not any(m == MODEL or m.startswith(MODEL + ":") for m in installed):
        print(f"[FAIL] 未找到模型 {MODEL}，请先 ollama pull {MODEL}")
        sys.exit(2)

    cases = build_cases()
    texts = [c[2] for c in cases]

    try:
        vecs = embed(texts)
    except Exception as e:
        print(f"[FAIL] 调用 embedding 接口失败: {e}")
        sys.exit(2)

    if len(vecs) != len(texts):
        print(f"[FAIL] 返回向量数 {len(vecs)} != 输入文本数 {len(texts)}")
        sys.exit(2)

    print(f"{'样例':<4}{'维度':<7}{'NaN':<6}{'Inf':<6}{'零元素':<8}{'L2范数':<14}判定")
    print("-" * 78)

    failed = []
    stats = {}
    for (cid, label, _), vec in zip(cases, vecs):
        s = analyze(vec)
        stats[cid] = s
        ok = (s["bad"] == 0 and s["norm"] > 0)
        if not ok:
            failed.append((cid, label, s))
        print(f"{cid:<4}{s['dim']:<7}{s['nan']:<6}{s['inf']:<6}{s['zeros']:<8}"
              f"{s['norm']:<14.6f}{'✅ 正常' if ok else '❌ 异常'}")

    print("\n" + "-" * 78)
    print("样例说明与语义区分度（与对照组 a 的余弦相似度）")
    print("-" * 78)
    base_vec = vecs[0]
    for (cid, label, _), vec in zip(cases, vecs):
        if cid == "a":
            continue
        sim = cosine(base_vec, vec)
        print(f"  {cid}  {label}")
        print(f"      sim(a,{cid}) = {sim:.4f}")

    print("\n" + "-" * 78)
    print("维度一致性")
    print("-" * 78)
    dim = stats["a"]["dim"]
    if ENV_DIM and str(dim) != str(ENV_DIM):
        print(f"  ❌ 实测维度 {dim} != .env 中 EMBED_DIM={ENV_DIM}，需修正 .env")
        failed.append(("env", "维度不一致", {"dim": dim}))
    else:
        print(f"  ✅ 实测维度 {dim} 与 .env EMBED_DIM={ENV_DIM} 一致")

    if not check_discrimination():
        failed.append(("sim", "判别力不足", {}))

    print("\n" + "=" * 78)
    if failed:
        print(f"【结论】{MODEL} 不可用，异常样例：{', '.join(f[0] for f in failed)}")
        print("         动作：改用 qwen3-embedding:0.6b，并同步修改 .env 的 EMBED_MODEL / EMBED_DIM")
        print("         ⚠️ 换模型必须重建整个向量库")
        sys.exit(1)
    print(f"【结论】{MODEL} 可用：全部样例输出有限值向量，维度 {dim}，无 NaN / Inf")
    print("         动作：模型定死不再更换，继续步骤 ③（向量化入 ChromaDB）")
    sys.exit(0)


if __name__ == "__main__":
    main()

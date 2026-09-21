"""
步骤⑤验证：混合检索 L1-A

用法：
    .venv\\Scripts\\python.exe eval/test_hybrid.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval.hybrid_search import search  # noqa: E402

CASES = [
    ("粉丝量5万到30万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过2万", None),
    ("粉丝量50万到200万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过8万", None),
    ("新出的氨基酸洁面，想找成分党类的博主做真实测评，重点讲温和不刺激，面向学生党。预算控制在6000以内。", "placement"),
    ("帮我找个达人合作一下。", None),
]


def show(r):
    parsed = r["parsed"]
    print("  解析:")
    print("    hard_filters:", json.dumps(parsed.get("hard_filters"), ensure_ascii=False))
    if parsed.get("semantic_query"):
        print("    semantic_query:", parsed["semantic_query"])
    if parsed.get("need_clarification"):
        print("    need_clarification:", json.dumps(parsed.get("need_clarification"), ensure_ascii=False))
    print(f"  SQL 过滤命中: {r['sql_count']} 人")
    for c in r["result"]:
        line = f"    {c['creator_id']} {c['nickname']:<10} 粉丝={int(c['followers']):>7,} " \
               f"女性={c['female_ratio']} 植入30s={c['quote_embed_30s']}"
        if c["matches"]:
            m = c["matches"][0]
            line += f"  [命中 {m['field']} dist={m['distance']:.3f}]"
        print(line)


def main():
    for i, (text, coop) in enumerate(CASES, 1):
        print("=" * 78)
        print(f"样例{i}: {text}")
        if coop:
            print(f"  （合作模式澄清 = {coop}）")
        print("=" * 78)
        try:
            show(search(text, coop_mode=coop))
        except Exception as e:
            print(f"[FAIL] {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    main()

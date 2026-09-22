"""
步骤⑥验证：可溯源理由生成

用法：
    .venv\\Scripts\\python.exe eval/test_reason.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval.hybrid_search import build_reasons  # noqa: E402


def show(r):
    parsed = r["parsed"]
    print("  解析 hard_filters:", json.dumps(parsed.get("hard_filters"), ensure_ascii=False))
    if parsed.get("semantic_query"):
        print("  semantic_query:", parsed["semantic_query"])
    if parsed.get("need_clarification"):
        print("  need_clarification:", json.dumps(parsed.get("need_clarification"), ensure_ascii=False))
    print(f"  SQL 过滤命中: {r['sql_count']} 人\n")
    for it in r["items"]:
        p = it["profile"]
        print(f"  【{it['creator_id']} {it['nickname']}】")
        print(f"    粉丝={int(p['followers']):,} 女性={p['female_ratio']} "
              f"植入30s={p['quote_embed_30s']} 定制={p['quote_custom']} "
              f"{p['category']}/{p['platform']}")
        for reason in it["reasons"]:
            if reason["type"] == "match":
                print(f"    · 语义命中 [{reason['field']}]: {reason['quote'][:50]}")
            elif reason["type"] == "trait":
                sev = reason["severity"]
                print(f"    · [{sev}] {reason['category']}: {reason['content']}")
                if reason["source_quote"]:
                    print(f"        原话: {reason['source_quote'][:50]}")
                print(f"        溯源: trait_id={reason['trait_id']}")
        if not it["reasons"]:
            print("    · （无命中文本 / 无注意事项）")
        print()


def main():
    cases = [
        ("新出的氨基酸洁面，想找成分党类的博主做真实测评，重点讲温和不刺激，面向学生党。预算控制在6000以内。", "placement"),
        ("粉丝量5万到30万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过2万", None),
    ]
    for i, (text, coop) in enumerate(cases, 1):
        print("=" * 78)
        print(f"样例{i}: {text}")
        print("=" * 78)
        try:
            show(build_reasons(text, coop_mode=coop))
        except Exception as e:
            print(f"[FAIL] {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    main()

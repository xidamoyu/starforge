"""
消融补充：纯 SQL 硬过滤策略（不做向量检索、不做 rerank）。

现有 ablation.py 覆盖 vector_only / hybrid / hybrid_rerank / union 四种，
但缺少「纯 SQL 硬过滤」这一对照策略。本脚本直接调用 src.retrieval.hybrid_search.sql_filter()，
按 followers DESC 排序（即 SQL 硬过滤的自然输出顺序），截取 top_k 后计算指标。

注意：query 仍需经 parse_requirement 解析出 hard_filters（与其它策略共用同一解析口径），
不调用 embed / rerank，因此不产生向量或 CrossEncoder 开销。

用法：
    .venv\\Scripts\\python.exe eval/ablation_sql.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from metrics import aggregate, evaluate_case  # noqa: E402
from src.core.llm import parse_requirement  # noqa: E402
from src.retrieval.hybrid_search import sql_filter  # noqa: E402

TOP_K = 10
SHOW_KEYS = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10", "hit@5"]


def search_sql(query, top_k=TOP_K):
    """纯 SQL 硬过滤：解析 hard_filters → sql_filter（followers DESC）→ 截取 top_k"""
    parsed = parse_requirement(query)
    hf = parsed.get("hard_filters", {})
    rows = sql_filter(hf)  # 已按 followers DESC 排序
    return [r["creator_id"] for r in rows[:top_k]]


def main():
    testset = json.loads((ROOT / "eval" / "testset.json").read_text(encoding="utf-8-sig"))
    cases = [c for c in testset["cases"] if c["type"] == "recall"]
    print("=" * 96)
    print(f"纯 SQL 硬过滤消融　用例数={len(cases)}")
    print("=" * 96)

    t0 = time.time()
    per = []
    for c in cases:
        try:
            ids = search_sql(c["query"], TOP_K)
        except Exception as e:
            print(f"  [sql_filter] {c['id']} FAIL: {type(e).__name__}: {e}")
            ids = []
        per.append(evaluate_case(ids, c["must_recall"]))
    elapsed = time.time() - t0
    agg = aggregate(per)
    agg["avg_sec"] = elapsed / len(cases)

    print("\n" + "=" * 96)
    print("纯 SQL 硬过滤（followers DESC，无向量/rerank）")
    print("=" * 96)
    header = f"{'策略':<20}" + "".join(f"{k:>11}" for k in SHOW_KEYS) + f"{'耗时/s':>10}"
    print(header)
    print("-" * 96)
    row = f"{'纯 SQL 硬过滤':<20}" + "".join(f"{agg.get(k, 0):>11.3f}" for k in SHOW_KEYS)
    row += f"{agg.get('avg_sec', 0):>10.2f}"
    print(row)

    # 逐条明细
    print("\n逐条召回顺序（top 6）:")
    for c in cases:
        ids = search_sql(c["query"], TOP_K)
        hit = [("✓" if i in c["must_recall"] else " ") for i in ids]
        line = "  ".join(f"{h}{i}" for h, i in zip(hit, ids[:6]))
        print(f"  {c['id']}  {line}")

    out = ROOT / "eval" / "ablation_sql_result.json"
    out.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存：{out}")


if __name__ == "__main__":
    main()

"""
消融实验：同一评测集（recall 用例）跑多种检索策略，输出指标对比表。

用途：量化回答「混合检索比纯向量好多少」「rerank 又提升多少」。

用法：
    .venv\\Scripts\\python.exe eval/ablation.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from metrics import aggregate, evaluate_case  # noqa: E402
from src.retrieval.hybrid_search import search  # noqa: E402

STRATEGIES = ["vector_only", "hybrid", "hybrid_rerank", "union"]
LABELS = {
    "vector_only": "纯向量（基线）",
    "hybrid": "混合检索 L1-A",
    "hybrid_rerank": "混合 + Rerank",
    "union": "双路并集 L1-C",
}
SHOW_KEYS = ["recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@10", "hit@5"]


def main():
    testset = json.loads((ROOT / "eval" / "testset.json").read_text(encoding="utf-8-sig"))
    cases = [c for c in testset["cases"] if c["type"] == "recall"]
    print("=" * 96)
    print(f"检索消融实验　用例数={len(cases)}")
    print("=" * 96)

    summary = {}
    for st in STRATEGIES:
        t0 = time.time()
        per = []
        for c in cases:
            try:
                r = search(c["query"], top_k=10, strategy=st)
                ids = [x["creator_id"] for x in r["result"]]
            except Exception as e:
                print(f"  [{st}] {c['id']} FAIL: {type(e).__name__}: {e}")
                ids = []
            per.append(evaluate_case(ids, c["must_recall"]))
        elapsed = time.time() - t0
        agg = aggregate(per)
        agg["avg_sec"] = elapsed / len(cases)
        summary[st] = agg
        print(f"  [{st}] 完成，耗时 {elapsed:.1f}s（{agg['avg_sec']:.2f}s/条）")

    # 指标对比表
    print("\n" + "=" * 96)
    print("指标对比（数值越高越好）")
    print("=" * 96)
    header = f"{'策略':<20}" + "".join(f"{k:>11}" for k in SHOW_KEYS) + f"{'耗时/s':>10}"
    print(header)
    print("-" * 96)
    for st in STRATEGIES:
        a = summary[st]
        row = f"{LABELS[st]:<20}" + "".join(f"{a.get(k, 0):>11.3f}" for k in SHOW_KEYS)
        row += f"{a.get('avg_sec', 0):>10.2f}"
        print(row)

    # 增量对比（相对基线）
    print("\n" + "=" * 96)
    print("相对基线的增量（百分点）")
    print("=" * 96)
    base = summary["vector_only"]
    print(f"{'策略':<20}" + "".join(f"{k:>11}" for k in SHOW_KEYS))
    print("-" * 96)
    for st in STRATEGIES[1:]:
        a = summary[st]
        row = f"{LABELS[st]:<20}" + "".join(
            f"{(a.get(k, 0) - base.get(k, 0)) * 100:>+11.1f}" for k in SHOW_KEYS
        )
        print(row)

    out = ROOT / "eval" / "ablation_result.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已保存：{out}")


if __name__ == "__main__":
    main()

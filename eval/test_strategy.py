"""对比不同检索策略在同一查询下的返回结果（rerank 效果肉眼可见版）。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval.hybrid_search import search  # noqa: E402

QUERY = "找母婴达人，粉丝5万以上，内容偏育儿知识"
STRATEGIES = ["vector_only", "hybrid", "hybrid_rerank", "union"]


def main():
    print("=" * 78)
    print(f"策略对比　查询：{QUERY}")
    print("=" * 78)

    for st in STRATEGIES:
        try:
            r = search(QUERY, top_k=5, strategy=st)
        except Exception as e:
            print(f"\n=== {st} === FAIL {type(e).__name__}: {e}")
            continue

        print(f"\n=== {st} ===  sql_count={r.get('sql_count')}  返回 {len(r['result'])} 条")
        for i, c in enumerate(r["result"], 1):
            rs = c.get("rerank_score")
            extra = f"  rerank={rs:.4f}" if rs is not None else ""
            print(f"  {i}. {c['creator_id']:<6} {c['nickname']:<14} "
                  f"粉丝={c['followers']:>8,}  植入30s={c['quote_embed_30s']}{extra}")

    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

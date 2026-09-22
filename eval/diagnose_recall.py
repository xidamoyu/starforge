"""诊断：逐条查看 recall 用例在各策略下的返回顺序，定位 rerank 未提升的原因。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval.hybrid_search import search  # noqa: E402


def main():
    testset = json.loads((ROOT / "eval" / "testset.json").read_text(encoding="utf-8-sig"))
    cases = [c for c in testset["cases"] if c["type"] == "recall"]

    for c in cases:
        print("=" * 90)
        print(f"{c['id']}  查询：{c['query']}")
        print(f"   must_recall = {c['must_recall']}")
        for st in ["hybrid", "hybrid_rerank"]:
            r = search(c["query"], top_k=10, strategy=st)
            ids = [x["creator_id"] for x in r["result"]]
            hit = [("✓" if i in c["must_recall"] else " ") for i in ids]
            rk = {x["creator_id"]: x.get("rerank_score") for x in r["result"]}
            line = "  ".join(
                f"{h}{i}" + (f"({rk[i]:.3f})" if st == "hybrid_rerank" and rk.get(i) is not None else "")
                for h, i in zip(hit, ids[:6])
            )
            print(f"  [{st:<13}] {line}")


if __name__ == "__main__":
    main()

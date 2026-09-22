"""
步骤⑦：评测集评估脚本（分层评测）

- parse   测需求解析：对比 LLM 解析的 hard_filters 与标注的结构化条件（固定，不膨胀）
- recall  测检索漏召：检查 must_recall 的核心达人是否被召回（golden set）
- clarify 测信息不足：need_clarification 是否非空

用法：
    .venv\\Scripts\\python.exe eval/run_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.retrieval.hybrid_search import search  # noqa: E402

RANGE_FIELDS = {"followers", "female_ratio", "age_18_24_ratio", "age_25_34_ratio",
                "avg_views", "engagement_rate", "quote_embed_15s", "quote_embed_30s",
                "quote_embed_60s", "quote_custom"}
LIST_FIELDS = {"category", "platform", "coop_models", "sub_categories"}


def load_testset():
    return json.loads((ROOT / "eval" / "testset.json").read_text(encoding="utf-8"))


def _close(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def check_hf(actual, expected):
    """检查 expected 的关键条件是否在 actual 中被正确解析。返回 (ok, err)"""
    for field, ev in expected.items():
        av = actual.get(field)
        if av is None:
            return False, f"缺字段 {field}"
        if field in RANGE_FIELDS:
            if not isinstance(ev, dict) or not isinstance(av, dict):
                return False, f"{field} 应为范围对象"
            for k, v in ev.items():
                if av.get(k) is None or not _close(av.get(k), v):
                    return False, f"{field}.{k} 应为 {v} 实为 {av.get(k)}"
        elif field in LIST_FIELDS:
            av_set = set(av) if isinstance(av, list) else {av}
            ev_set = set(ev) if isinstance(ev, list) else {ev}
            if not ev_set <= av_set:
                return False, f"{field} 缺 {sorted(ev_set - av_set)}"
    return True, ""


def eval_one(case):
    r = search(case["query"], coop_mode=case.get("coop_mode"))
    parsed = r["parsed"]
    hit = [c["creator_id"] for c in r["result"]]
    hit_set = set(hit)
    need = parsed.get("need_clarification", [])
    typ = case["type"]

    if typ == "parse":
        ok, err = check_hf(parsed.get("hard_filters", {}), case["expected"])
        detail = "条件解析正确" if ok else err
    elif typ == "recall":
        miss = [c for c in case["must_recall"] if c not in hit_set]
        ok = not miss
        detail = f"命中{len(hit)}个" + (f" 漏召{miss}" if miss else "")
    else:  # clarify
        ok = bool(need)
        detail = f"反问{len(need)}条" if need else "未反问"
    return ok, detail, hit, need


def main():
    cases = load_testset()["cases"]
    passed, failed = 0, []
    stat = {}
    print("=" * 78)
    print(f"评测集共 {len(cases)} 条（分层：parse / recall / clarify）")
    print("=" * 78)
    for case in cases:
        try:
            ok, detail, hit, need = eval_one(case)
        except Exception as e:
            ok, detail, hit, need = False, f"异常 {type(e).__name__}: {e}", [], []
        stat[case["type"]] = stat.get(case["type"], 0) + 1
        print(f"{'✅' if ok else '❌'} {case['id']} [{case['type']}] {case['query'][:30]}")
        if not ok:
            print(f"     {detail}")
            print(f"     命中: {hit}")
        if ok:
            passed += 1
        else:
            failed.append(case["id"])
    print("=" * 78)
    dist = " / ".join(f"{k} {v}" for k, v in sorted(stat.items()))
    print(f"通过 {passed}/{len(cases)}　分布: {dist}")
    if failed:
        print(f"失败项: {failed}")


if __name__ == "__main__":
    main()

"""
步骤④验证：需求解析 Prompt 效果

用三类样例验证 LLM 能否正确解析：
  1. 口语化需求（含预算）
  2. 精确数值范围需求
  3. 信息严重不足（应触发 need_clarification 反问）

用法：
    .venv\\Scripts\\python.exe eval/test_parse.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.llm import ensure_budget, extract_budget, parse_requirement  # noqa: E402

CASES = [
    "新出的氨基酸洁面，想找成分党类的博主做真实测评，重点讲温和不刺激，面向学生党。预算控制在6000以内。",
    "粉丝量50万到200万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过8万。",
    "帮我找个达人合作一下。",
]


def test_budget_fallback():
    """预算兜底单元测试（确定性，不调 LLM）"""
    for text, expected in [
        ("预算控制在6000以内", 6000),
        ("预算1万", 10000),
        ("预算50万左右", 500000),
        ("总预算3千", 3000),
        ("帮我找个达人", None),
    ]:
        got = extract_budget(text)
        assert got == expected, f"extract_budget({text!r}) = {got}, 期望 {expected}"

    p = ensure_budget({"hard_filters": {"category": ["美妆"]}}, "预算控制在6000以内")
    assert p["hard_filters"]["quote_embed_15s"] == {"max": 6000}, p

    p2 = ensure_budget({"hard_filters": {"quote_embed_30s": {"max": 80000}}}, "预算控制在6000以内")
    assert "quote_embed_15s" not in p2["hard_filters"], p2
    assert p2["hard_filters"]["quote_embed_30s"] == {"max": 80000}, p2

    p3 = ensure_budget({"hard_filters": {"category": ["美妆"]}}, "帮我找个达人")
    assert "quote_embed_15s" not in p3["hard_filters"], p3

    print("[OK] 预算兜底单元测试 7 项全部通过")


def main():
    test_budget_fallback()
    print()
    for i, c in enumerate(CASES, 1):
        print("=" * 78)
        print(f"样例{i}: {c}")
        print("=" * 78)
        try:
            r = parse_requirement(c)
            print(json.dumps(r, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"[FAIL] {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    main()

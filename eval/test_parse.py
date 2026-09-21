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

from src.core.llm import parse_requirement  # noqa: E402

CASES = [
    "新出的氨基酸洁面，想找成分党类的博主做真实测评，重点讲温和不刺激，面向学生党。预算控制在6000以内。",
    "粉丝量50万到200万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过8万。",
    "帮我找个达人合作一下。",
]


def main():
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

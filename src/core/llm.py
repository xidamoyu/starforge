"""
LLM 客户端（DashScope OpenAI 兼容接口）+ 需求解析

步骤④：把甲方大白话需求解析成结构化检索条件。
铁律约束：只从原文提取明确信息，不臆造；无法确定的信息进 need_clarification 反问。
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SYSTEM_PROMPT = """你是广告中介公司的「需求解析器」。把甲方用大白话表达的合作需求，解析成结构化检索条件。

输出必须是严格的 JSON（不要输出任何多余文字，不要用 markdown 代码块包裹），格式：
{
  "hard_filters": {
    "followers": {"min": 500000, "max": 2000000},
    "female_ratio": {"min": 0.70},
    "quote_embed_30s": {"max": 80000},
    "category": ["美妆"],
    "platform": ["抖音"]
  },
  "semantic_query": "一句话提炼的非硬约束语义需求，用于向量检索",
  "need_clarification": ["信息不足、无法确定时提出的自然反问"]
}

hard_filters 可选字段（单位/格式严格）：
- followers: 粉丝数（整数），min/max
- female_ratio: 女性粉丝占比（0~1 小数，70% → 0.70），min/max
- age_18_24_ratio / age_25_34_ratio: 年龄段占比（0~1）
- avg_views: 平均播放量（整数）
- engagement_rate: 互动率（0~1 小数）
- quote_embed_15s / quote_embed_30s / quote_embed_60s: 植入按时长报价（元，整数），min/max
- quote_custom: 定制整条报价（元，整数），min/max
- category: 垂类（数组，如 ["美妆"]）
- sub_categories: 细分标签（数组）
- platform: 平台（数组，抖音/小红书/B站）
- region: 地域（字符串或数组）
- coop_models: 合作模式（数组，placement=植入 / custom=定制）

规则：
1. 只从原文提取明确提到的信息，不臆造、不补全。
2. 数值精确换算：百分比转 0~1 小数；"万"转整数（50万=500000）。
3. 原文没提到的字段一律不放进 hard_filters。
4. 原文无法确定、但对匹配关键的信息（预算/平台/垂类/合作模式/粉丝量级等），放进 need_clarification，用一句自然的反问。
5. 语义化、无法数值化的需求（如"真实测评向"、"氛围感强"）提炼进 semantic_query，一句话说清。
6. 报价口径：植入按时长档位（15s/30s/60s）；"植入报价不超过X"归入 quote_embed_30s（未指定时长时）；"定制"归入 quote_custom；若原文只说"预算"而既没提植入也没提定制，不要把预算放进任何报价字段，只在 need_clarification 反问。
7. 合作模式：原文已明确"植入"或"定制"时，直接设 coop_models（植入=["placement"]、定制=["custom"]），不要反问；仅当原文既没提植入也没提定制时，才在 need_clarification 反问"这次要植入还是定制？"。
"""

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
        )
    return _client


def _extract_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def parse_requirement(text, model=None):
    """甲方大白话需求 → 结构化条件 dict（含 hard_filters / semantic_query / need_clarification）"""
    client = get_client()
    resp = client.chat.completions.create(
        model=model or os.getenv("LLM_MODEL", "qwen-plus"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content
    return _extract_json(raw)


# 澄清策略（用户确认，2026-09-21）：
#   未明确「植入/定制」时及时反问；只反问一次，用户不答即搁置该字段，不臆断、不阻塞检索。
def apply_coop_mode(parsed, choice):
    """把「植入 or 定制」的一次澄清结果合并进解析结果。

    choice:
      "placement" → 合作模式=植入，预算挪到 quote_embed_30s（时长未定）
      "custom"    → 合作模式=定制
      None        → 搁置：不设 coop_models，并丢弃硬过滤里未绑定模式的报价字段
    """
    result = {k: v for k, v in parsed.items()}
    hf = dict(result.get("hard_filters", {}))
    if choice == "placement":
        hf["coop_models"] = ["placement"]
        # 预算从"未绑定模式"的 quote_custom 挪到植入报价（时长未定，默认 30s）
        if "quote_custom" in hf and "quote_embed_30s" not in hf:
            hf["quote_embed_30s"] = hf.pop("quote_custom")
        else:
            hf.pop("quote_custom", None)
    elif choice == "custom":
        hf["coop_models"] = ["custom"]
    else:
        # 搁置：不设 coop_models，丢弃未绑定模式的报价字段
        hf.pop("coop_models", None)
        for k in ("quote_embed_15s", "quote_embed_30s", "quote_embed_60s", "quote_custom"):
            hf.pop(k, None)
    result["hard_filters"] = hf
    # 移除已处理的合作模式反问，避免澄清后仍残留
    nc = result.get("need_clarification", [])
    result["need_clarification"] = [q for q in nc if not ("植入" in q and "定制" in q)]
    return result

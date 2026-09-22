"""
对齐问题清单：服务 Dify V2 的意图 #7（签约前对齐）。

把某商单的商务条件逐项对照，标出「已明确 / 待确认」，产出可直接用于建联对齐的核对清单。

设计约束：
    - **规则驱动**（非 LLM）——核对类任务必须逐项确定，不能遗漏
    - 只读，不修改任何数据
"""
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# (字段, 标签, 适用条件)
ALIGN_ITEMS = [
    ("coop_mode", "合作模式", None),
    ("quoted_price", "报价", None),
    ("agreed_price", "成交价", None),
    ("embed_duration_sec", "植入时长", "placement"),   # 仅植入模式适用
    ("revision_count", "修改次数", None),
    ("deliverable", "交付内容", None),
    ("exclusive_days", "独家期", None),
    ("authorization_scope", "素材授权范围", None),
    ("publish_deadline", "发布时间截止", None),
]

DEAL_COLS = [
    "deal_id", "title", "brand_id", "creator_id", "status", "coop_mode",
    "quoted_price", "agreed_price", "embed_duration_sec", "revision_count",
    "deliverable", "exclusive_days", "authorization_scope", "publish_deadline",
]


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def _val(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def get_align_questions(deal_id):
    """返回该商单的对齐清单；未找到时 found=False。"""
    if not deal_id:
        return {"found": False, "message": "需要提供 deal_id"}

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(DEAL_COLS)} FROM deals WHERE deal_id = %s", (deal_id,)
        )
        row = cur.fetchone()
        if not row:
            return {"found": False, "message": f"未找到商单：{deal_id}"}

        d = dict(zip(DEAL_COLS, row))
        items = []
        for field, label, cond in ALIGN_ITEMS:
            if cond == "placement" and d.get("coop_mode") != "placement":
                continue  # 不适用
            v = d.get(field)
            if v is None or v == "":
                items.append({
                    "field": field, "label": label,
                    "status": "missing", "hint": f"未约定{label}",
                })
            else:
                items.append({
                    "field": field, "label": label,
                    "status": "confirmed", "value": str(_val(v)),
                })

        missing = [i for i in items if i["status"] == "missing"]
        return {
            "found": True,
            "deal_id": d["deal_id"],
            "title": d["title"],
            "creator_id": d["creator_id"],
            "brand_id": d["brand_id"],
            "status": d["status"],
            "coop_mode": d["coop_mode"],
            "items": items,
            "summary": {"confirmed": len(items) - len(missing), "missing": len(missing)},
            "missing_labels": [i["label"] for i in missing],
        }

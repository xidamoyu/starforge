"""
达人档案查询：服务 Dify V2 的意图 #2（公司资产咨询）与 #3a（某人公开数据）。

与 /search 的分工：
    /search        给「商单需求」→ 从池子里筛出多个达人（多对一）
    /creator_info  给「已知达人」→ 拉出公开数据 + 私有经验（一对一）

设计约束（与全局铁律一致）：
    - 只读不生成：返回库里的事实，不做二次生成、不编造数字
    - 私有经验只取 verified=TRUE 的 party_traits
    - 数据新鲜度以 creators.updated_at 为准，供上层做提示
"""
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

SELECT_COLS = [
    "creator_id", "nickname", "platform", "profile_url",
    "followers", "female_ratio", "age_18_24_ratio", "age_25_34_ratio",
    "avg_views", "engagement_rate",
    "quote_embed_15s", "quote_embed_30s", "quote_embed_60s", "quote_custom",
    "category", "sub_categories", "region", "coop_models",
    "profile_text", "content_style", "past_brands", "cooperation_history",
    "updated_at",
]

BASE_SQL = f"SELECT {', '.join(SELECT_COLS)} FROM creators"


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def _num(v):
    """Decimal → float，便于 JSON 序列化"""
    return float(v) if isinstance(v, Decimal) else v


def _date(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def _resolve(cur, creator_id=None, name=None):
    """
    返回 (row | None, matched_by | None, candidates)。

    - 给 creator_id：精确查。
    - 给 name：完全匹配优先；
        模糊命中 1 个 → 返回该行；
        模糊命中多个 → **不猜**，返回 candidates 供上层澄清（与「不臆断」原则一致）。
    """
    if creator_id:
        cur.execute(BASE_SQL + " WHERE creator_id = %s", (creator_id,))
        row = cur.fetchone()
        return (row, "id", []) if row else (None, None, [])

    if name:
        cur.execute(BASE_SQL + " WHERE nickname = %s", (name,))
        row = cur.fetchone()
        if row:
            return (row, "exact_name", [])

        cur.execute(
            "SELECT creator_id, nickname, platform, followers FROM creators "
            "WHERE nickname ILIKE %s ORDER BY followers DESC LIMIT 10",
            (f"%{name}%",),
        )
        cols = [d[0] for d in cur.description]
        cand = [dict(zip(cols, r)) for r in cur.fetchall()]
        if len(cand) == 1:
            cur.execute(BASE_SQL + " WHERE creator_id = %s", (cand[0]["creator_id"],))
            return (cur.fetchone(), "fuzzy_name", [])
        if len(cand) > 1:
            return (None, None, cand)

    return (None, None, [])


def get_creator_info(creator_id=None, name=None):
    """返回达人档案；未找到时 found=False。"""
    if not creator_id and not name:
        return {"found": False, "message": "需要提供 creator_id 或 name"}

    with get_conn() as conn, conn.cursor() as cur:
        row, matched_by, candidates = _resolve(cur, creator_id, name)

        if candidates:
            return {
                "found": False,
                "ambiguous": True,
                "message": f"「{name}」匹配到 {len(candidates)} 个达人，需确认指哪一个",
                "candidates": candidates,
            }
        if not row:
            return {"found": False, "message": f"未找到达人：{creator_id or name}"}

        c = dict(zip(SELECT_COLS, row))
        cid = c["creator_id"]

        # 私有经验 1：已验证注意事项（critical 优先）
        cur.execute(
            """
            SELECT trait_id, trait_category, trait_content, severity, source_quote
            FROM party_traits
            WHERE party_type = 'creator' AND party_id = %s AND verified = TRUE
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, trait_id
            """,
            (cid,),
        )
        tcols = [d[0] for d in cur.description]
        traits = [dict(zip(tcols, r)) for r in cur.fetchall()]

        # 私有经验 2：历史商单
        cur.execute(
            """
            SELECT deal_id, title, status, coop_mode, agreed_price, published_date
            FROM deals WHERE creator_id = %s
            ORDER BY COALESCE(published_date, signed_date) DESC NULLS LAST
            """,
            (cid,),
        )
        dcols = [d[0] for d in cur.description]
        deals = [{k: _date(v) for k, v in zip(dcols, r)} for r in cur.fetchall()]

        # 私有经验 3：该达人商单的复盘
        cur.execute(
            """
            SELECT r.review_id, r.deal_id, r.reviewer_role, r.rating, r.content
            FROM deal_reviews r JOIN deals d ON r.deal_id = d.deal_id
            WHERE d.creator_id = %s ORDER BY r.review_id
            """,
            (cid,),
        )
        rcols = [d[0] for d in cur.description]
        reviews = [dict(zip(rcols, r)) for r in cur.fetchall()]

        upd = c["updated_at"]
        days_ago = None
        if isinstance(upd, datetime):
            tz = upd.tzinfo or timezone.utc
            days_ago = (datetime.now(tz) - upd).days

        return {
            "found": True,
            "matched_by": matched_by,
            "creator_id": cid,
            "public": {
                "nickname": c["nickname"],
                "platform": c["platform"],
                "profile_url": c["profile_url"],
                "followers": c["followers"],
                "female_ratio": _num(c["female_ratio"]),
                "age_18_24_ratio": _num(c["age_18_24_ratio"]),
                "age_25_34_ratio": _num(c["age_25_34_ratio"]),
                "avg_views": c["avg_views"],
                "engagement_rate": _num(c["engagement_rate"]),
                "quotes": {
                    "embed_15s": c["quote_embed_15s"],
                    "embed_30s": c["quote_embed_30s"],
                    "embed_60s": c["quote_embed_60s"],
                    "custom": c["quote_custom"],
                },
                "category": c["category"],
                "sub_categories": c["sub_categories"],
                "region": c["region"],
                "coop_models": c["coop_models"],
                "profile_text": c["profile_text"],
                "content_style": c["content_style"],
            },
            "private": {
                "past_brands": c["past_brands"],
                "cooperation_history": c["cooperation_history"],
                "traits": traits,
                "deals": deals,
                "reviews": reviews,
            },
            "freshness": {
                "data_updated_at": _date(upd),
                "days_ago": days_ago,
            },
        }

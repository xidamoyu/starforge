"""
增量导入脚本：把数据文件里的记录 upsert 进数据库（**不清空、不重建**）。

与 init_db.py 的分工：
    init_db.py      执行 schema.sql（DROP + CREATE）→ 全量重建，会清空数据。
                    仅用于首次初始化，或变更表结构时。
    import_data.py  只做 INSERT ... ON CONFLICT DO UPDATE，已有数据不动。
                    **日常新增 / 修改记录用这个。**

用法：
    .venv\\Scripts\\python.exe src/db/import_data.py                       # 导入 data/seed_data.json 全部
    .venv\\Scripts\\python.exe src/db/import_data.py --file data/new.json   # 指定数据文件
    .venv\\Scripts\\python.exe src/db/import_data.py --table party_traits   # 只导入某张表

导入后如涉及文本字段，再跑一次向量化（它是 upsert，安全）：
    .venv\\Scripts\\python.exe src/retrieval/vectorize.py
"""
import argparse
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
        autocommit=True,
    )


def row_brands(r):
    return (r["brand_id"], r["brand_name"], r["industry"], r.get("company_size"),
            r.get("contact_person"), r.get("contact_wechat"), r.get("cooperation_notes"))


def row_creators(r):
    return (r["creator_id"], r["nickname"], r["platform"], r.get("profile_url"),
            r["followers"], r["female_ratio"],
            r.get("age_18_24_ratio"), r.get("age_25_34_ratio"),
            r.get("avg_views"), r.get("engagement_rate"),
            r.get("quote_embed_15s"), r.get("quote_embed_30s"),
            r.get("quote_embed_60s"), r.get("quote_custom"),
            r["category"], r.get("sub_categories"), r.get("region"),
            r.get("coop_models"), r["profile_text"], r.get("content_style"),
            r.get("past_brands"), r.get("cooperation_history"))


def row_deals(r):
    return (r["deal_id"], r["brand_id"], r["creator_id"], r["title"], r.get("category"),
            r["coop_mode"], r.get("embed_duration_sec"), r.get("agreed_price"),
            r.get("quoted_price"), r.get("revision_count"), r.get("revision_used"),
            r.get("deliverable"), r.get("exclusive_days"), r.get("authorization_scope"),
            r.get("signed_date") or None, r.get("publish_deadline") or None,
            r.get("published_date") or None, r["status"], r.get("settlement_amount"),
            r.get("requirement_text"), r.get("negotiation_notes"),
            r.get("result_views"), r.get("result_engagement"))


def row_deal_reviews(r):
    return (r["review_id"], r["deal_id"], r["reviewer_role"], r.get("rating"), r["content"])


def row_party_traits(r):
    return (r["trait_id"], r["party_type"], r["party_id"], r["trait_category"],
            r["trait_content"], r.get("severity", "info"), r.get("source_deal_id"),
            r.get("source_quote"), r.get("source_channel") or "manual_note",
            r.get("source_ref"), r.get("confidence"), r.get("verified", False))


# 表定义：主键 / 列顺序 / 取值函数 / 需要顺带刷新的时间戳列
TABLES = {
    "brands": {
        "pk": "brand_id",
        "columns": ["brand_id", "brand_name", "industry", "company_size",
                    "contact_person", "contact_wechat", "cooperation_notes"],
        "row": row_brands,
        "touch": [],
    },
    "creators": {
        "pk": "creator_id",
        "columns": ["creator_id", "nickname", "platform", "profile_url", "followers", "female_ratio",
                    "age_18_24_ratio", "age_25_34_ratio", "avg_views", "engagement_rate",
                    "quote_embed_15s", "quote_embed_30s", "quote_embed_60s", "quote_custom",
                    "category", "sub_categories", "region", "coop_models",
                    "profile_text", "content_style", "past_brands", "cooperation_history"],
        "row": row_creators,
        "touch": ["updated_at"],
    },
    "deals": {
        "pk": "deal_id",
        "columns": ["deal_id", "brand_id", "creator_id", "title", "category", "coop_mode",
                    "embed_duration_sec", "agreed_price", "quoted_price",
                    "revision_count", "revision_used", "deliverable", "exclusive_days",
                    "authorization_scope", "signed_date", "publish_deadline", "published_date",
                    "status", "settlement_amount", "requirement_text", "negotiation_notes",
                    "result_views", "result_engagement"],
        "row": row_deals,
        "touch": ["updated_at"],
    },
    "deal_reviews": {
        "pk": "review_id",
        "columns": ["review_id", "deal_id", "reviewer_role", "rating", "content"],
        "row": row_deal_reviews,
        "touch": [],
    },
    "party_traits": {
        "pk": "trait_id",
        "columns": ["trait_id", "party_type", "party_id", "trait_category", "trait_content",
                    "severity", "source_deal_id", "source_quote", "source_channel", "source_ref",
                    "confidence", "verified"],
        "row": row_party_traits,
        "touch": [],
    },
}

ORDER = ["brands", "creators", "deals", "deal_reviews", "party_traits"]


def build_sql(table, spec):
    cols = spec["columns"]
    pk = spec["pk"]
    placeholders = ",".join(["%s"] * len(cols))
    updates = [f"{c} = EXCLUDED.{c}" for c in cols if c != pk]
    updates += [f"{c} = NOW()" for c in spec["touch"]]
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT ({pk}) DO UPDATE SET {', '.join(updates)} "
        f"RETURNING (xmax = 0) AS inserted"
    )


def main():
    ap = argparse.ArgumentParser(description="增量导入：upsert 数据文件中的记录（不清空表）")
    ap.add_argument("--file", default=str(ROOT / "data" / "seed_data.json"),
                    help="数据文件路径（默认 data/seed_data.json）")
    ap.add_argument("--table", default=None,
                    help="只导入某张表：brands / creators / deals / deal_reviews / party_traits")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"[FAIL] 数据文件不存在：{path}")
        sys.exit(1)

    # utf-8-sig：兼容带 BOM 的文件（记事本 / Excel / PowerShell Out-File 导出的 JSON 常带 BOM）
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    targets = [args.table] if args.table else ORDER
    for t in targets:
        if t not in TABLES:
            print(f"[FAIL] 未知表：{t}（可选：{', '.join(ORDER)}）")
            sys.exit(1)

    print("=" * 70)
    print(f"增量导入　文件={path.name}　表={', '.join(targets)}")
    print("=" * 70)

    try:
        conn = get_conn()
    except Exception as e:
        print(f"[FAIL] 数据库连接失败：{e}")
        sys.exit(1)

    total_new = total_upd = 0
    with conn.cursor() as cur:
        for t in targets:
            spec = TABLES[t]
            rows = data.get(t, [])
            if not rows:
                print(f"  {t:14s} 文件中无数据，跳过")
                continue
            sql = build_sql(t, spec)
            ins = upd = 0
            for r in rows:
                cur.execute(sql, spec["row"](r))
                if cur.fetchone()[0]:
                    ins += 1
                else:
                    upd += 1
            total_new += ins
            total_upd += upd
            print(f"  {t:14s} 新增 {ins:>4} 条　更新 {upd:>4} 条")

    conn.close()
    print("-" * 70)
    print(f"合计：新增 {total_new} 条，更新 {total_upd} 条（已有数据未被删除）")
    print("提示：涉及文本字段时，请再跑 src/retrieval/vectorize.py 同步向量库")


if __name__ == "__main__":
    main()

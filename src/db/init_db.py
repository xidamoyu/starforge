"""
StarForge 数据库初始化脚本
用法：
    python src/db/init_db.py
功能：
    1. 建立数据库连接
    2. 执行 schema.sql 建表
    3. 导入 seed_data.json 种子数据
"""
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


def apply_schema(conn):
    schema_sql = (ROOT / "src" / "db" / "schema.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    print("[OK] schema.sql 执行完成")


def import_seed(conn):
    data = json.loads((ROOT / "data" / "seed_data.json").read_text(encoding="utf-8"))

    with conn.cursor() as cur:
        # --- brands ---
        for b in data["brands"]:
            cur.execute(
                """INSERT INTO brands (brand_id, brand_name, industry, company_size,
                                       contact_person, contact_wechat, cooperation_notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (b["brand_id"], b["brand_name"], b["industry"], b["company_size"],
                 b.get("contact_person"), b.get("contact_wechat"), b.get("cooperation_notes")),
            )
        print(f"[OK] brands: {len(data['brands'])} 条")

        # --- creators ---
        for c in data["creators"]:
            cur.execute(
                """INSERT INTO creators (
                       creator_id, nickname, platform, followers, female_ratio,
                       age_18_24_ratio, age_25_34_ratio, avg_views, engagement_rate,
                       quote_embed_15s, quote_embed_30s, quote_embed_60s, quote_custom,
                       category, sub_categories, region, coop_models,
                       profile_text, content_style, past_brands, cooperation_history)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (c["creator_id"], c["nickname"], c["platform"], c["followers"],
                 c["female_ratio"], c.get("age_18_24_ratio"), c.get("age_25_34_ratio"),
                 c.get("avg_views"), c.get("engagement_rate"),
                 c.get("quote_embed_15s"), c.get("quote_embed_30s"),
                 c.get("quote_embed_60s"), c.get("quote_custom"),
                 c["category"], c.get("sub_categories"), c.get("region"),
                 c.get("coop_models"), c["profile_text"], c.get("content_style"),
                 c.get("past_brands"), c.get("cooperation_history")),
            )
        print(f"[OK] creators: {len(data['creators'])} 条")

        # --- deals ---
        for d in data["deals"]:
            cur.execute(
                """INSERT INTO deals (
                       deal_id, brand_id, creator_id, title, category, coop_mode,
                       embed_duration_sec, agreed_price, quoted_price,
                       revision_count, revision_used, deliverable, exclusive_days,
                       authorization_scope, signed_date, publish_deadline, published_date,
                       status, settlement_amount, requirement_text, negotiation_notes,
                       result_views, result_engagement)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (d["deal_id"], d["brand_id"], d["creator_id"], d["title"], d.get("category"),
                 d["coop_mode"], d.get("embed_duration_sec"), d.get("agreed_price"),
                 d.get("quoted_price"), d.get("revision_count"), d.get("revision_used"),
                 d.get("deliverable"), d.get("exclusive_days"), d.get("authorization_scope"),
                 d.get("signed_date") or None, d.get("publish_deadline") or None,
                 d.get("published_date") or None, d["status"], d.get("settlement_amount"),
                 d.get("requirement_text"), d.get("negotiation_notes"),
                 d.get("result_views"), d.get("result_engagement")),
            )
        print(f"[OK] deals: {len(data['deals'])} 条")

        # --- party_traits ---
        for t in data["party_traits"]:
            cur.execute(
                """INSERT INTO party_traits (
                       trait_id, party_type, party_id, trait_category, trait_content,
                       severity, source_deal_id, source_quote, source_channel, source_ref,
                       confidence, verified)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (t["trait_id"], t["party_type"], t["party_id"], t["trait_category"],
                 t["trait_content"], t.get("severity", "info"), t.get("source_deal_id"),
                 t.get("source_quote"), t.get("source_channel") or "manual_note",
                 t.get("source_ref"), t.get("confidence"), t.get("verified", False)),
            )
        print(f"[OK] party_traits: {len(data['party_traits'])} 条")

        # --- deal_reviews ---
        for r in data["deal_reviews"]:
            cur.execute(
                """INSERT INTO deal_reviews (review_id, deal_id, reviewer_role, rating, content)
                   VALUES (%s,%s,%s,%s,%s)""",
                (r["review_id"], r["deal_id"], r["reviewer_role"], r.get("rating"), r["content"]),
            )
        print(f"[OK] deal_reviews: {len(data['deal_reviews'])} 条")


def verify(conn):
    print("\n===== 数据校验 =====")
    with conn.cursor() as cur:
        for tbl in ["brands", "creators", "deals", "party_traits", "deal_reviews"]:
            cur.execute(f"SELECT COUNT(*) FROM {tbl}")
            print(f"  {tbl:16s}: {cur.fetchone()[0]} 行")

        cur.execute("""
            SELECT nickname, followers, female_ratio, quote_embed_30s
            FROM creators ORDER BY followers DESC LIMIT 3
        """)
        print("\n  粉丝最多的 3 位达人：")
        for row in cur.fetchall():
            print(f"    {row[0]:16s} 粉丝={row[1]:>7,}  女性占比={row[2]}  植入30s={row[3]}元")

        cur.execute("""
            SELECT trait_category, COUNT(*) FROM party_traits
            WHERE verified = TRUE GROUP BY trait_category ORDER BY 2 DESC
        """)
        print("\n  已确认 trait 分类统计：")
        for row in cur.fetchall():
            print(f"    {row[0]:10s}: {row[1]} 条")


def main():
    try:
        conn = get_conn()
    except Exception as e:
        print(f"[FAIL] 数据库连接失败: {e}")
        print("请检查 .env 中的 PostgreSQL 配置")
        sys.exit(1)

    apply_schema(conn)
    import_seed(conn)
    verify(conn)
    conn.close()
    print("\n[完成] 数据库初始化成功")


if __name__ == "__main__":
    main()

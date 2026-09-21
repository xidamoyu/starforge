"""数据校验脚本：验证导入结果与边界样本"""
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
if not os.getenv("PGPASSWORD"):
    raise SystemExit(f"[FAIL] 未读到 .env，请检查路径: {ROOT / '.env'}")

conn = psycopg.connect(
    host=os.getenv("PGHOST"), port=os.getenv("PGPORT"),
    dbname=os.getenv("PGDATABASE"), user=os.getenv("PGUSER"),
    password=os.getenv("PGPASSWORD"),
)

with conn.cursor() as cur:
    print("=" * 70)
    print("【边界样本】女性占比 0.68~0.72 的达人（检验过滤精度）")
    print("=" * 70)
    cur.execute("""
        SELECT creator_id, nickname, followers, female_ratio, quote_embed_30s
        FROM creators WHERE female_ratio BETWEEN 0.68 AND 0.72
        ORDER BY female_ratio
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}  {r[1]:<12} 粉丝={r[2]:>7,}  女性占比={float(r[3]):.3f}  植入30s={r[4]:>6,}元")

    print()
    print("=" * 70)
    print("【critical 级 trait】最高优先级注意事项（核心私有资产）")
    print("=" * 70)
    cur.execute("""
        SELECT trait_id, party_id, trait_category, trait_content, severity
        FROM party_traits WHERE severity = 'critical' ORDER BY trait_id
    """)
    for r in cur.fetchall():
        print(f"  [{r[0]}] {r[1]} | {r[2]} | {r[3]}")

    print()
    print("=" * 70)
    print("【报价分布】用于验证预算过滤条件")
    print("=" * 70)
    cur.execute("""
        SELECT category,
               MIN(quote_embed_30s), MAX(quote_embed_30s),
               MIN(quote_custom),    MAX(quote_custom),
               COUNT(*)
        FROM creators GROUP BY category ORDER BY category
    """)
    print(f"  {'垂类':<8} {'植入30s区间':<20} {'定制区间':<22} {'数量'}")
    for r in cur.fetchall():
        print(f"  {r[0]:<8} {r[1]:>6,} ~ {r[2]:<8,}     {r[3]:>6,} ~ {r[4]:<8,}     {r[5]}")

    print()
    print("=" * 70)
    print("【模拟查询】粉丝5-30万、女性占比70%+、美妆达人（混合检索的SQL部分）")
    print("=" * 70)
    cur.execute("""
        SELECT c.creator_id, c.nickname, c.followers, c.female_ratio,
               c.quote_embed_30s, c.category,
               (SELECT COUNT(*) FROM party_traits pt
                 WHERE pt.party_type='creator' AND pt.party_id=c.creator_id
                   AND pt.verified=TRUE) AS traits
        FROM creators c
        WHERE c.platform = '抖音'
          AND c.category = '美妆'
          AND c.followers BETWEEN 50000 AND 300000
          AND c.female_ratio >= 0.70
        ORDER BY c.followers
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {r[0]}  {r[1]:<12} 粉丝={r[2]:>7,}  女性={float(r[3]):.2f}  "
                  f"植入30s={r[4]:>6,}元  【已验证注意事项 {r[6]} 条】")
    else:
        print("  （无结果）")

    print()
    print("=" * 70)
    print("【对照：放宽到女性占比 0.65+】看边界达人是否被正确纳入/排除")
    print("=" * 70)
    cur.execute("""
        SELECT creator_id, nickname, followers, female_ratio
        FROM creators
        WHERE platform='抖音' AND category='美妆'
          AND followers BETWEEN 50000 AND 300000
          AND female_ratio >= 0.65
        ORDER BY female_ratio
    """)
    for r in cur.fetchall():
        flag = "✅ 达标" if float(r[3]) >= 0.70 else "❌ 未达标（0.70门槛）"
        print(f"  {r[0]}  {r[1]:<12} 女性占比={float(r[3]):.3f}  {flag}")

conn.close()

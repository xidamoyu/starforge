"""
数据质量检查：行数 / 文本模板化 / 必填缺失 / 边界样本 / 未验证条目 / 向量库一致性。

用法（在项目根目录执行）：
    .venv\\Scripts\\python.exe .codebuddy/skills/data-pipeline/scripts/check_quality.py
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# 项目根 = .codebuddy/skills/data-pipeline/scripts/ 向上 4 级
ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")

CREATORS_MIN_UNIQ = 0.70  # 文本唯一率下限（低于此值检索会失效）


def get_conn():
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "starforge"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )


def main():
    print("=" * 74)
    print("StarForge 数据质量检查")
    print("=" * 74)

    try:
        conn = get_conn()
    except Exception as e:
        print(f"[FAIL] 数据库连接失败：{e}")
        return

    with conn, conn.cursor() as cur:
        # 1. 各表行数
        print("\n[1] 表行数")
        for t in ["brands", "creators", "deals", "deal_reviews", "party_traits"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"    {t:16s}: {cur.fetchone()[0]:>5} 行")

        # 2. 文本模板化（最关键）
        cur.execute("SELECT COUNT(*), COUNT(DISTINCT profile_text) FROM creators")
        tot, uniq = cur.fetchone()
        ratio = uniq / tot if tot else 0.0
        ok = ratio >= CREATORS_MIN_UNIQ
        print(f"\n[2] 文本唯一率（模板化检查）")
        print(f"    {uniq}/{tot} = {ratio:.1%}   下限 {CREATORS_MIN_UNIQ:.0%}   "
              f"{'OK' if ok else '!! 模板化严重 → 向量与 rerank 都会失效，需重写描述'}")

        if not ok:
            cur.execute("""
                SELECT LEFT(profile_text, 40), COUNT(*) n FROM creators
                GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 5
            """)
            print("    重复最多的描述：")
            for txt, n in cur.fetchall():
                print(f"      x{n}  {txt}")

        # 3. 必填字段缺失
        cur.execute("""
            SELECT COUNT(*) FROM creators
            WHERE profile_text IS NULL OR female_ratio IS NULL OR followers IS NULL OR category IS NULL
        """)
        miss = cur.fetchone()[0]
        print(f"\n[3] creators 必填缺失：{miss} 条   {'OK' if miss == 0 else '!! 需补全'}")

        # 4. 边界样本（刻意设计，不应被"修正"）
        cur.execute("SELECT creator_id, nickname, female_ratio FROM creators "
                    "WHERE creator_id IN ('C019','C003') ORDER BY creator_id")
        rows = cur.fetchall()
        print("\n[4] 边界样本（设计意图：C019 应被 ≥0.70 排除、C003 应纳入）")
        for cid, nick, fr in rows:
            print(f"    {cid} {nick:<12} female_ratio={fr}")
        if len(rows) < 2:
            print("    !! 边界样本缺失，评测会失效")

        # 5. 未验证条目
        cur.execute("SELECT COUNT(*) FROM party_traits WHERE verified = FALSE")
        nv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM party_traits")
        allt = cur.fetchone()[0]
        print(f"\n[5] party_traits：{allt} 条，其中未验证 {nv} 条（不参与检索）")

    # 6. 向量库
    print("\n[6] 向量库（ChromaDB）")
    try:
        import chromadb
        path = ROOT / os.getenv("CHROMA_PATH", "./data/chroma")
        coll = os.getenv("CHROMA_COLLECTION", "starforge_creators")
        client = chromadb.PersistentClient(path=str(path))
        n = client.get_collection(coll).count()
        print(f"    collection '{coll}' 向量数：{n}")
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}: {e}")

    print("\n" + "=" * 74)
    print("提示：改了文本字段后需跑 src/retrieval/vectorize.py 同步向量库")


if __name__ == "__main__":
    main()

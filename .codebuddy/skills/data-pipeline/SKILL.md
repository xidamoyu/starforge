---
name: data-pipeline
description: 用于 StarForge 项目的数据导入、校验与清洗。当用户要求「录入数据」「导入数据」「补数据」「校验数据」「清洗数据」「检查数据质量」时使用。
---

# 数据导入与质量

## 用途

处理 StarForge 的关系库数据（PostgreSQL）：导入、增量更新、质量校验、向量同步。

## 导入方式（两种，**切勿混用**）

| 场景 | 脚本 | 行为 |
|---|---|---|
| **日常新增 / 修改** | `src/db/import_data.py` | `ON CONFLICT DO UPDATE`（upsert），**不清空**已有数据 |
| 改表结构 / 从零重建 | `src/db/init_db.py` | 执行 `schema.sql`（**DROP + 重建，会清空全部数据**） |

```powershell
cd C:\Users\Administrator\WorkBuddy\2026-09-21-10-45-59\starforge
$env:PYTHONIOENCODING="utf-8"

# 增量导入（日常用这个）
.venv\Scripts\python.exe src/db/import_data.py
.venv\Scripts\python.exe src/db/import_data.py --table party_traits
.venv\Scripts\python.exe src/db/import_data.py --file data/batch_2026_10.json

# 改了文本字段后必须同步向量库，否则检索仍命中旧数据
.venv\Scripts\python.exe src/retrieval/vectorize.py

# 校验
.venv\Scripts\python.exe eval/verify_data.py
```

## 字段规范

详见 `docs/数据录入格式.md`（5 表逐字段说明 + 枚举值 + 可复制 JSON 模板）。

关键约束：

- `female_ratio` 等占比字段填 **0~1 小数**（不是百分数）
- 外键须先存在：录入顺序 `brands → creators → deals → deal_reviews / party_traits`
- `party_traits.verified = FALSE` 的条目**不参与检索**
- `source_quote` 必须是**原始材料原话**（防幻觉红线）

## 质量检查清单

导入后逐项检查：

**1. 文本模板化**（最隐蔽，直接毁掉检索质量）

```sql
SELECT COUNT(*) AS total, COUNT(DISTINCT profile_text) AS uniq FROM creators;
```

唯一占比应 **> 70%**；低于此值需重写描述，否则向量检索与 rerank 都会失效。

**2. 必填字段缺失**

```sql
SELECT COUNT(*) FROM creators WHERE profile_text IS NULL OR female_ratio IS NULL;
```

**3. 边界样本**（本项目刻意设计，不要"修正"）

- `C019`（female_ratio 0.690）应被"女性占比 ≥ 0.70"**排除**
- `C003`（female_ratio 0.710）应被**纳入**

**4. 向量库一致性**（PG 与 ChromaDB 是否同步）

```powershell
.venv\Scripts\python.exe eval/verify_vector.py
```

## 常见坑

| 坑 | 表现 | 解决 |
|---|---|---|
| **BOM** | `JSONDecodeError: Unexpected UTF-8 BOM` | 脚本已统一用 `utf-8-sig`；新脚本要跟进 |
| **误用全量重建** | 日常导入却跑了 `init_db.py` → 数据被清空 | 日常用 `import_data.py` |
| **忘记同步向量** | 检索命中不到新数据（且不报错） | 改文本后必跑 `vectorize.py` |
| **百分数当小数** | 硬过滤条件全部失效 | 填 `0.78` 而非 `78` |
| **外部键引用不存在的 ID** | 导入报错 | 先录 brands / creators |

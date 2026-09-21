# StarForge 项目交接文档

> **用途**：本文件用于把项目上下文交接给 VSCode / CodeBuddy 继续开发。
> **写于**：2026-09-21
> **交接原因**：原开发环境（WorkBuddy 桌面端）响应卡顿，转移到 VSCode 继续。

---

## 〇、给接手的 AI 助手：如何读这份文档

1. **先读第 一 节「项目一句话」和第 二 节「铁律」**——铁律是用户明确下过的行为约束，违反会被立刻纠正。
2. **再读第 三 节「当前进度」**，确认哪一步已完成、下一步该做什么。
3. **第四节是下一步的具体任务**，可直接执行。
4. 需要背景细节时再查 `docs/实施文档-全过程记录.md`（完整实施过程）和 `docs/PRD-广告中介商单Agent工作台.md`（需求规格）。
5. **第 七 节的坑全部是真实踩过的**，不要重复踩。

**当前项目绝对路径**：
```
C:\Users\Administrator\WorkBuddy\2026-09-21-10-45-59\starforge
```

---

## 一、项目一句话

面向**广告中介公司（MCN / 星图服务商）**的私有化 AI 工作台：把公司自己的历史商单经验沉淀成可检索资产，用多 Agent 串起「刊例生成 → 达人商单匹配 → 建联对齐」全流程。

- **定位**：简历作品优先，但按真实可用设计（用户所在公司后续可能真的用）。
- **差异化**：不做"又一个达人数据工具"（公开数据赛道已被巨量星图/蝉妈妈/飞瓜做透），做**公司私有成交经验的沉淀与复用**——无法标准化成 SaaS，只能私有化部署，大厂不会做。

---

## 二、铁律（用户明确要求，必须遵守）

### 2.1 沟通与判断方式

| 铁律 | 说明 |
|---|---|
| **只做客观理性判断** | 用户原话："所有对需求和我的问题只做最客观理性的判断，不必为我提供情绪价值，有就是有没有就是没有。" 不要客套、不要"这是个很好的想法"、不要为了安慰而模糊结论。 |
| **用简体中文** | 全部交流与文档。 |
| **每步停下等确认** | 用户明确要求过"先plan出来所有的方案"、"停"。完成一个步骤后停下汇报，不要一路推到底。**这点用户强调过多次

### 2.2 工程与合规铁律

| 铁律 | 说明 |
|---|---|
| **V1 不做知识图谱** | 已论证：KG 唯一优势区（多跳推理）在本场景仅占 1/4 查询类型，其余已被混合检索覆盖。前置条件是 LLM 抽三元组人工抽检准确率 ≥85%，当前不满足。 |
| **禁止伪精度评分** | 输出中**禁止**出现"匹配度 82%"这类无来源数字。每条推荐理由必须绑定**数据源字段名 + 记录 ID**，可溯源。 |
| **只抽取不生成** | 入库时由 LLM 抽取结构化条目（+人工确认）；查询时**只列事实条目原文**，不做二次生成（防幻觉）。 |

---

## 三、当前进度

### 3.1 阶段划分与状态

| 步骤 | 内容 | 状态 |
|---|---|---|
| ① | 项目骨架 + 数据库（schema / 种子数据 / 初始化） | ✅ **已完成** |
| ② | Ollama embedding 实测（验证模型可用性） | ⬜ 未开始 |
| ③ | 向量化入 ChromaDB | ⬜ 未开始 |
| ④ | 需求解析（Prompt 设计与验证） | ⬜ 未开始 |
| ⑤ | 混合检索实现（L1-A：先 SQL 过滤后向量） | ⬜ 未开始 |
| ⑥ | 可溯源理由生成 | ⬜ 未开始 |
| ⑦ | 评测集构建（30-50 条标注问题） | ⬜ 未开始 |
| ⑧ | Dify 接入 | ⬜ 未开始（放最后） |

**规则：步骤 ⑧（Dify）必须放最后。** 核心检索逻辑先在命令行调对，再接 Dify。原因见第 七 节坑 P-07。

### 3.2 步骤 ① 的产出物清单

| 文件 | 说明 | 状态 |
|---|---|---|
| `starforge/src/db/schema.sql` | 5 表 1 视图，PostgreSQL 18 | ✅ 已执行 |
| `starforge/data/seed_data.json` | 种子数据（虚构） | ✅ 已导入 |
| `starforge/src/db/init_db.py` | 建表 + 导数据 + 校验 | ✅ 已验证通过 |
| `starforge/eval/verify_data.py` | 数据校验脚本 | ✅ 已通过 |
| `starforge/.env` | 真实配置（**不入库**，已在 .gitignore） | ✅ 已配置 PG |
| `starforge/.env.example` | 配置模板 | ✅ |
| `starforge/requirements.txt` | 依赖清单 | ✅ |
| `starforge/README.md` | 项目说明 | ⚠️ 有 2 处过时描述（见第 八 节） |
| `starforge/docs/PRD-广告中介商单Agent工作台.md` | PRD v1.1 | ✅ |
| `starforge/docs/实施文档-全过程记录.md` | 全过程实施记录（11 节） | ✅ |
| `starforge/.venv/` | 虚拟环境（已建，依赖已装） | ✅ |

### 3.3 数据库实测状态

已用 `init_db.py` 跑通，实际数据量：

```
brands        :  8 行
creators      : 20 行
deals         : 17 行
party_traits  : 30 行（全部 verified=TRUE）
deal_reviews  :  0 行（表已建，暂无数据）
```

`party_traits` 分布：
- severity：`warning` 14 条 / `info` 8 条 / `critical` 8 条
- `deals.coop_mode`：`placement` 10 条 / `custom` 7 条
- `deals.status`：`settled` 14 / `producing` 2 / `signed` 1

**边界样本（刻意设计，用于检验检索精度，不要"修正"它们）**：

| 达人 | female_ratio | 设计意图 |
|---|---|---|
| C019 | 0.690 | 查询"女性占比≥0.70"时**应被排除**（卡在阈值下一位） |
| C003 | 0.710 | 同一查询中**应被纳入** |

---

## 四、下一步任务（步骤 ②，可直接执行）

### 4.1 目标

验证本地 Ollama 的 embedding 模型可用，**重点验证是否输出 NaN**。

### 4.2 背景（为什么专门验这个）

bge-m3 在 GPU 模式下处理含 **JSON / Markdown 结构**的文本时会输出 NaN 向量，导致服务报 500。本项目数据恰好大量是「结构化字段 + 聊天记录」，属于高危场景。

### 4.3 操作清单

```powershell
# 1. 确认 Ollama 服务在跑 & 已有哪些模型
ollama list

# 2. 若没有 bge-m3，拉取
ollama pull bge-m3

# 3. 实测：重点测含 Markdown/JSON 的文本是否输出 NaN
#    建议直接写个小脚本，分别测：
#      (a) 纯中文自然语言（对照组）
#      (b) 含 ``` 代码块 的文本
#      (c) 含 {"key": "value"} JSON 的文本
#      (d) 含 ### 标题 / | 表格 的 Markdown
#    判定：任一情况出现 NaN / Inf，即判定该模型不可用

# 4. 若 bge-m3 异常 → 切换备用
ollama pull qwen3-embedding:0.6b
#    注意：本机显存仅 4GB，0.6B 模型（约 639MB）够用

# 5. 配置 DashScope API Key（写入 .env）
#    第 ④ 步需要，可以现在给，也可以到时再给
```

### 4.4 判定标准

| 结果 | 动作 |
|---|---|
| 4 类文本全部输出正常有限值向量 | bge-m3 可用，继续步骤 ③ |
| 任一情况出现 NaN / Inf | **立即弃用 bge-m3**，改 `qwen3-embedding:0.6b`；并同步更新 `.env` 的 `EMBED_MODEL` 与 `EMBED_DIM` |
| 换模型后仍需重跑 | Embedding 模型一旦定死就不要换——**换模型必须重建整个向量库** |

### 4.5 ⚠️ 关键约束

**Embedding 模型必须一次定死。** 原因：换 embedding 模型 → 向量空间改变 → 已入库的所有向量失效 → 必须全量重建。所以步骤 ② 的模型选型是"一次决策"，做完不要回头改。

---

## 五、技术方案（已定稿，不要重开讨论）

### 5.1 分层模型部署

| 层 | 选型 | 理由 |
|---|---|---|
| **Embedding** | **Ollama 本地跑小模型** | 换模型需重建向量库 → 必须自持、定死。本地跑无外部依赖。建议 `qwen3-embedding:0.6b`（639MB），4GB 显存够用 |
| **主模型** | **DashScope API（OpenAI 兼容）** | 意图识别 / 需求解析 / 理由生成。云端 API 可随时切换模型，不受本机显存限制 |
| **关系库** | PostgreSQL 18 | 结构化过滤（数值范围条件） |
| **向量库** | ChromaDB（本地） | 语义检索 |
| **编排** | Dify | 外壳：对话界面、意图路由、模型接入 |

### 5.2 为什么 embedding 本地、主模型云端

- **Embedding 换模型代价高**（要重建全库）→ 必须自己控制住，不能依赖随时可能下线的第三方服务。
- **主模型换模型零代价**（只改配置）→ 用云端 API 更划算，且能随时升级。
- 本机显存只有 4GB，跑不动可用的 Agent 主模型，但跑 0.6B embedding 绰绰有余。

### 5.3 Dify 的能力边界（重要）

**Dify 内置知识库做不了混合检索，也做不了可溯源输出。** 因此：

- Dify **只做外壳**：对话界面、意图路由、模型接入。
- **核心检索逻辑必须自建 FastAPI 服务**，通过 Dify 的 HTTP 工具节点接入。
- 自建服务包含：需求解析（调 LLM）→ SQL 过滤 → 向量检索 → 可溯源理由生成。

### 5.4 混合检索策略

**为什么必做**：纯向量检索无法处理数值范围条件。比如"粉丝量 50万-200万、女性占比≥70%、植入30s报价不超过8万"，这些是**硬约束**，向量相似度算不出来。

策略分两级，V1 先做 L1-A：

| 级别 | 策略 | V1 |
|---|---|---|
| **L1-A** | 先 SQL 硬过滤 → 再对结果做向量检索 | ✅ 先做这个 |
| **L1-C** | 双路并集（SQL 结果 ∪ 向量结果）→ 合并去重 | 之后再加 |

合并策略已由用户确认：**先 L1-A，之后加 C**。

### 5.5 需求解析输出结构（预期）

LLM 把甲方大白话需求解析成结构化条件，形如：

```json
{
  "hard_filters": {
    "followers": {"min": 500000, "max": 2000000},
    "female_ratio": {"min": 0.70},
    "quote_embed_30s": {"max": 80000},
    "category": ["美妆"],
    "platform": ["抖音"]
  },
  "semantic_query": "平价敏感肌护肤品的真实测评向内容",
  "need_clarification": []
}
```

`need_clarification` 用于：需求信息不足时反问用户，而不是瞎猜。

---

## 六、数据模型要点

### 6.1 五张表

| 表 | 说明 | 关键点 |
|---|---|---|
| `brands` | 甲方/品牌方 | `cooperation_notes` 进向量库 |
| `creators` | 达人档案（核心表） | 结构化过滤字段 + 向量检索文本字段**分列存放** |
| `deals` | 商单记录 | 商务条件（对齐 Agent 的比对字段）+ `negotiation_notes` 谈判过程 |
| `deal_reviews` | 商单复盘 | 公司私有经验资产（当前 0 行） |
| `party_traits` | **【核心私有资产】** 达人/甲方脾气癖好 | 防幻觉设计见下 |

### 6.2 creators 表的字段分区（设计核心）

```
=== 量化过滤字段（走 SQL）===
followers, female_ratio, age_18_24_ratio, age_25_34_ratio,
avg_views, engagement_rate,
quote_embed_15s, quote_embed_30s, quote_embed_60s, quote_custom,
category, sub_categories[], region, coop_models[]

=== 文本描述字段（走向量）===
profile_text, content_style, past_brands, cooperation_history
                       ↑ cooperation_history 是核心私有资产
```

### 6.3 报价模型（双模式，已确认）

| 模式 | 说明 | 字段 |
|---|---|---|
| **植入 placement** | **按时长固定档位**（不是按市场浮动） | `quote_embed_15s` / `quote_embed_30s` / `quote_embed_60s` |
| **定制 custom** | 整条视频，达人自主报价 | `quote_custom` |

- 两种模式**均可做**，不是二选一 → `coop_models TEXT[] DEFAULT '{"placement","custom"}'`
- **不涉及直播**，schema 中不含任何直播字段。

### 6.4 party_traits 的防幻觉设计（核心）

```sql
trait_category  -- 沟通偏好/改稿态度/排期习惯/付款要求/内容尺度/其他
trait_content   -- 抽取出的具体内容
severity        -- info / warning / critical
source_quote    -- 【防幻觉关键】原始材料原话引用
verified        -- 仅 TRUE 的条目参与检索
```

三条设计原则：
1. 从原始素材（聊天记录/复盘笔记）由 LLM **抽取**结构化条目。
2. `source_quote` 保留原文引用 → 出问题能回溯到原话。
3. `verified = FALSE` 的条目不参与检索 → 防止脏数据污染。
4. 查询时**直接列条目原文，不做二次生成**。

### 6.5 ⚠️ schema.sql 的幂等性陷阱

`schema.sql` 开头是：

```sql
DROP VIEW  IF EXISTS v_creator_overview CASCADE;
DROP TABLE IF EXISTS party_traits CASCADE;
DROP TABLE IF EXISTS deal_reviews CASCADE;
...
```

**这意味着每次跑 `init_db.py` 都会清空所有数据。** 开发期可接受，但要注意：
- 如果手工往库里加了测试数据，重跑一次就没了。
- 后续要改 schema 时，考虑改成 `CREATE TABLE IF NOT EXISTS` + 独立的 reset 脚本。

---

## 七、踩坑记录（全部真实踩过，不要重复）

| 编号 | 坑 | 现象 | 解决 |
|---|---|---|---|
| P-01 | PowerShell 的 `curl` 是 `Invoke-WebRequest` 别名 | `curl -I <url>` 报"请为以下参数提供值: Uri" | 用 `curl.exe`（带 .exe 后缀） |
| P-02 | pip 默认源不通 | `Tunnel connection failed: 502 Bad Gateway`，重试 5 次失败 | 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| P-03 | PowerShell 输出被吞 | 命令 exit 0 但无任何输出 | 用 `Out-File` + `Get-Content` 两步走 |
| P-04 | `verify_data.py` 报 `no password supplied` | 脚本在 `eval/` 子目录，`Path(__file__).resolve().parents[2]` 算错路径，指向了项目外 | 改为 `parents[1]`，并加显式检查报错。**写脚本时注意 `parents[N]` 的层级——`src/db/` 下用 parents[2]，`eval/` 下用 parents[1]** |
| P-05 | PowerShell 控制台中文乱码 | 显示 `鎵ц瀹屾垚` | **是显示问题，不是数据问题**（库里存的是正确 UTF-8）。设 `$env:PYTHONIOENCODING="utf-8"`，或用 Python 直接读库验证 |
| P-06 | PAI-DSW 公网地址代码访问不了 | `curl.exe -I` 返回 `HTTP/1.1 302 Found` 重定向到 `account.aliyun.com` 登录页 | 浏览器能访问是因为带阿里云登录 Cookie；代码没有 → 无法直连。地址含 `?appId=MAAS`，是给 Model-as-a-Service 用的，默认要求阿里云身份认证 |
| P-07 | Dify 能力边界 | — | Dify 内置知识库**做不了混合检索、做不了可溯源输出** → Dify 只做外壳，核心检索自建 FastAPI。**这也是为什么步骤 ⑧（Dify）必须放最后——先用命令行把检索效果调对。** |

### 已排除的部署方案（不要再走一遍）

| 方案 | 结论 |
|---|---|
| 本地部署 Qwen3-14B | ❌ 本机显存仅 4GB |
| 阿里云 PAI-DSW 对外提供服务 | ❌ 公网地址需阿里云登录态（302），代码无法直连；且是限时实例 |
| 魔搭 Notebook 对外服务 | ❌ 对外访问能力有限 |
| 魔搭创空间（Studio） | ⚠️ 可行但有门槛：端口固定 7860、只能暴露一个端口、默认文件系统不持久、Docker 部署需实名+绑阿里云、GPU 需申请「xGPU乐园」、免费版 2核CPU 跑不了推理 |
| **最终方案** | ✅ **分层：Embedding 走本地 Ollama，主模型走 DashScope API** |

---

## 八、⚠️ 已知需要修正的问题（接手后建议优先处理）

### 8.1 `README.md` 有过时描述

| 位置 | 过时内容 | 应改为 |
|---|---|---|
| 技术栈表格 | `Embedding: Ollama + bge-m3` | 需按步骤 ② 实测结果定：若 bge-m3 触发 NaN 则改 `qwen3-embedding:0.6b` |
| 目录结构 | 已列出 `src/core/` `src/retrieval/` 等目录 | 这些目录**尚未创建**，实际只有 `src/db/`、`data/`、`eval/`、`docs/` |

### 8.2 `requirements.txt` 可能缺依赖

当前内容：
```
psycopg[binary]>=3.1
python-dotenv>=1.0
requests>=2.31
chromadb>=0.4.22
openai>=1.30
pandas>=2.0
```

后续会用到但**尚未加入**：`fastapi`、`uvicorn`（Dify 接入时）。步骤 ② 若写实测脚本，可能需要 `numpy`。

### 8.3 `deal_reviews` 表为空

表已建但 0 行数据。而 `deal_reviews.content` 是设计中的"进向量库"字段之一。步骤 ③ 向量化时需要考虑：是补种子数据，还是 V1 先不向量化这张表。

---

## 九、术语表

| 术语 | 含义 |
|---|---|
| **植入 / placement** | 在视频中插入产品片段，**按时长固定档位**计费（15s/30s/60s） |
| **定制 / custom** | 整条视频为品牌定制，达人自主报价 |
| **party_traits** | 达人/甲方的脾气、癖好、注意事项——公司私有经验资产 |
| **可溯源理由** | 每条推荐理由都绑定数据源字段名 + 记录 ID，可点击回溯到原始数据。禁止伪精度评分 |
| **L1-A** | 混合检索策略：先 SQL 硬过滤，再对结果做向量检索 |
| **L1-C** | 混合检索策略：SQL 结果 ∪ 向量结果，双路并集后合并去重 |
| **人工确认拦截** | 全局机制（非意图）：对外动作前强制中断，等待人工确认 |
| **意图体系** | 7 用户意图 + 1 自动管道 + 1 全局拦截（详见 PRD 第 4 章） |

---

## 十、意图体系（V2 才实现，此处备查）

**7 个用户意图**：
1. 联网通用聊天
2. 公司资产咨询（RAG）
3. 公开数据咨询
4. 话术构思
5. 刊例生成
6. 达人 ↔ 商单匹配
7. 对齐问题清单

**1 个自动管道**：⑧ 数据入库（自动触发 + 人工确认）

**1 个全局拦截**：⑨ 人工确认（全局机制，非意图）

> 讨论中修正过两点：原"甲方需求解析"降级为**匹配 Agent 的内部子步骤**（用户不会专门发起）；"人工确认"从意图改为**全局拦截层**。

> **注意**：V1 只做意图 ⑥（达人↔商单匹配）这一条链路，其余全部砍掉。意图体系是 V2 的事。

---

## 十一、复现清单（换机器时用）

```powershell
# 1. 确认环境
python --version      # 需要 3.11+
psql --version        # 需要 PostgreSQL 18
ollama list           # 需要 Ollama 在跑

# 2. 进入项目
cd C:\Users\Administrator\WorkBuddy\2026-09-21-10-45-59\starforge

# 3. 激活虚拟环境（已存在 .venv）
.venv\Scripts\Activate.ps1

# 4. 若需重装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 5. 确认 .env（从 .env.example 复制并填 PostgreSQL 密码）
#    注意 .env 不入库

# 6. 建库（若未建）
psql -U postgres -c "CREATE DATABASE starforge;"

# 7. 建表 + 导入种子数据（⚠️ 会清空现有数据，见 6.5 节）
python src/db/init_db.py

# 8. 数据校验
python eval/verify_data.py
```

**期望输出**：brands 8 / creators 20 / deals 17 / party_traits 30，边界样本 C019（0.690）与 C003（0.710）校验通过。

---

## 十二、文档索引

| 文档 | 路径 | 内容 |
|---|---|---|
| **本文件** | `docs/CONTINUE-交接文档.md` | 交接说明、铁律、进度、下一步 |
| PRD | `docs/PRD-广告中介商单Agent工作台.md` | v1.1，需求规格（11 章 + 2 附录） |
| 实施记录 | `docs/实施文档-全过程记录.md` | 全过程实施细节（11 节），含决策日志 D-01~D-10、踩坑 P-01~P-06 |

**接手时的第一步动作建议**：
1. 读本文件第二节「铁律」，确认理解行为约束。
2. 跑一遍第十一节「复现清单」，确认本地环境正常。
3. 执行第四节「步骤 ②」。
4. 完成后**停下向用户汇报**，不要连续推进到步骤 ③。

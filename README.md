# StarForge · 广告中介商单 Agent 工作台

> 面向广告中介公司（MCN / 星图服务商）的私有化 AI 工作台。
> 把公司自己的历史商单经验沉淀为可检索资产，用多 Agent 串起「刊例生成 → 达人商单匹配 → 建联对齐」全流程。

## 项目定位

**不做**"又一个达人数据工具"（公开数据赛道已被巨量星图、蝉妈妈、飞瓜数据做透）。

**做**"广告中介公司的私有商单协作工作台"——公开数据大厂做透了，但**公司私有的成交经验无人沉淀**，且每家公司数据结构不同、无法标准化成 SaaS，只能私有化部署。

详见 `docs/PRD-广告中介商单Agent工作台.md`。

## 当前阶段：V1 最小可行链路

只做一条能证明价值的链路：

```
甲方需求（大白话）
   ↓
[需求解析] LLM → 结构化条件
   ↓
[混合检索] PostgreSQL 硬过滤 + 向量语义检索
   ↓
[可溯源理由] 每条理由绑定数据源字段/记录ID
   ↓
推介单
```

**其余功能全部砍掉**（刊例、对齐、话术、入库管道、企微），等这条链路跑通再扩展。

## 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| Embedding | Ollama（本地） | 模型待定：bge-m3 需实测，若触发 NaN bug 则改 `qwen3-embedding:0.6b`。**模型必须一次定死**，换模型需重建全库 |
| 主模型 | DashScope Qwen（OpenAI 兼容） | 意图识别、需求解析、理由生成。云端 API 可随时切换 |
| 关系库 | PostgreSQL 18 | 结构化过滤 |
| 向量库 | ChromaDB | 语义检索 |
| 编排 | Dify | 外壳与界面（**放最后接入**，Dify 做不了混合检索与可溯源输出） |

> 分层原则：Embedding 换模型代价高（需重建向量库）→ 自持本地；主模型换模型零代价 → 走云端 API。

## 目录结构

```
starforge/
├── data/
│   ├── seed_data.json      # 种子数据（虚构，8甲方/20达人/17商单/30条trait）
│   └── chroma/             # 向量库（运行时生成，不入库）
├── src/
│   └── db/
│       ├── schema.sql      # 表结构
│       └── init_db.py      # 建表 + 导入种子数据
├── eval/                   # 数据校验 / 评测集
├── docs/                   # PRD、实施记录、交接文档
├── .env                    # 密钥（不入库）
└── requirements.txt
```

> 规划中但**尚未创建**的模块：`src/core/`（配置与模型客户端）、`src/retrieval/`（混合检索）、需求解析 / 理由生成。
> 完整进度见 `docs/CONTINUE-交接文档.md`。

## 数据库表

| 表 | 说明 |
|---|---|
| `brands` | 甲方/品牌方 |
| `creators` | 达人档案（结构化字段 + 向量检索文本字段） |
| `deals` | 商单记录（商务条件 + 谈判过程） |
| `deal_reviews` | 商单复盘 |
| `party_traits` | **【核心私有资产】达人/甲方的脾气、癖好、注意事项** |

### 核心设计：可溯源

`party_traits.source_quote` 保留原始材料原话引用，是**防幻觉**的关键。
只有 `verified = TRUE` 的 trait 参与检索，防止脏数据污染。

### 报价模式

- **植入（placement）**：按时长固定档位 → 15s / 30s / 60s
- **定制（custom）**：整条视频，达人自主报价
- 两种模式均可做，不涉及直播

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量
copy .env.example .env
# 编辑 .env 填入 PostgreSQL 密码

# 4. 建库
psql -U postgres -c "CREATE DATABASE starforge;"

# 5. 建表并导入种子数据
python src/db/init_db.py
```

## 文档

| 文档 | 说明 |
|---|---|
| `docs/CONTINUE-交接文档.md` | **接手先读这个**：铁律、进度、下一步任务、踩坑记录 |
| `docs/PRD-广告中介商单Agent工作台.md` | PRD v1.1，需求规格 |
| `docs/实施文档-全过程记录.md` | 全过程实施细节、决策日志、踩坑汇总 |

## 开发原则

1. **可溯源优先**：禁止输出无数据来源的评分数字（如"匹配度82%"）
2. **人工确认拦截**：入库、报价、发送等对外动作必须人工确认
3. **先命令行验证，再接框架**：检索效果在命令行调对后再接 Dify

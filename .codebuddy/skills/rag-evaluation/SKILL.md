---
name: rag-evaluation
description: 用于 StarForge 项目的检索质量评估、消融实验与策略对比。当用户要求「评测检索效果」「跑消融实验」「对比检索策略」「算召回率 / MRR / NDCG」「诊断漏召错召」时使用。
---

# RAG 评测与消融实验

## 用途

量化评估 StarForge 检索链路的质量，回答两类问题：

1. **某策略好不好**——如「混合检索比纯向量强多少」
2. **某增量有没有用**——如 rerank / 硬过滤带来的提升

## 前置检查（必须先做，否则指标无意义）

**跑任何评测前，先检查数据是否有区分度：**

```sql
-- 文本模板化程度：唯一文本数 / 总记录数（越低越糟）
SELECT COUNT(*) AS total, COUNT(DISTINCT profile_text) AS uniq FROM creators;
```

若唯一文本占比 **< 70%**，先修数据再评测。

> 模板化文本会让向量检索与 rerank **都无法区分候选**，指标会呈现「所有策略结果一样」的假象。
> 本项目实际踩过：89 条记录仅 48 种 profile_text，导致 rerank 看起来完全无效。

## 评测集结构

文件：`eval/testset.json`，分层设计：

| type | 用途 | 答案字段 |
|---|---|---|
| `parse` | 需求解析 | `expected`（结构化条件） |
| `recall` | 检索召回 | `must_recall`（必须召回的达人 ID） |
| `clarify` | 澄清反问 | `expected` |

**检索指标只使用 `recall` 类**（只有它带 golden set）。

## 执行流程

```powershell
cd C:\Users\Administrator\WorkBuddy\2026-09-21-10-45-59\starforge
$env:HF_ENDPOINT="https://hf-mirror.com"; $env:PYTHONIOENCODING="utf-8"

# 1. 消融实验：4 种策略 × recall 用例 → 指标对比表
.venv\Scripts\python.exe eval/ablation.py

# 2. 逐条诊断：查看每个用例的召回顺序，定位漏召/错召
.venv\Scripts\python.exe eval/diagnose_recall.py

# 3. 单查询看策略差异（快速肉眼验证）
.venv\Scripts\python.exe eval/test_strategy.py
```

结果落盘：`eval/ablation_result.json`

## 指标含义

脚本：`eval/metrics.py`（纯数学，不依赖 LLM）

| 指标 | 含义 | 反映 |
|---|---|---|
| Recall@K | golden set 有多少进了 top K | **召回能力** |
| MRR | 首个命中的排名倒数 | **排序质量** |
| NDCG@K | 位置加权的排序质量 | **排序质量（更细）** |
| Hit@K | 至少命中一个 | 粗粒度召回 |

## 常见陷阱

| 陷阱 | 表现 | 处理 |
|---|---|---|
| **数据模板化** | 各策略指标相同；rerank 分数出现大量完全相同的值 | 先修数据 |
| **recall 饱和** | Recall@5/@10 已达 1.0，rerank 显示无提升 | rerank 只能在 MRR/NDCG 上体现；需补充更难用例 |
| **评测标注偏差** | golden set 与业务直觉不符（如「找健身垂类」却未含头部达人） | 复核 `must_recall` |
| **LLM 解析波动** | 同一查询多次运行结果不同 | 多次运行取均值 |

## 汇报要求

输出评测结论时**必须包含**：

1. **数据前提**：唯一文本占比、用例数
2. **指标对比表**：含相对基线的增量（百分点）
3. **失败用例的具体分析**：不能只给数字
4. **明确区分**「实现问题」与「数据问题」——避免把数据缺陷误判为代码缺陷

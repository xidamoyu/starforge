"""
检索指标计算（纯数学，不依赖 LLM）。

指标说明：
    Recall@K     该召回的目标中，有多少进了 top K（查全）
    Precision@K  top K 里有多少是目标（查准）
    MRR          第一个命中目标的排名倒数（越靠前越好）
    NDCG@K       考虑位置权重的排序质量（首位权重最大）
    Hit@K        至少命中一个目标的比例
"""
import math


def recall_at_k(retrieved, expected, k):
    if not expected:
        return 0.0
    return len(set(retrieved[:k]) & set(expected)) / len(expected)


def precision_at_k(retrieved, expected, k):
    if k <= 0:
        return 0.0
    return len(set(retrieved[:k]) & set(expected)) / k


def mrr(retrieved, expected):
    exp = set(expected)
    for i, cid in enumerate(retrieved, 1):
        if cid in exp:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved, expected, k):
    exp = set(expected)
    dcg = sum(1.0 / math.log2(i + 1) for i, c in enumerate(retrieved[:k], 1) if c in exp)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(exp), k) + 1))
    return dcg / idcg if idcg else 0.0


def hit_rate(retrieved, expected, k):
    return 1.0 if set(retrieved[:k]) & set(expected) else 0.0


def evaluate_case(retrieved_ids, expected_ids, ks=(1, 3, 5, 10)):
    """对单条用例计算全部指标，返回 {指标名: 值}"""
    out = {}
    for k in ks:
        out[f"recall@{k}"] = recall_at_k(retrieved_ids, expected_ids, k)
        out[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, expected_ids, k)
        out[f"hit@{k}"] = hit_rate(retrieved_ids, expected_ids, k)
    out["mrr"] = mrr(retrieved_ids, expected_ids)
    return out


def aggregate(per_case, keys=None):
    """对多条用例的指标取平均"""
    if not per_case:
        return {}
    keys = keys or list(per_case[0].keys())
    return {k: sum(c.get(k, 0.0) for c in per_case) / len(per_case) for k in keys}

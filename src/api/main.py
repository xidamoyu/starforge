"""
步骤⑧：自建检索服务（FastAPI），供 Dify HTTP 工具节点调用

链路：需求解析（LLM）→ SQL 硬过滤 → 向量检索 → 可溯源理由生成
Dify 只做外壳（对话界面/意图路由/模型接入），核心检索在本服务里。

启动（Dify 在 WSL/Docker 里时，必须监听 0.0.0.0）：
    .venv\\Scripts\\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.retrieval.align_questions import get_align_questions  # noqa: E402
from src.retrieval.creator_info import get_creator_info  # noqa: E402
from src.retrieval.hybrid_search import build_reasons  # noqa: E402

# Dify 导入 OpenAPI 后靠 schema 的 servers 确定请求地址；默认填 WSL 侧访问 Windows 的地址
# （可用环境变量 PUBLIC_BASE_URL 覆盖；WSL IP 变动时改这里或 .env）。
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://172.21.32.1:8000")

app = FastAPI(
    title="StarForge 混合检索服务",
    version="1.0",
    description="需求解析 → SQL 硬过滤 → 向量检索 → 可溯源理由（禁止伪精度评分）",
    servers=[{"url": PUBLIC_BASE_URL}],
)

# 允许 Dify 前端（浏览器）跨域直连本服务（「从 URL 导入 OpenAPI」若由前端发起则需要）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    """FastAPI 0.141 已移除构造函数的 openapi_version 参数（固定输出 3.1.0），
    而 Dify 的 OpenAPI 导入解析器只稳定支持 3.0.x，故手动覆写降级为 3.0.3。"""
    if app.openapi_schema:
        return app.openapi_schema
    app.openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
        openapi_version="3.0.3",
    )
    return app.openapi_schema


app.openapi = custom_openapi


class SearchRequest(BaseModel):
    requirement: str
    coop_mode: Optional[str] = None   # "placement" / "custom" / None（搁置，不指定合作模式）
    top_k: int = 10


class ReasonItem(BaseModel):
    """单条可溯源理由：match（语义命中字段原文）/ trait（达人注意事项）"""
    type: str
    field: Optional[str] = None          # match：命中字段名
    quote: Optional[str] = None          # match：命中原文
    severity: Optional[str] = None       # trait：critical/warning/info
    category: Optional[str] = None       # trait：分类
    content: Optional[str] = None        # trait：内容
    source_quote: Optional[str] = None   # trait：原始材料原话
    trait_id: Optional[str] = None       # trait：可回溯 party_traits 表


class CreatorProfile(BaseModel):
    followers: Optional[float] = None
    female_ratio: Optional[float] = None
    quote_embed_30s: Optional[float] = None
    quote_custom: Optional[float] = None
    category: Optional[str] = None
    platform: Optional[str] = None


class SearchItem(BaseModel):
    creator_id: str
    nickname: Optional[str] = None
    profile: CreatorProfile
    reasons: List[ReasonItem] = []


class SearchResponse(BaseModel):
    """推荐结果：items 按相关度排序，每条绑定可溯源 reasons（禁止伪精度评分）"""
    parsed: Dict[str, Any]
    sql_count: int
    items: List[SearchItem] = []


# ---------- /creator_info：达人档案（公开数据 + 私有经验） ----------

class CreatorInfoRequest(BaseModel):
    creator_id: Optional[str] = None   # 优先，如 "C001"
    name: Optional[str] = None         # 昵称（完全匹配优先，其次模糊匹配）


class CreatorQuotes(BaseModel):
    embed_15s: Optional[int] = None
    embed_30s: Optional[int] = None
    embed_60s: Optional[int] = None
    custom: Optional[int] = None


class CreatorPublic(BaseModel):
    """公开数据（粉丝、画像、报价）"""
    nickname: Optional[str] = None
    platform: Optional[str] = None
    profile_url: Optional[str] = None
    followers: Optional[int] = None
    female_ratio: Optional[float] = None
    age_18_24_ratio: Optional[float] = None
    age_25_34_ratio: Optional[float] = None
    avg_views: Optional[int] = None
    engagement_rate: Optional[float] = None
    quotes: CreatorQuotes = CreatorQuotes()
    category: Optional[str] = None
    sub_categories: Optional[List[str]] = None
    region: Optional[str] = None
    coop_models: Optional[List[str]] = None
    profile_text: Optional[str] = None
    content_style: Optional[str] = None


class TraitItem(BaseModel):
    trait_id: str
    trait_category: Optional[str] = None
    trait_content: Optional[str] = None
    severity: Optional[str] = None
    source_quote: Optional[str] = None


class DealItem(BaseModel):
    deal_id: str
    title: Optional[str] = None
    status: Optional[str] = None
    coop_mode: Optional[str] = None
    agreed_price: Optional[int] = None
    published_date: Optional[str] = None


class ReviewItem(BaseModel):
    review_id: str
    deal_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    rating: Optional[int] = None
    content: Optional[str] = None


class CreatorPrivate(BaseModel):
    """公司私有经验（外部工具拿不到的部分）"""
    past_brands: Optional[str] = None
    cooperation_history: Optional[str] = None
    traits: List[TraitItem] = []
    deals: List[DealItem] = []
    reviews: List[ReviewItem] = []


class Freshness(BaseModel):
    data_updated_at: Optional[str] = None
    days_ago: Optional[int] = None


class CandidateItem(BaseModel):
    """昵称命中多个时返回的候选（供上层追问，不替用户猜）"""
    creator_id: str
    nickname: Optional[str] = None
    platform: Optional[str] = None
    followers: Optional[int] = None


class CreatorInfoResponse(BaseModel):
    found: bool
    ambiguous: bool = False                 # True = 命中多个，需澄清
    message: Optional[str] = None
    candidates: List[CandidateItem] = []    # ambiguous=True 时给出
    matched_by: Optional[str] = None        # id / exact_name / fuzzy_name
    creator_id: Optional[str] = None
    public: Optional[CreatorPublic] = None
    private: Optional[CreatorPrivate] = None
    freshness: Optional[Freshness] = None


# ---------- /align_questions：签约前对齐清单 ----------

class AlignRequest(BaseModel):
    deal_id: str


class AlignItem(BaseModel):
    field: str
    label: str
    status: str                      # confirmed / missing
    value: Optional[str] = None
    hint: Optional[str] = None


class AlignSummary(BaseModel):
    confirmed: int = 0
    missing: int = 0


class AlignResponse(BaseModel):
    found: bool
    message: Optional[str] = None
    deal_id: Optional[str] = None
    title: Optional[str] = None
    creator_id: Optional[str] = None
    brand_id: Optional[str] = None
    status: Optional[str] = None
    coop_mode: Optional[str] = None
    items: List[AlignItem] = []
    summary: Optional[AlignSummary] = None
    missing_labels: List[str] = []


@app.get("/health", include_in_schema=False)  # 探活接口：不进 OpenAPI，Dify 导入时不出现
def health():
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    """输入甲方需求文本，返回可溯源推荐结果"""
    try:
        return build_reasons(req.requirement, coop_mode=req.coop_mode, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/creator_info", response_model=CreatorInfoResponse)
def creator_info(req: CreatorInfoRequest):
    """输入达人 ID 或昵称，返回其公开数据与公司私有经验（只读，不生成）"""
    try:
        return get_creator_info(creator_id=req.creator_id, name=req.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/align_questions", response_model=AlignResponse)
def align_questions(req: AlignRequest):
    """输入商单 ID，返回签约前需对齐的商务条件清单（规则判定，不遗漏）"""
    try:
        return get_align_questions(req.deal_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

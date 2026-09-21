-- ============================================================
-- StarForge 广告中介商单 Agent 工作台 —— 数据库 Schema
-- PostgreSQL 18
-- ============================================================
-- 设计原则：
--   1. 结构化字段（粉丝量、报价、性别比）用于 SQL 硬过滤
--   2. 文本描述字段用于向量检索（语义匹配）
--   3. 每条数据都有稳定 ID，用于"可溯源理由"绑定
--
-- 合作模式约定（2026-09-21 确认）：
--   · 植入（placement）：按时长固定档位计费 → 15s / 30s / 60s
--   · 定制（custom）：整条视频，达人自主报价
--   · 两个模式均可做，不是二选一
--   · 不涉及直播相关字段
-- ============================================================

DROP VIEW  IF EXISTS v_creator_overview CASCADE;
DROP TABLE IF EXISTS party_traits CASCADE;
DROP TABLE IF EXISTS deal_reviews CASCADE;
DROP TABLE IF EXISTS deals CASCADE;
DROP TABLE IF EXISTS creators CASCADE;
DROP TABLE IF EXISTS brands CASCADE;

-- ------------------------------------------------------------
-- 品牌方 / 甲方
-- ------------------------------------------------------------
CREATE TABLE brands (
    brand_id            VARCHAR(16) PRIMARY KEY,
    brand_name          VARCHAR(128) NOT NULL,
    industry            VARCHAR(64)  NOT NULL,       -- 行业：美妆/食品/3C/服饰...
    company_size        VARCHAR(32),                 -- 初创/中型/大型
    contact_person      VARCHAR(64),
    contact_wechat      VARCHAR(64),
    cooperation_notes   TEXT,                        -- 合作偏好、注意事项（进向量库）
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE brands IS '甲方/品牌方信息';
COMMENT ON COLUMN brands.cooperation_notes IS '合作偏好描述，用于向量检索';

-- ------------------------------------------------------------
-- 达人（核心表）
-- ------------------------------------------------------------
CREATE TABLE creators (
    creator_id          VARCHAR(16) PRIMARY KEY,
    nickname            VARCHAR(128) NOT NULL,
    platform            VARCHAR(32)  NOT NULL,       -- 抖音/小红书/B站
    profile_url         VARCHAR(256),

    -- === 量化过滤字段 ===
    followers           INTEGER      NOT NULL,       -- 粉丝数
    female_ratio        NUMERIC(4,3) NOT NULL,       -- 女性粉丝占比 0.000-1.000
    age_18_24_ratio     NUMERIC(4,3),                -- 18-24岁占比
    age_25_34_ratio     NUMERIC(4,3),                -- 25-34岁占比
    avg_views           INTEGER,                     -- 平均播放量
    engagement_rate     NUMERIC(5,4),                -- 互动率

    -- === 报价：植入按时长固定档位 ===
    quote_embed_15s     INTEGER,                     -- 植入 15s 价格（元）
    quote_embed_30s     INTEGER,                     -- 植入 30s 价格（元）
    quote_embed_60s     INTEGER,                     -- 植入 60s 价格（元）
    -- === 报价：定制整条 ===
    quote_custom        INTEGER,                     -- 定制视频报价（元）

    -- === 分类 ===
    category            VARCHAR(64)  NOT NULL,       -- 垂类：美妆/母婴/数码...
    sub_categories      TEXT[],                      -- 细分标签
    region              VARCHAR(64),                 -- 地域
    coop_models         TEXT[] DEFAULT '{"placement","custom"}', -- 支持的合作模式

    -- === 文本描述（进向量库）===
    profile_text        TEXT         NOT NULL,       -- 达人画像描述
    content_style       TEXT,                        -- 内容风格
    past_brands         TEXT,                        -- 历史合作品牌
    cooperation_history TEXT,                        -- 历史合作情况总结【核心私有资产】

    -- === 可信度与状态 ===
    data_source         VARCHAR(32) DEFAULT 'manual',
    verified            BOOLEAN      DEFAULT FALSE,
    status              VARCHAR(16)  DEFAULT 'active',

    created_at          TIMESTAMPTZ  DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX idx_creators_platform    ON creators(platform);
CREATE INDEX idx_creators_followers   ON creators(followers);
CREATE INDEX idx_creators_category    ON creators(category);
CREATE INDEX idx_creators_female      ON creators(female_ratio);
CREATE INDEX idx_creators_quote_embed ON creators(quote_embed_30s);
CREATE INDEX idx_creators_quote_custom ON creators(quote_custom);

COMMENT ON TABLE creators IS '达人档案：结构化过滤字段 + 向量检索文本字段';
COMMENT ON COLUMN creators.cooperation_history IS '【核心私有资产】历史合作情况总结，向量检索主要数据源';
COMMENT ON COLUMN creators.coop_models IS '支持的合作模式数组：placement/custom';

-- ------------------------------------------------------------
-- 商单（合作项目）
-- ------------------------------------------------------------
CREATE TABLE deals (
    deal_id             VARCHAR(16) PRIMARY KEY,
    brand_id            VARCHAR(16) REFERENCES brands(brand_id),
    creator_id          VARCHAR(16) REFERENCES creators(creator_id),

    title               VARCHAR(256) NOT NULL,
    category            VARCHAR(64),
    coop_mode           VARCHAR(16) NOT NULL,        -- placement(植入) / custom(定制)
    embed_duration_sec  INTEGER,                     -- 植入时长（仅 placement 模式）

    -- === 商务条件（对齐 Agent 比对字段）===
    agreed_price        INTEGER,                     -- 成交价
    quoted_price        INTEGER,                     -- 报价
    revision_count      INTEGER,                     -- 约定修改次数
    revision_used       INTEGER,                     -- 实际使用次数
    deliverable         TEXT,                        -- 交付内容
    exclusive_days      INTEGER,                     -- 独家期（天）
    authorization_scope VARCHAR(128),                -- 素材授权范围

    -- === 排期 ===
    signed_date         DATE,
    publish_deadline    DATE,
    published_date      DATE,

    -- === 状态 ===
    status              VARCHAR(32) NOT NULL,        -- negotiating/signed/producing/published/settled/cancelled
    settlement_amount   INTEGER,

    -- === 文本（进向量库）===
    requirement_text    TEXT,                        -- 甲方原始需求描述
    negotiation_notes   TEXT,                        -- 谈判过程记录【核心私有资产】

    -- === 效果 ===
    result_views        INTEGER,
    result_engagement   INTEGER,

    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_deals_brand    ON deals(brand_id);
CREATE INDEX idx_deals_creator  ON deals(creator_id);
CREATE INDEX idx_deals_status   ON deals(status);
CREATE INDEX idx_deals_category ON deals(category);
CREATE INDEX idx_deals_price    ON deals(agreed_price);

COMMENT ON TABLE deals IS '商单记录：商务条件 + 谈判过程';
COMMENT ON COLUMN deals.negotiation_notes IS '【核心私有资产】谈判过程记录';
COMMENT ON COLUMN deals.coop_mode IS '合作模式：placement(植入) / custom(定制)';

-- ------------------------------------------------------------
-- 商单复盘
-- ------------------------------------------------------------
CREATE TABLE deal_reviews (
    review_id       VARCHAR(16) PRIMARY KEY,
    deal_id         VARCHAR(16) REFERENCES deals(deal_id),
    reviewer_role   VARCHAR(32) NOT NULL,       -- agency/brand/creator
    rating          INTEGER,                    -- 1-5
    content         TEXT NOT NULL,              -- 复盘内容（进向量库）
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reviews_deal ON deal_reviews(deal_id);

COMMENT ON TABLE deal_reviews IS '商单复盘记录，公司私有经验资产';

-- ------------------------------------------------------------
-- 【核心】达人/甲方的脾气与注意事项
-- ------------------------------------------------------------
-- 设计说明（2026-09-21 确认）：
--   1. 从原始素材（聊天记录/复盘笔记）由 LLM 抽取结构化条目
--   2. source_quote 保留原文引用，是"防幻觉"的关键依据
--   3. verified=FALSE 的条目不参与检索（防止脏数据污染）
--   4. 查询时直接列条目原文，不做二次生成（避免幻觉）
-- ------------------------------------------------------------
CREATE TABLE party_traits (
    trait_id        VARCHAR(16) PRIMARY KEY,
    party_type      VARCHAR(16) NOT NULL,       -- creator / brand
    party_id        VARCHAR(16) NOT NULL,       -- 达人ID 或 甲方ID

    trait_category  VARCHAR(32) NOT NULL,       -- 沟通偏好/改稿态度/排期习惯/付款要求/内容尺度/其他
    trait_content   TEXT NOT NULL,              -- 具体内容
    severity        VARCHAR(16) DEFAULT 'info', -- info / warning / critical

    source_deal_id  VARCHAR(16),                -- 来源商单
    source_quote    TEXT,                       -- 原始材料原话引用【防幻觉关键】
    confidence      NUMERIC(3,2),               -- 抽取置信度 0-1
    verified        BOOLEAN DEFAULT FALSE,      -- 是否人工确认

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_traits_party    ON party_traits(party_type, party_id);
CREATE INDEX idx_traits_verified ON party_traits(verified);
CREATE INDEX idx_traits_category ON party_traits(trait_category);

COMMENT ON TABLE party_traits IS '【核心私有资产】达人/甲方的脾气、癖好、注意事项';
COMMENT ON COLUMN party_traits.source_quote IS '原始材料原话引用，可溯源、防幻觉';
COMMENT ON COLUMN party_traits.verified IS '仅 verified=true 的条目参与检索';

-- ============================================================
-- 验证视图
-- ============================================================
CREATE OR REPLACE VIEW v_creator_overview AS
SELECT
    c.creator_id, c.nickname, c.platform, c.category,
    c.followers, c.female_ratio,
    c.quote_embed_30s, c.quote_custom,
    COUNT(d.deal_id)                                        AS deal_count,
    ROUND(AVG(d.agreed_price))                              AS avg_deal_price,
    COUNT(d.deal_id) FILTER (WHERE d.status = 'settled')    AS settled_count,
    (SELECT COUNT(*) FROM party_traits pt
      WHERE pt.party_type = 'creator'
        AND pt.party_id = c.creator_id
        AND pt.verified = TRUE)                             AS verified_trait_count
FROM creators c
LEFT JOIN deals d ON c.creator_id = d.creator_id
GROUP BY c.creator_id;

COMMENT ON VIEW v_creator_overview IS '达人概览：含历史商单数、均价、已确认注意事项数';

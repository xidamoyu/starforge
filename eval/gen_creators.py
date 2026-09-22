"""
批量生成达人种子数据（追加到 data/seed_data.json）

用途：把每个垂类补足到 5~6 个达人，用真实达人昵称 + 估算数值。
注意：粉丝数/报价/占比均为估算值（真实报价为商业机密，网上查不到），仅用于演示与评测。

用法：
    .venv\\Scripts\\python.exe eval/gen_creators.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seed_data.json"

# 垂类默认女性粉丝占比（估算）
CATEGORY_FEMALE = {
    "美妆": 0.78, "母婴": 0.88, "食品": 0.55, "3C数码": 0.25, "服饰": 0.80,
    "宠物": 0.75, "家居": 0.70, "汽车": 0.20, "游戏": 0.25, "教育": 0.55,
    "旅游": 0.62, "健身": 0.38, "健康": 0.70, "财经": 0.28, "本地生活": 0.58,
    "图书文化": 0.66, "二次元": 0.32, "情感剧情": 0.72,
}

# 新增达人名单：(昵称, 平台, 垂类, 粉丝数/万)
NEW_CREATORS = [
    # 母婴
    ("年糕妈妈", "小红书", "母婴", 500),
    ("崔玉涛育学园", "抖音", "母婴", 600),
    ("小小包麻麻", "小红书", "母婴", 320),
    # 食品
    ("密子君", "抖音", "食品", 800),
    ("蜀中桃子姐", "抖音", "食品", 1000),
    # 3C数码
    ("影视飓风", "B站", "3C数码", 700),
    ("钟文泽", "B站", "3C数码", 150),
    # 服饰
    ("程十安", "小红书", "服饰", 600),
    ("一枝南南", "小红书", "服饰", 400),
    # 宠物
    ("尿尿是只猫", "抖音", "宠物", 600),
    ("花花与三猫", "B站", "宠物", 500),
    ("在下铁头阿彪", "B站", "宠物", 200),
    # 家居
    ("住范儿", "抖音", "家居", 300),
    ("一条", "B站", "家居", 800),
    ("极简主义生活", "小红书", "家居", 200),
    # 汽车
    ("38号车评中心", "B站", "汽车", 300),
    ("韩路", "抖音", "汽车", 800),
    ("陈震同学", "抖音", "汽车", 500),
    ("李老鼠说车", "B站", "汽车", 200),
    # 游戏
    ("老番茄", "B站", "游戏", 2000),
    ("逍遥散人", "B站", "游戏", 500),
    ("某幻君", "B站", "游戏", 600),
    ("纯黑", "B站", "游戏", 400),
    # 教育
    ("李永乐老师", "抖音", "教育", 1500),
    ("罗翔说刑法", "B站", "教育", 2500),
    ("张雪峰老师", "抖音", "教育", 800),
    ("樊登", "抖音", "教育", 1000),
    # 旅游
    ("房琪kiki", "抖音", "旅游", 1500),
    ("韩船长漂流记", "抖音", "旅游", 600),
    ("侣行", "抖音", "旅游", 1200),
    ("破产兄弟", "B站", "旅游", 300),
    # 健身
    ("刘畊宏", "抖音", "健身", 6000),
    ("周六野Zoey", "B站", "健身", 500),
    ("帕梅拉", "抖音", "健身", 1500),
    ("帅soserious", "B站", "健身", 300),
    # 健康
    ("丁香医生", "抖音", "健康", 800),
    ("无穷小亮的科普日常", "B站", "健康", 800),
    ("老爸评测", "抖音", "健康", 1500),
    ("顾中一", "抖音", "健康", 300),
    # 财经
    ("温义飞的急救财经", "B站", "财经", 500),
    ("马督工", "B站", "财经", 300),
    ("财经马红漫", "抖音", "财经", 400),
    ("小Lin说", "B站", "财经", 600),
    # 本地生活
    ("唐仁杰", "B站", "本地生活", 300),
    ("王刚", "B站", "本地生活", 800),
    ("老饭骨", "抖音", "本地生活", 1000),
    ("日食记", "B站", "本地生活", 600),
    # 图书文化
    ("都靓", "抖音", "图书文化", 800),
    ("蒋勋", "抖音", "图书文化", 600),
    ("梁文道", "抖音", "图书文化", 300),
    # 二次元
    ("泛式", "B站", "二次元", 400),
    ("LexBurner", "B站", "二次元", 800),
    ("瓶子君", "B站", "二次元", 300),
    ("壁吧视频", "B站", "二次元", 200),
    # 情感剧情
    ("张同学", "抖音", "情感剧情", 1000),
    ("疯狂小杨哥", "抖音", "情感剧情", 8000),
    ("大狼狗郑建鹏夫妇", "抖音", "情感剧情", 2000),
    ("深情航仔", "抖音", "情感剧情", 500),
]


def gen(creator_id, nickname, platform, category, wan):
    followers = wan * 10000
    quote_30s = int(800 * (wan ** 0.75))
    female = CATEGORY_FEMALE.get(category, 0.6)
    return {
        "creator_id": creator_id,
        "nickname": nickname,
        "platform": platform,
        "followers": followers,
        "female_ratio": round(female, 2),
        "age_18_24_ratio": 0.30,
        "age_25_34_ratio": 0.45,
        "avg_views": int(followers * 0.4),
        "engagement_rate": round(0.03 + (wan % 30) / 1000, 3),
        "quote_embed_15s": int(quote_30s * 0.55),
        "quote_embed_30s": quote_30s,
        "quote_embed_60s": int(quote_30s * 1.5),
        "quote_custom": int(quote_30s * 1.8),
        "category": category,
        "sub_categories": [category],
        "region": "北京",
        "coop_models": ["placement", "custom"],
        "profile_text": f"{category}领域的头部达人，粉丝画像清晰、内容稳定，适合品牌垂类合作。",
        "content_style": "真实、专业、有辨识度",
        "past_brands": f"多个{category}相关品牌",
        "cooperation_history": f"历史合作稳定，对内容质量有要求。真实昵称，粉丝数/报价为估算值。",
    }


def main():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    existing = {c["creator_id"] for c in data["creators"]}
    max_id = max(int(c["creator_id"][1:]) for c in data["creators"])

    added = 0
    idx = max_id + 1
    for nickname, platform, category, wan in NEW_CREATORS:
        cid = f"C{idx:03d}"
        while cid in existing:
            idx += 1
            cid = f"C{idx:03d}"
        data["creators"].append(gen(cid, nickname, platform, category, wan))
        existing.add(cid)
        idx += 1
        added += 1

    # 更新 meta 说明
    data["_meta"]["note"] = "含真实达人昵称；粉丝数/报价/占比均为估算值，仅用于演示与评测。"
    SEED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 新增 {added} 个达人，当前共 {len(data['creators'])} 个")


if __name__ == "__main__":
    main()

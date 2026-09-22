"""验证 /creator_info：歧义候选、完全匹配、模糊唯一、按 ID、不存在、空参数。"""
import json

import requests

BASE = "http://127.0.0.1:8000"


def call(payload):
    r = requests.post(f"{BASE}/creator_info", json=payload, timeout=30)
    return r.status_code, r.json()


def main():
    print("=" * 78)
    print("验证 /creator_info")
    print("=" * 78)

    # 1. 歧义：多个候选 → 不应猜，应返回候选
    s, d = call({"name": "小满"})
    print(f"\n1. 昵称 '小满'（有歧义）→ HTTP {s} | found={d.get('found')} "
          f"| ambiguous={d.get('ambiguous')}")
    print(f"   message: {d.get('message')}")
    for c in d.get("candidates", []):
        print(f"     - {c.get('creator_id')} {c.get('nickname')} 粉丝={c.get('followers')}")

    # 2. 完全匹配 → 直接返回档案
    s, d = call({"name": "小满不加糖"})
    print(f"\n2. 昵称 '小满不加糖'（完全匹配）→ HTTP {s} | found={d.get('found')} "
          f"| matched_by={d.get('matched_by')} | id={d.get('creator_id')}")

    # 3. 模糊唯一 → 直接返回
    s, d = call({"name": "小满去旅行"})
    print(f"\n3. 昵称 '小满去旅行' → HTTP {s} | found={d.get('found')} "
          f"| matched_by={d.get('matched_by')} | id={d.get('creator_id')}")

    # 4. 按 ID → 完整档案
    s, d = call({"creator_id": "C001"})
    print(f"\n4. 按 ID 'C001' → HTTP {s} | found={d.get('found')} | matched_by={d.get('matched_by')}")
    if d.get("found"):
        pub, prv = d["public"], d["private"]
        print(f"   public: 粉丝={pub.get('followers')} 女性占比={pub.get('female_ratio')} 垂类={pub.get('category')}")
        print(f"   quotes: {json.dumps(pub.get('quotes'), ensure_ascii=False)}")
        print(f"   private: traits={len(prv.get('traits', []))} deals={len(prv.get('deals', []))} "
              f"reviews={len(prv.get('reviews', []))}")
        if prv.get("traits"):
            print(f"   首条 trait: {json.dumps(prv['traits'][0], ensure_ascii=False)}")
        print(f"   freshness: {json.dumps(d.get('freshness'), ensure_ascii=False)}")

    # 5. 不存在
    s, d = call({"name": "这个达人不存在xyz"})
    print(f"\n5. 查不存在 → HTTP {s} | found={d.get('found')} | message={d.get('message')}")

    # 6. 空参数
    s, d = call({})
    print(f"\n6. 空参数 → HTTP {s} | found={d.get('found')} | message={d.get('message')}")

    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

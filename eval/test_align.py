"""验证 /align_questions：正常单、字段不全的单、不存在的单、空参数。"""
import json

import requests

BASE = "http://127.0.0.1:8000"


def call(payload):
    r = requests.post(f"{BASE}/align_questions", json=payload, timeout=30)
    return r.status_code, r.json()


def main():
    print("=" * 78)
    print("验证 /align_questions")
    print("=" * 78)

    for deal_id in ["D001", "D005", "D014", "D999"]:
        s, d = call({"deal_id": deal_id})
        print(f"\n--- {deal_id} → HTTP {s} | found={d.get('found')} ---")
        if d.get("found"):
            print(f"  {d.get('title')} | 状态={d.get('status')} | 模式={d.get('coop_mode')}")
            print(f"  汇总: {json.dumps(d.get('summary'), ensure_ascii=False)}"
                  f"  待确认: {d.get('missing_labels')}")
            for i in d.get("items", []):
                mark = "OK " if i["status"] == "confirmed" else "?? "
                print(f"    {mark}{i['label']}: {i.get('value') or i.get('hint')}")
        else:
            print(f"  {d.get('message')}")

    s, d = call({})
    print(f"\n空参数 → HTTP {s} | found={d.get('found')} | {d.get('message')}")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

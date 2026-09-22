"""
步骤⑧验证：FastAPI 检索服务（用 TestClient，无需启动服务器）

用法：
    .venv\\Scripts\\python.exe eval/test_api.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402

client = TestClient(app)


def main():
    r = client.get("/health")
    print("GET /health ->", r.status_code, r.json())

    payload = {
        "requirement": "粉丝量5万到30万，女性粉丝占比70%以上，抖音平台，美妆垂类，植入30秒报价不超过2万",
        "top_k": 5,
    }
    r = client.post("/search", json=payload)
    print("\nPOST /search ->", r.status_code)
    if r.status_code != 200:
        print(r.text)
        return
    data = r.json()
    print("  sql_count:", data["sql_count"])
    print("  parsed.hard_filters:", json.dumps(data["parsed"]["hard_filters"], ensure_ascii=False))
    for it in data["items"][:3]:
        print(f"  · {it['creator_id']} {it['nickname']} "
              f"粉丝={int(it['profile']['followers']):,} 植入30s={it['profile']['quote_embed_30s']}")
        for reason in it["reasons"][:2]:
            if reason["type"] == "trait":
                print(f"      [{reason['severity']}] {reason['content']} (trait_id={reason['trait_id']})")
            elif reason["type"] == "match":
                print(f"      命中[{reason['field']}]: {reason['quote'][:40]}")


if __name__ == "__main__":
    main()

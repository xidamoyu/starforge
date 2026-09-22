"""
公开数据抓取可行性探测（低频单次，不批量）。

目的：判断「达人公开数据（粉丝数 / 报价）自动刷新」走哪条路——
      能稳定抓到 → L2（定时抓取）
      抓不到     → L1（人工定期导出 + 新鲜度提示）

只做连通性与反爬特征探测，不做任何绕过、不批量请求。
"""
import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

TARGETS = [
    ("抖音首页", "https://www.douyin.com/"),
    ("小红书首页", "https://www.xiaohongshu.com/"),
    ("星图(抖音官方)", "https://www.xingtu.cn/"),
    ("蝉妈妈", "https://www.chanmama.com/"),
    ("巨量算数", "https://trendinsight.oceanengine.com/"),
]


def probe():
    for name, url in TARGETS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            body = r.text or ""
            title = re.search(r"<title>(.*?)</title>", body, re.S)
            t = title.group(1).strip()[:36] if title else "-"
            print(f"  {name:16s} HTTP {r.status_code}  len={len(body):>7}  title={t}")
            low = body.lower()
            flags = []
            if "登录" in body or "login" in low or "signin" in low:
                flags.append("疑似需登录")
            if "验证" in body or "captcha" in low or "滑块" in body:
                flags.append("疑似有验证")
            if "javascript" in low and len(body) < 3000:
                flags.append("正文靠 JS 渲染")
            if flags:
                print(f"    └─ {' / '.join(flags)}")
        except Exception as e:
            print(f"  {name:16s} FAIL  {type(e).__name__}: {e}")


DEEP = [
    ("抖音搜索页(无登录)", "https://www.douyin.com/search/%E5%B0%8F%E6%BB%A1%E4%B8%8D%E5%8A%A0%E7%B3%96"),
    ("抖音web搜索API", "https://www.douyin.com/aweme/v1/web/discover/search/?keyword=test&count=5&offset=0"),
    ("小红书搜索页(无登录)", "https://www.xiaohongshu.com/search_result?keyword=%E7%BE%8E%E5%A6%86"),
    ("iesdouyin用户接口(旧)", "https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=MS4wLjABAAAAtest"),
]

DATA_HINTS = ["follower", "粉丝", "fans", "nickname", "昵称", "sec_uid", "aweme_count"]


def probe_deep():
    print("\n--- 第二轮：具体达人数据可达性 ---")
    for name, url in DEEP:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            body = r.text or ""
            low = body.lower()
            hits = [h for h in DATA_HINTS if h.lower() in low]
            print(f"  {name:22s} HTTP {r.status_code}  len={len(body):>7}  "
                  f"命中数据字段={hits if hits else '无'}")
            if "登录" in body or "login" in low:
                print("    └─ 返回登录页/要求登录")
        except Exception as e:
            print(f"  {name:22s} FAIL  {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=" * 78)
    print("公开数据抓取可行性探测（低频单次）")
    print("=" * 78)
    probe()
    probe_deep()
    print("=" * 78)
    print("判定：出现「需登录 / 有验证 / 命中数据字段=无」→ L2 抓取成本很高，建议 L1。")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weread_pull.py — 拉取微信读书官方 Agent Gateway 数据（纯标准库，无需 pip install）
用法: python3 weread_pull.py <key文件路径> [输出目录]
Key 文件里只有一行 wrk-xxx。Key 不会打印、不会写入任何输出文件。
"""
import json, os, sys, time, urllib.request
import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"

def call(api_key, api_name, params=None, retries=3):
    body = {"api_name": api_name, "skill_version": SKILL_VERSION}
    if params:
        body.update(params)
    req = urllib.request.Request(
        GATEWAY,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    last_err = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            if data.get("errcode") not in (0, None):
                raise RuntimeError(f"{api_name} errcode={data.get('errcode')} {data.get('errmsg','')}")
            if data.get("upgrade_info"):
                print(f"!! 官方提示升级: {json.dumps(data['upgrade_info'], ensure_ascii=False)[:200]}")
            return data
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"{api_name} 连续失败: {last_err}")

def main():
    key_file = sys.argv[1] if len(sys.argv) > 1 else "wxds.txt"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "weread-data"
    os.makedirs(out_dir, exist_ok=True)
    with open(key_file, "r", encoding="utf-8") as f:
        api_key = f.read().strip()
    if not api_key.startswith("wrk-"):
        sys.exit("key 文件内容应为 wrk- 开头的 API Key")
    print(f"key 已加载: wrk-***{api_key[-4:]}")

    def save(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

    # 1. 书架
    shelf = call(api_key, "/shelf/sync")
    save("shelf.json", shelf)
    print(f"✓ 书架: {len(shelf.get('books', []))} 本")
    time.sleep(0.8)

    # 2. 阅读统计（4 种模式）
    stats = {}
    for mode in ["weekly", "monthly", "annually", "overall"]:
        try:
            stats[mode] = call(api_key, "/readdata/detail", {"mode": mode})
            print(f"✓ 统计/{mode}")
        except Exception as e:
            print(f"× 统计/{mode}: {str(e)[:80]}")
        time.sleep(0.8)
    save("readdata.json", stats)

    # 3. 笔记本（分页拉全）
    notebooks, last_sort, page = [], None, 0
    while page < 10:
        params = {"count": 100}
        if last_sort is not None:
            params["lastSort"] = last_sort
        nb = call(api_key, "/user/notebooks", params)
        books = nb.get("books", [])
        notebooks.extend(books)
        page += 1
        if not nb.get("hasMore") or not books:
            break
        last_sort = books[-1].get("sort")
        time.sleep(0.8)
    save("notebooks.json", {"totalBookCount": len(notebooks), "books": notebooks})
    print(f"✓ 笔记本: {len(notebooks)} 本书有笔记")

    # 4. 每本书：章节目录 + 划线 + 我的想法 + 进度
    details, done = {}, 0
    for nb in notebooks:
        book_id = nb["bookId"]
        title = (nb.get("book") or {}).get("title", "?")
        d = {}
        try:
            d["chapters"] = call(api_key, "/book/chapterinfo", {"bookId": book_id}).get("chapters")
        except Exception:
            d["chapters"] = None
        time.sleep(0.7)
        try:
            d["highlights"] = call(api_key, "/book/bookmarklist", {"bookId": book_id})
        except Exception as e:
            d["highlights"] = {"err": str(e)[:80]}
        time.sleep(0.7)
        try:
            reviews, synckey, guard = [], 0, 0
            while guard < 20:
                r = call(api_key, "/review/list/mine", {"bookid": book_id, "synckey": synckey, "count": 100})
                reviews.extend(r.get("reviews", []))
                if not r.get("hasMore"):
                    break
                synckey = r.get("synckey", 0)
                guard += 1
                time.sleep(0.7)
            d["myThoughts"] = reviews
        except Exception as e:
            d["myThoughts"] = {"err": str(e)[:80]}
        time.sleep(0.7)
        details[book_id] = d
        done += 1
        hl = d["highlights"]
        n_hl = len(hl.get("updated", [])) if isinstance(hl, dict) and "err" not in hl else "?"
        n_th = len(d["myThoughts"]) if isinstance(d["myThoughts"], list) else "?"
        print(f"  [{done}/{len(notebooks)}] {title} 划线{n_hl} 想法{n_th}")
    save("book-details.json", details)
    print("✓ 完成 →", out_dir)

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""生成纯虚构演示数据 → 演示看板（用于教程截图，零真实数据）"""
import json, os, sqlite3, time, random, shutil, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

random.seed(42)
D = "share-demo"
shutil.rmtree(D, ignore_errors=True)
os.makedirs(D, exist_ok=True)

# ---- shelf：60 本虚构书 ----
fake_titles = ["山月往来录", "四季食堂", "缓慢的平原", "夜航地图", "群鸟之后", "临水照花",
               "旧铁轨与蝉鸣", "玻璃灯塔", "南方植物园", "雪线之下", "纸船远航", "午夜面包房",
               "银河修理员", "慢船去往浅滩", "候鸟旅馆", "雨季不再来的夏天", "午后的考古学",
               "风从麦原来", "长街短梦", "拾穗人手记", "岛屿边缘", "夜晚的潜水艇手", "春山可望",
               "昨日的咖啡渍", "无名车站", "旅鼠的冬天", "绿皮火车志", "深海邮局", "苹果树下",
               "时间的形状", "屋檐上的猫", "野草莓平原", "半亩月光", "写信的人", "南方来信",
               "雪落在旧书页", "灯塔看守人的狗", "晚风信箱", "铁道员", "木星旅馆"]
books = [{"bookId": f"fb{i:03d}", "title": t, "author": f"作者{i%7+1}号",
          "cover": "", "deepLink": "", "bookStatus": 1} for i, t in enumerate(fake_titles)]
json.dump({"books": books, "albums": []}, open(f"{D}/shelf.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- readdata：2019→2026 月度轨迹 ----
now = int(time.time())
read_times = {}
for year in range(2019, 2027):
    for month in range(1, 13):
        ts = int(time.mktime((year, month, 1, 0, 0, 0, 0, 0, -1)))
        if ts > now:
            break
        read_times[str(ts)] = random.choice([0, 1200, 3600, 7200, 10800, 14400, 20000])
json.dump({"overall": {"readTimes": read_times, "totalReadTime": 486500,
                        "preferBooks": []},
           "weekly": {}, "monthly": {}, "annually": {}},
          open(f"{D}/readdata.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- 笔记本：8 本有笔记 ----
note_ids = [0, 3, 6, 10, 14, 20, 25, 33]
demo_chapters = {
    0: ["第一章 灯塔", "第二章 潮汐"],
    3: ["上部 春", "下部 秋"],
    6: ["第一章 到达", "第二章 离开"],
}
nb_books, details = [], {}
for k, i in enumerate(note_ids):
    b = books[i]
    prog = random.choice([15, 38, 55, 72, 90, 100])
    last = now - random.randint(86400, 86400 * 90)
    nb_books.append({"bookId": b["bookId"], "book": b, "noteCount": 3, "bookmarkCount": 2,
                     "reviewCount": 1, "sort": last, "readingProgress": prog})
    ch_uid = 100 + k
    details[b["bookId"]] = {
        "chapters": [{"chapterUid": ch_uid, "chapterIdx": 0, "title": "第一章 灯塔"}],
        "highlights": {"updated": [
            {"chapterUid": ch_uid, "markText": "灯塔的意义不在于照亮海面，而在于让航行者确认自己的位置。",
             "range": "1-0-20-1-0-45", "createTime": last - 86400},
            {"chapterUid": ch_uid, "markText": "所有伟大的导航术，本质上都是与不确定性共处的艺术。",
             "range": "2-0-10-2-0-60", "createTime": last - 86400 * 2},
        ], "chapters": [{"chapterUid": ch_uid, "title": "第一章 灯塔"}]},
        "myThoughts": [{"review": {"chapterUid": ch_uid, "abstract": "读到这段想起博尔赫斯的巴别图书馆——确认位置和确认存在，也许是一回事。",
                                    "createTime": last - 86400 * 3}}],
    }
json.dump({"totalBookCount": len(nb_books), "books": nb_books},
          open(f"{D}/notebooks.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(details, open(f"{D}/book-details.json", "w", encoding="utf-8"), ensure_ascii=False)

# ---- 共读演示书：完全虚构 ----
segs = [
    (0, "第一章 灯塔", 0, "守塔人在日志的第一页写道：光不是用来征服黑暗的，是用来标记边界——这里有人，这里被记得。"),
    (0, "第一章 灯塔", 1, "他每天擦亮透镜，像擦拭一段不肯褪色的记忆。船从远处经过，没有人知道塔里的人也在凝视他们。"),
    (0, "第一章 灯塔", 2, "“你见过最远的船是什么样子？”学徒问。“最远的船，”守塔人说，“是消失前还在发光的那一艘。”"),
]
db = sqlite3.connect(f"{D}/segments.db")
db.execute("CREATE TABLE segments (id INTEGER PRIMARY KEY, chapter_idx INT, chapter_title TEXT, para_idx INT, text TEXT)")
for i, (ci, ct, pi, text) in enumerate(segs, 1):
    db.execute("INSERT INTO segments VALUES (?,?,?,?,?)", (i, ci, ct, pi, text))
db.commit(); db.close()
json.dump({"book": "示例书《灯塔日志》.epub", "totalSegments": len(segs),
           "chapters": [{"idx": 0, "title": "第一章 灯塔", "segStart": 0}],
           "dbPath": os.path.abspath(f"{D}/segments.db")},
          open(f"{D}/book.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"1": {"user": "这段像在写守塔，其实在写所有坚持记录的人。", "ai": "第一页日志就把“光”重新定义了：不是照亮，是标记。这个动词的转换贯穿全书——守塔人做的每一件事，都是把宏大还原成具体的日常。"},
           "3": {"user": "", "ai": "注意“消失前还在发光”的双重含义：物理上的船和记忆里的人。作者不写离别，只写光还在——这是全书最温柔的处理方式。"}},
          open(f"{D}/coread-notes.json", "w", encoding="utf-8"), ensure_ascii=False)

print("✓ 演示数据就绪 →", D)

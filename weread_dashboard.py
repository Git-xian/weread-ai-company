#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weread_dashboard.py — 生成共读看板（纯标准库）。
用法: python3 weread_dashboard.py <数据目录> [输出html]
读取 <数据目录>/{shelf,readdata,notebooks,book-details}.json + 可选 book.json/segments.db（共读库）
可选 coread-notes.json：{"<segId>": {"user": "...", "ai": "..."}}
"""
import json, os, re, sqlite3, sys, time

import io as _io
if hasattr(sys.stdout, "buffer"):
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def fmt_time(sec):
    if sec is None:
        return "—"
    h, m = int(sec) // 3600, (int(sec) % 3600) // 60
    return f"{h}小时{m}分" if h else f"{m}分钟"

def fmt_date(ts):
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(ts)))
    except Exception:
        return "—"

def load(d, name, default):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

# ---------- 共读库（EPUB 拆分结果，可选） ----------
def find_coread_dir(data_dir):
    """共读库候选：data_dir 根目录 + data_dir/books/* 子目录，取 book.json 最新者。"""
    cands = []
    if os.path.exists(os.path.join(data_dir, "book.json")):
        cands.append(data_dir)
    books_root = os.path.join(data_dir, "books")
    if os.path.isdir(books_root):
        for name in sorted(os.listdir(books_root)):
            d = os.path.join(books_root, name)
            if os.path.exists(os.path.join(d, "book.json")) and os.path.exists(os.path.join(d, "segments.db")):
                cands.append(d)
    if not cands:
        return None
    return max(cands, key=lambda p: os.path.getmtime(os.path.join(p, "book.json")))

def load_coread(data_dir):
    cdir = find_coread_dir(data_dir)
    if not cdir:
        return None
    with open(os.path.join(cdir, "book.json"), encoding="utf-8") as f:
        book_meta = json.load(f)
    db_path = os.path.join(cdir, "segments.db")
    if not os.path.exists(db_path):
        db_path = book_meta.get("dbPath") or db_path
    if not os.path.exists(db_path):
        return None
    db = sqlite3.connect(db_path)
    rows = db.execute("SELECT id, chapter_idx, chapter_title, para_idx, text FROM segments ORDER BY id").fetchall()
    db.close()
    notes = load(cdir, "coread-notes.json", {})
    segs = [{"id": r[0], "ch": r[1], "chTitle": r[2], "idx": r[3], "text": r[4],
             "user": (notes.get(str(r[0])) or {}).get("user", ""),
             "ai": (notes.get(str(r[0])) or {}).get("ai", "")} for r in rows]
    book_meta["_dir"] = cdir  # 该书数据所在文件夹（批注 JSON 也在这里）
    return {"meta": book_meta, "segments": segs}

def coread_html(coread):
    if not coread:
        return ""
    ch_map = {}
    for s in coread["segments"]:
        ch_map.setdefault(s["ch"], []).append(s)
    parts = ['<div class="panel" id="coread">',
             '<h3 class="cr-head">📖 共读模式（原版书对照）<span class="cr-sub">点任意段落 → 写 🟡你的 / 🔵助手的批注</span></h3>']
    for ci in sorted(ch_map):
        parts.append(f'<h4 class="cth">{esc(ch_map[ci][0]["chTitle"])}</h4>')
        for s in ch_map[ci]:
            u = f'<div class="u-note">🟡 你：{esc(s["user"])}</div>' if s["user"] else ""
            a = f'<div class="a-note">🔵 助手：{esc(s["ai"])}</div>' if s["ai"] else ""
            parts.append(f'<div class="seg" id="seg-{s["id"]}" onclick="pick({s["id"]})">'
                         f'<div class="seg-text">{esc(s["text"])}</div>{u}{a}</div>')
    parts.append('''<div id="editor" hidden>
      <div id="edit-which" class="mm"></div>
      <textarea id="edit-user" placeholder="🟡 你的批注…"></textarea>
      <textarea id="edit-ai" placeholder="🔵 助手的批注…"></textarea>
      <button onclick="saveNote()">保存</button>
      <span class="hint">保存后记得导出 JSON 发给助手</span>
    </div>
    <details id="export-box"><summary>📤 导出批注（发给助手保存）</summary><div id="coread-json"></div></details></div>''')
    return "".join(parts)

COREAD_JS = """
function pick(id){
  document.querySelectorAll('.seg.on').forEach(function(x){x.classList.remove('on')});
  var el=document.getElementById('seg-'+id);el.classList.add('on');cur=id;
  var ed=document.getElementById('editor');ed.hidden=false;
  document.getElementById('edit-which').textContent='第 '+id+' 段 · '+(el.querySelector('.seg-text').textContent.slice(0,40))+'…';
  var n=COREAD_NOTES[String(id)]||{};
  document.getElementById('edit-user').value=n.user||'';
  document.getElementById('edit-ai').value=n.ai||'';
}
function saveNote(){
  if(cur==null)return;
  COREAD_NOTES[String(cur)]={user:document.getElementById('edit-user').value,ai:document.getElementById('edit-ai').value};
  var el=document.getElementById('seg-'+cur);
  var un=el.querySelector('.u-note'); if(un)un.remove();
  var an=el.querySelector('.a-note'); if(an)an.remove();
  var n=COREAD_NOTES[String(cur)];
  if(n.user){var u=document.createElement('div');u.className='u-note';u.textContent='🟡 你：'+n.user;el.appendChild(u)}
  if(n.ai){var a=document.createElement('div');a.className='a-note';a.textContent='🔵 助手：'+n.ai;el.appendChild(a)}
  document.getElementById('coread-json').textContent=JSON.stringify(COREAD_NOTES);
  alert('已保存在页面里。点下方「📤 导出批注」把 JSON 发给助手即可长期保存');
}
"""

CSS = """
:root{--bg:#faf7f2;--card:#fff;--ink:#2c2a26;--sub:#8a8578;--yellow:#f5c518;--blue:#4a90d9;--purple:#9b6bd3;--line:#e8e2d6}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:15px/1.7 "PingFang SC","Microsoft YaHei",sans-serif;padding:28px 14px 80px}
.wrap{max-width:860px;margin:0 auto}
h1{font-size:22px}.sub{color:var(--sub);font-size:13px;margin:4px 0 14px}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{flex:1;font:inherit;font-size:14px;font-weight:600;padding:10px 0;border:1px solid var(--blue);border-radius:10px;background:var(--card);color:var(--ink);cursor:pointer;box-shadow:0 1px 4px rgba(74,144,217,.15)}
.tab.off{background:#e9e4da;color:#a39c8c;font-weight:400;border-color:#e0dacd;box-shadow:none}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:21px}.kpi span{color:var(--sub);font-size:12px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:18px}
.panel h3{font-size:14px;color:var(--sub);margin-bottom:10px}.hint{font-weight:400;font-size:11px;margin-left:8px}
.cr-book{background:#f4f8fd;border:1px solid #d8e5f4;border-radius:10px;padding:10px 14px;margin-bottom:12px;font-size:14px}
.cr-book-sub{display:block;color:var(--sub);font-size:11px;margin-top:2px}
.cr-head{display:block}
.cr-sub{display:block;font-weight:400;font-size:12px;color:var(--sub);margin-top:3px}
.heat{display:flex;gap:10px;overflow-x:auto;padding-bottom:4px}
.hm-col{display:flex;flex-direction:column;align-items:center;gap:4px;flex:0 0 auto}
.hm-col span{font-size:10px;color:var(--sub)}
.hm-col .cell{width:36px;height:36px;border-radius:9px}
.cell{background:#efece5}
.cell:hover{transform:scale(1.08)}
.cell.l1{background:#cfe3f7}.cell.l2{background:#a3cbef}.cell.l3{background:#6fa8de}.cell.l4{background:#3d7fc1}
.top-row{display:flex;gap:10px;padding:3px 0;font-size:14px}.rk{color:var(--sub);width:18px}
.tm{margin-left:auto;color:var(--sub);font-size:12px}
.search{width:100%;padding:9px 14px;border:1px solid var(--line);border-radius:10px;font:inherit;margin-bottom:12px;background:#fff}
.book-card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin-bottom:10px;overflow:hidden}
.bh{padding:13px 16px;cursor:pointer;display:block}
.bh:hover{background:#fdfbf7}
.bt{font-weight:600;font-size:15px;line-height:1.45;word-break:break-word}
.ba{color:var(--sub);font-weight:400;font-size:13px;margin-left:8px;white-space:normal}
.bs{color:var(--sub);font-size:12px;display:flex;align-items:center;gap:10px;margin-top:6px;flex-wrap:wrap}
.prog{display:inline-flex;align-items:center;width:78px;height:5px;background:#efece5;border-radius:3px;flex:0 0 auto}
.pb{height:100%;background:var(--blue);border-radius:3px}
.prog b{position:absolute;left:calc(100% + 6px);font-size:11px;color:var(--sub);font-weight:400;white-space:nowrap}
.rd{color:#8a9a6b;font-size:11px}
.open{color:var(--blue);font-size:12px;text-decoration:none;margin-left:auto}
.bb{border-top:1px dashed var(--line);padding:4px 16px 12px}
.mark{padding:11px 0;border-bottom:1px dashed var(--line)}.mark:last-child{border:0}
.mm{color:var(--sub);font-size:12px;margin-bottom:3px}.mt{font-size:14px}
.highlight .mt{border-left:3px solid var(--yellow);padding-left:10px}
.thought .mt{border-left:3px solid var(--purple);padding-left:10px}
.ai{margin-top:7px;padding:7px 11px;background:#f4f8fd;border-left:3px solid var(--blue);border-radius:0 6px 6px 0;font-size:13px;color:#5b7fa6}
.empty{color:var(--sub);text-align:center;padding:16px}
.cth{margin:14px 0 6px;color:#6b6250;font-size:15px}
.seg{padding:8px 10px;border-radius:8px;cursor:pointer;margin:2px 0}
.seg:hover{background:#fdf8ea}
.seg.on{background:#fdf3d1;outline:1px solid var(--yellow)}
.seg-text{font-size:14px}
.u-note{margin-top:5px;font-size:13px;background:#fdf6d8;border-left:3px solid var(--yellow);padding:5px 9px;border-radius:0 6px 6px 0}
.a-note{margin-top:5px;font-size:13px;background:#f4f8fd;border-left:3px solid var(--blue);padding:5px 9px;border-radius:0 6px 6px 0}
#editor{margin-top:12px;border-top:1px dashed var(--line);padding-top:10px}
textarea{width:100%;min-height:56px;font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;margin:4px 0}
button{font:inherit;padding:7px 18px;border:0;border-radius:8px;background:var(--blue);color:#fff;cursor:pointer}
#coread-json{margin-top:8px;padding:8px;background:#f6f4ee;border-radius:8px;font:11px/1.5 monospace;word-break:break-all;max-height:140px;overflow:auto;color:#7a7466}
#export-box{margin-top:12px}
#export-box summary{cursor:pointer;color:var(--blue);font-size:13px;padding:6px 0}
footer{margin-top:26px;text-align:center;color:var(--sub);font-size:12px}
"""

def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "weread-data"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(data_dir, "dashboard.html")

    shelf = load(data_dir, "shelf.json", {})
    stats = load(data_dir, "readdata.json", {})
    notebooks = load(data_dir, "notebooks.json", {})
    details = load(data_dir, "book-details.json", {})

    books = shelf.get("books", [])
    nb_list = notebooks.get("books", [])

    per_book = []
    for nb in nb_list:
        meta = nb.get("book") or {}
        d = details.get(nb["bookId"], {})
        last_ts = nb.get("sort") or 0  # 微信读书的笔记本排序字段 = 最后笔记时间
        hl = d.get("highlights") or {}
        hl_items = [] if ("err" in hl or not isinstance(hl, dict)) else hl.get("updated", [])
        ch_meta = {c.get("chapterUid"): c.get("title") for c in (hl.get("chapters") or [])}
        chap_meta = {c.get("chapterUid"): c.get("title") for c in (d.get("chapters") or [])}
        th = d.get("myThoughts") if isinstance(d.get("myThoughts"), list) else []
        items = []
        for h in hl_items:
            items.append({"t": "hl", "ch": ch_meta.get(h.get("chapterUid")) or chap_meta.get(h.get("chapterUid"), ""),
                          "text": h.get("markText", ""), "date": fmt_date(h.get("createTime"))})
        for t in th:
            r = t.get("review") or {}
            body = r.get("abstract") or strip_tags(r.get("htmlContent"))
            items.append({"t": "th", "ch": ch_meta.get(t.get("chapterUid")) or chap_meta.get(t.get("chapterUid"), ""),
                          "text": body, "date": fmt_date(r.get("createTime"))})
        rp = nb.get("readingProgress")
        prog = rp.get("percent") if isinstance(rp, dict) else (rp if isinstance(rp, (int, float)) else None)
        per_book.append({
            "title": meta.get("title", "?"), "author": meta.get("author", ""),
            "deepLink": meta.get("deepLink", ""), "hl": len(hl_items), "th": len(th),
            "progress": prog, "lastTs": last_ts,
            "lastDate": fmt_date(last_ts) if last_ts else "",
            "items": items,
        })
    # 只保留真正有划线或想法的书（noteCount 可能含空笔记本）
    per_book = [b for b in per_book if b["hl"] + b["th"] > 0]
    per_book.sort(key=lambda b: -b["lastTs"])  # 最近读的排最前
    total_hl = sum(b["hl"] for b in per_book)
    total_th = sum(b["th"] for b in per_book)

    rd = stats.get("overall") or {}
    heat = sorted((int(k), int(v or 0)) for k, v in (rd.get("readTimes") or {}).items())
    max_heat = max([v for _, v in heat], default=1) or 1

    kpis = "".join(
        f'<div class="kpi"><b>{v}</b><span>{label}</span></div>' for v, label in [
            (len(books), "书架藏书"), (len(nb_list), "有笔记的书"),
            (total_hl, "划线"), (total_th, "想法"),
            (fmt_time(rd.get("totalReadTime")), "累计阅读"),
        ])
    cells = "".join(
        f'<div class="hm-col"><div class="cell l{0 if v == 0 else min(4, v * 4 // max_heat + 1)}" title="{fmt_date(k)}：{fmt_time(v)}"></div><span>{time.strftime("%y-%m", time.localtime(k))}</span></div>'
        for k, v in heat)

    # ---- 书卡 ----
    cards = []
    for b in per_book:
        items_html = "".join(
            f'<div class="mark {"highlight" if it["t"] == "hl" else "thought"}">'
            f'<div class="mm">{"🟡 划线" if it["t"] == "hl" else "💭 想法"} · {esc(it["ch"])}{(" · " + it["date"]) if it["date"] else ""}</div>'
            f'<div class="mt">{esc(it["text"])}</div>'
            f'<div class="ai">🔵 <i>助手批注区</i></div></div>'
            for it in b["items"]) or '<div class="empty">无笔记</div>'
        prog = (f'<div class="prog"><div class="pb" style="width:{min(100, b["progress"])}%"></div>'
                f'<b>{b["progress"]}%</b></div>') if b.get("progress") is not None else ""
        recent = f'<span class="rd">🕒 {b["lastDate"]}</span>' if b.get("lastDate") else ""
        link = f'<a class="open" href="{esc(b["deepLink"])}" target="_blank">阅读 ↗</a>' if b.get("deepLink") else ""
        stats_line = f'<div class="bs">🟡 {b["hl"]} · 💭 {b["th"]}{prog}{recent}{link}</div>'
        cards.append(
            f'<div class="book-card"><div class="bh" onclick="tg(this)">'
            f'<div class="bt">{esc(b["title"])}<span class="ba">{esc(b["author"])}</span></div>'
            f'{stats_line}'
            f'</div><div class="bb" hidden>{items_html}</div></div>')
    cards_html = "".join(cards)

    # ---- 共读库（EPUB 拆分结果，可选） ----
    coread = load_coread(data_dir)
    cr_html = coread_html(coread)
    cr_js = COREAD_JS if coread else ""
    cr_init = json.dumps({s["id"]: {"user": s["user"], "ai": s["ai"]} for s in coread["segments"]} if coread else {},
                         ensure_ascii=False)
    # 共读页顶部显示当前共读的书 + 批注应保存到哪个文件
    cr_book = ""
    if coread:
        book_name = coread["meta"].get("book", "?")
        notes_path = coread["meta"].get("_dir", "").replace("\\", "/").split("/")[-1]
        cr_book = (f'<div class="cr-book">当前共读：<b>{esc(book_name)}</b>'
                   f'<span class="cr-book-sub">批注将保存在 {esc(notes_path)}/coread-notes.json</span></div>')

    # Tab 导航：共读库存在时共读为默认页
    tabs = f'''<div class="tabs">
  <button class="tab{' off' if not coread else ''}" id="tab-coread" onclick="go('coread')">📖 共读</button>
  <button class="tab off" id="tab-shelf" onclick="go('shelf')">📚 书架与笔记</button>
</div>'''
    coread_page = f'<div id="page-coread" class="page"{" hidden" if not coread else ""}>{cr_book}{cr_html}</div>'
    shelf_page = f'''<div id="page-shelf" class="page"{" hidden" if coread else ""}>
<div class="kpis">{kpis}</div>
<div class="panel"><h3>🔥 阅读轨迹</h3><div class="heat">{cells or '<div class="empty">暂无</div>'}</div></div>
<input class="search" placeholder="搜索书名 / 作者 / 划线内容…">
{cards_html}
</div>'''

    html = f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>共读看板</title><style>{CSS}</style></head><body><div class="wrap">
<h1>📖 共读看板</h1>
<div class="sub">你的划线 🟡 · 想法 💭 · AI 批注 🔵 · 生成于 {time.strftime("%Y-%m-%d")}</div>
{tabs}
{coread_page}
{shelf_page}
<footer>微信读书官方 Agent Gateway · 仅存本地 · 双色共读：🟡你 🔵AI</footer>
<script>
var COREAD_NOTES={cr_init};
var cur=null;
function tg(h){{var b=h.nextElementSibling;b.hidden=!b.hidden}}
var sb=document.querySelector('.search');
sb.addEventListener('input',function(){{var q=sb.value.trim().toLowerCase();
document.querySelectorAll('.book-card').forEach(function(c){{
var hit=!q||c.textContent.toLowerCase().includes(q);
c.style.display=hit?'':'none';
if(q&&hit){{c.querySelector('.bb').hidden=false;
c.querySelectorAll('.mark').forEach(function(m){{m.style.display=m.querySelector('.mt').textContent.toLowerCase().includes(q)?'':'none'}})}}
else{{c.querySelectorAll('.mark').forEach(function(m){{m.style.display=''}})}}
}})}});
{cr_js}
function go(w){{
  document.querySelectorAll('.page').forEach(function(p){{p.hidden=true}});
  document.getElementById('page-'+w).hidden=false;
  document.querySelectorAll('.tab').forEach(function(t){{t.classList.remove('off')}});
  document.getElementById('tab-'+w).classList.add('off');
}}
</script>
</div></body></html>'''

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    extra = f" · 共读库 {coread['meta'].get('totalSegments', '?')} 段" if coread else ""
    print(f"✓ {out} ({len(html)//1024} KB) · {len(per_book)} 本书 · {total_hl} 划线 · {total_th} 想法{extra}")

if __name__ == "__main__":
    main()

"""digests/ 의 JSON을 읽어 _site/ 에 GitHub Pages용 웹페이지를 만든다.

- {날짜}-{claude|rss}.html : 날짜별 소식 (카톡 메시지 링크가 여기로 연결됨)
- index.html               : 가장 최근 소식
- archive.html             : 지난 소식 목록 + 전체 검색
카카오 메시지 링크는 '등록한 도메인'만 열리므로 기사 원문 링크는 모두 이 페이지에 모은다.
"""
import glob
import html
import json
import os
from datetime import date as Date

from common import site_url, ROOT, SECTION_TITLES, SOURCE_LABELS, load_json, page_name

OUT = os.path.join(ROOT, "_site")
ASSETS = os.path.join(ROOT, "site_assets")
SITE_NAME = (os.environ.get("SITE_NAME") or "").strip() or "레고 데일리"
KAKAO_CHANNEL_URL = (os.environ.get("KAKAO_CHANNEL_URL") or "").strip()
INSTAGRAM_URL = (os.environ.get("INSTAGRAM_URL") or "").strip()
# 웹푸시·방문기록 설정 (공개해도 되는 값만). 없으면 알림 버튼이 숨겨짐
CONFIG = {
    "sbUrl": os.environ.get("SUPABASE_URL", "").strip().rstrip("/"),
    "sbKey": os.environ.get("SUPABASE_ANON_KEY", "").strip(),
    "vapid": os.environ.get("VAPID_PUBLIC_KEY", "").strip(),
}
DISPLAY_ORDER = ["kr_deal", "new_release", "kr_news", "global_news"]
WEEK = "월화수목금토일"
e = html.escape

CSS = """
:root{--bg:#f6f5f1;--surface:#fff;--fg:#1c1b19;--muted:#6d6b64;--line:#e5e2d9;--accent:#C2410C;
--accent-soft:#FFEADF;--yellow:#ffcf00;--chip:#f0eee7;--shadow:0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.04)}
@media (prefers-color-scheme:dark){:root{--bg:#121211;--surface:#1c1c1a;--fg:#ecebe6;--muted:#a09e96;
--line:#2f2e2b;--accent:#FF7A3D;--accent-soft:#3A2116;--chip:#2a2927;--shadow:none}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);-webkit-font-smoothing:antialiased;
font:16px/1.6 Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
a{color:inherit}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.top-in{max-width:760px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:12px}
.logo{text-decoration:none;display:flex;align-items:center;gap:8px;font-family:'Black Han Sans',Pretendard,sans-serif;font-size:1.25rem;font-weight:400;letter-spacing:0}
.logo img{width:28px;height:28px;display:block}
.top nav{margin-left:auto;display:flex;gap:4px}
.top nav a{text-decoration:none;font-size:.9rem;color:var(--muted);padding:6px 10px;border-radius:8px}
.top nav a:hover,.top nav a.on{color:var(--fg);background:var(--chip)}
main{max-width:760px;margin:0 auto;padding:20px 16px 72px}
.date{color:var(--muted);font-size:.92rem;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{font-size:.75rem;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--chip);color:var(--muted)}
.pill.ai{background:var(--accent-soft);color:var(--accent)}
h1{font-size:1.55rem;line-height:1.35;letter-spacing:-.02em;margin:.35em 0 .2em;word-break:keep-all}
.chips{position:sticky;top:53px;z-index:4;background:var(--bg);display:flex;gap:6px;overflow-x:auto;
padding:10px 0;margin:8px 0 4px;scrollbar-width:none}
.chips a{flex:none;text-decoration:none;font-size:.88rem;padding:6px 12px;border-radius:999px;
background:var(--surface);border:1px solid var(--line)}
.chips b{color:var(--accent);margin-left:2px}
h2{font-size:1.1rem;margin:28px 0 10px;display:flex;align-items:center;gap:8px;scroll-margin-top:110px}
h2 small{font-weight:500;color:var(--muted);font-size:.85rem}
.card{display:flex;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:14px;
padding:14px;margin:10px 0;box-shadow:var(--shadow);scroll-margin-top:110px;transition:border-color .2s}
.card:target{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.thumb{flex:none;width:92px;height:92px;border-radius:10px;object-fit:cover;background:var(--chip)}
.body{min-width:0;flex:1}
.badges{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:4px}
.b{font-size:.72rem;font-weight:700;padding:1px 7px;border-radius:5px;background:var(--chip);color:var(--muted)}
.b.hot{background:var(--accent);color:#fff}.b.rumor{background:#ede7fb;color:#5b3fc4}
.b.off{background:var(--yellow);color:#222}
@media (prefers-color-scheme:dark){.b.rumor{background:#2c2540;color:#b9a6ff}}
.card .t{font-weight:700;text-decoration:none;line-height:1.45;word-break:keep-all;display:block}
.card .t:hover{text-decoration:underline}
.card p{margin:4px 0 0;color:var(--muted);font-size:.93rem;word-break:keep-all}
.meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;font-size:.8rem}
.meta span{background:var(--chip);padding:2px 8px;border-radius:6px}
.meta .src{background:none;color:var(--muted);padding:2px 0}
.empty{color:var(--muted);font-size:.92rem;padding:14px;border:1px dashed var(--line);border-radius:12px}
.cal{background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.cal div{display:grid;grid-template-columns:88px 1fr auto;gap:10px;padding:10px 14px;border-top:1px solid var(--line);font-size:.92rem}
.cal div:first-child{border-top:0}.cal .d{color:var(--accent);font-weight:700;font-variant-numeric:tabular-nums}
.cal .n small{display:block;color:var(--muted);font-size:.8rem}.cal .p{color:var(--muted);text-align:right;font-size:.85rem}
.pager{display:flex;justify-content:space-between;margin-top:36px;gap:8px}
.pager a{text-decoration:none;padding:10px 14px;border-radius:10px;background:var(--surface);border:1px solid var(--line);font-size:.9rem}
footer{color:var(--muted);font-size:.8rem;text-align:center;margin-top:40px}
.search{width:100%;font:inherit;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface);color:var(--fg)}
.day{display:block;text-decoration:none;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0}
.day b{display:block}.day span{color:var(--muted);font-size:.88rem}
.hit{padding:10px 0;border-bottom:1px solid var(--line)}.hit a{font-weight:600;text-decoration:none}.hit small{color:var(--muted);display:block}
.push{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:14px 0;box-shadow:var(--shadow)}
.push b{display:block;margin-bottom:2px}.push p{margin:4px 0;color:var(--muted);font-size:.92rem;word-break:keep-all}
.push .warn{color:var(--accent)}.push .hint,.push .note{font-size:.85rem}
.push .topics{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}
.push .topics label{font-size:.88rem;background:var(--chip);padding:6px 10px;border-radius:999px;cursor:pointer;user-select:none}
.push .topics input{accent-color:var(--accent);margin:0 4px 0 0;vertical-align:-2px}
.push button{font:inherit;font-weight:700;border:0;border-radius:10px;padding:11px 16px;cursor:pointer;background:var(--accent);color:#fff;width:100%;margin-top:6px}
.push button.off{background:var(--chip);color:var(--fg)}.push button:disabled{opacity:.6}
.push .row{display:flex;gap:8px}.push details summary{cursor:pointer;color:var(--muted);font-size:.9rem;margin-top:6px}
.push .steps{margin:8px 0 0;padding-left:1.2em;font-size:.92rem}.push .steps li{margin:3px 0}
.follow{display:flex;gap:8px;flex-wrap:wrap;margin:-4px 0 6px}
.follow a{flex:1 1 160px;text-align:center;text-decoration:none;font-weight:700;font-size:.92rem;padding:11px 14px;border-radius:10px;border:1px solid var(--line);background:var(--surface)}
.follow a.kakao{background:#FEE500;color:#191600;border-color:#FEE500}
@media (max-width:520px){h1{font-size:1.3rem}.thumb{width:72px;height:72px}.cal div{grid-template-columns:74px 1fr}.cal .p{grid-column:2;text-align:left}}
"""

FONT = ("<link rel='stylesheet' href='https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
        "dist/web/variable/pretendardvariable-dynamic-subset.min.css'>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap'>")


def page(title, body, active=""):
    nav = (f"<a href='index.html' class='{'on' if active == 'today' else ''}'>오늘</a>"
           f"<a href='archive.html' class='{'on' if active == 'archive' else ''}'>지난 소식</a>")
    cfg = json.dumps(CONFIG).replace("</", "<\\/")
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            f"<title>{e(title)}</title>"
            f"<meta name='theme-color' content='#FF6B2C'>"
            f"<link rel='manifest' href='manifest.webmanifest'>"
            f"<link rel='icon' href='favicon.svg' type='image/svg+xml'><link rel='icon' href='favicon-32.png' sizes='32x32'>"
            f"<link rel='apple-touch-icon' href='apple-touch-icon.png'>"
            f"<meta property='og:image' content='{site_url()}/og-image.png'>"
            f"<meta name='apple-mobile-web-app-capable' content='yes'>"
            f"<meta name='apple-mobile-web-app-title' content='{e(SITE_NAME)}'>"
            f"<meta property='og:title' content='{e(title)}'>"
            f"<meta property='og:description' content='매일 12시, 국내 레고 할인·전 세계 신제품 소식'>"
            f"{FONT}<style>{CSS}</style></head><body>"
            f"<header class='top'><div class='top-in'><a class='logo' href='index.html'>"
            f"<img src='favicon.svg' alt=''>{e(SITE_NAME)}</a><nav>{nav}</nav></div></header>"
            f"<main>{body}<footer>매일 낮 12시 업데이트 · 기사 저작권은 각 원문 매체에 있습니다</footer></main>"
            f"<script>window.LD_CONFIG={cfg}</script><script src='push.js' defer></script>"
            f"</body></html>")


def follow_links():
    links = []
    if KAKAO_CHANNEL_URL:
        links.append(f"<a class='kakao' href='{e(KAKAO_CHANNEL_URL)}' target='_blank' rel='noopener'>카카오톡 채널 추가</a>")
    if INSTAGRAM_URL:
        links.append(f"<a href='{e(INSTAGRAM_URL)}' target='_blank' rel='noopener'>인스타그램 팔로우</a>")
    return f"<div class='follow'>{''.join(links)}</div>" if links else ""


def kdate(s):
    try:
        y, m, d = map(int, s.split("-"))
        return f"{y}년 {m}월 {d}일 ({WEEK[Date(y, m, d).weekday()]})"
    except Exception:
        return s


def cal_date(s):
    s = str(s or "")
    try:
        y, m, d = map(int, s.split("-"))
        return f"{m}/{d} ({WEEK[Date(y, m, d).weekday()]})"
    except Exception:
        parts = s.split("-")
        return f"{int(parts[1])}월 중" if len(parts) == 2 and parts[1].isdigit() else s


def badges(it):
    out = []
    if int(it.get("importance", 0) or 0) >= 3:
        out.append("<span class='b hot'>핵심</span>")
    tag = it.get("tag")
    if tag:
        cls = "rumor" if tag == "루머" else "off" if tag in ("공식", "공식몰") else ""
        out.append(f"<span class='b {cls}'>{e(tag)}</span>")
    return f"<div class='badges'>{''.join(out)}</div>" if out else ""


def meta(it):
    keys = ["discount", "period", "set", "theme", "price", "release"]
    chips = [f"<span>{e(str(it[k]))}</span>" for k in keys if it.get(k)]
    if it.get("source"):
        chips.append(f"<span class='src'>{e(it['source'])}</span>")
    return f"<div class='meta'>{''.join(chips)}</div>" if chips else ""


def card(key, i, it):
    img = (f"<img class='thumb' src='{e(it['image'])}' alt='' loading='lazy' "
           f"referrerpolicy='no-referrer' onerror=\"this.remove()\">") if it.get("image") else ""
    return (f"<article class='card' id='{key}-{i}'>{img}<div class='body'>{badges(it)}"
            f"<a class='t' href='{e(it['url'])}' target='_blank' rel='noopener'>{e(it['title'])}</a>"
            + (f"<p>{e(it['summary'])}</p>" if it.get("summary") else "")
            + meta(it) + "</div></article>")


def render_digest(d, prev_d=None, next_d=None, active=""):
    by_key = {s["key"]: s.get("items", []) for s in d.get("sections", [])}
    label = SOURCE_LABELS.get(d["source"], d["source"])
    parts = [f"<div class='date'>{e(kdate(d['date']))}"
             f"<span class='pill {'ai' if d['source'] == 'claude' else ''}'>{e(label)}</span></div>",
             f"<h1>{e(d.get('headline') or '오늘의 레고 소식')}</h1>",
             "<section id='push' class='push' hidden></section>",
             follow_links()]
    chips = [f"<a href='#{k}'>{e(SECTION_TITLES[k])}<b>{len(by_key.get(k, []))}</b></a>" for k in DISPLAY_ORDER]
    if d.get("calendar"):
        chips.append("<a href='#calendar'>🗓️ 출시 캘린더</a>")
    parts.append(f"<nav class='chips'>{''.join(chips)}</nav>")
    for key in DISPLAY_ORDER:
        items = by_key.get(key, [])
        parts.append(f"<h2 id='{key}'>{e(SECTION_TITLES[key])} <small>{len(items)}건</small></h2>")
        if not items:
            parts.append("<div class='empty'>오늘은 새 소식이 없어요.</div>")
        parts += [card(key, i, it) for i, it in enumerate(items)]
    if d.get("calendar"):
        rows = "".join(
            f"<div><span class='d'>{e(cal_date(c.get('date')))}</span>"
            f"<span class='n'>{e(c.get('name', ''))}<small>{e(' · '.join(x for x in [c.get('set'), c.get('theme'), c.get('region')] if x))}</small></span>"
            f"<span class='p'>{e(str(c.get('price', '')))}</span></div>" for c in d["calendar"])
        parts.append(f"<h2 id='calendar'>🗓️ 출시 캘린더 <small>앞으로 60일</small></h2><div class='cal'>{rows}</div>")
    nav = "<div class='pager'>"
    nav += f"<a href='{page_name(prev_d)}'>← {prev_d['date'][5:]}</a>" if prev_d else "<span></span>"
    nav += f"<a href='{page_name(next_d)}'>{next_d['date'][5:]} →</a>" if next_d else "<span></span>"
    parts.append(nav + "</div>")
    return page(f"{SITE_NAME} {d['date']}", "".join(parts), active)


def render_archive(main_digests):
    rows = []
    for d in main_digests:
        n = sum(len(s.get("items", [])) for s in d.get("sections", []))
        rows.append(f"<a class='day' href='{page_name(d)}'><b>{e(kdate(d['date']))}</b>"
                    f"<span>{e(d.get('headline') or '')} · {n}건</span></a>")
    index = [{"d": d["date"], "p": page_name(d), "k": s["key"], "i": i,
              "t": it["title"], "s": it.get("summary", "")}
             for d in main_digests for s in d.get("sections", []) for i, it in enumerate(s.get("items", []))]
    data = json.dumps(index, ensure_ascii=False).replace("</", "<\\/")
    body = (
        "<h1>지난 소식</h1>"
        "<input class='search' id='q' placeholder='세트 이름·번호·행사로 검색'>"
        "<div id='hits'></div><div id='days'>" + "".join(rows) + "</div>"
        f"<script>const D={data};const q=document.getElementById('q'),h=document.getElementById('hits'),"
        "dy=document.getElementById('days');const esc=s=>s.replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();dy.hidden=!!v;"
        "if(!v){h.innerHTML='';return}const r=D.filter(x=>(x.t+' '+x.s).toLowerCase().includes(v)).slice(0,100);"
        "h.innerHTML=r.length?r.map(x=>`<div class='hit'><a href='${x.p}#${x.k}-${x.i}'>${esc(x.t)}</a><small>${x.d} · ${esc(x.s)}</small></div>`).join('')"
        ":'<p class=\"empty\">검색 결과가 없어요.</p>'});</script>")
    return page(f"{SITE_NAME} · 지난 소식", body, "archive")


def write_assets():
    import shutil
    for name in os.listdir(ASSETS):
        shutil.copy(os.path.join(ASSETS, name), os.path.join(OUT, name))
    manifest = {
        "name": SITE_NAME, "short_name": SITE_NAME, "lang": "ko",
        "start_url": "./index.html?src=pwa", "scope": "./", "display": "standalone",
        "background_color": "#1B1B1F", "theme_color": "#FF6B2C",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }
    with open(os.path.join(OUT, "manifest.webmanifest"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)


def main():
    os.makedirs(OUT, exist_ok=True)
    write_assets()
    all_d = [d for p in glob.glob(os.path.join(ROOT, "digests", "*", "*.json"))
             if (d := load_json(p)) and d.get("date")]
    # 날짜마다 대표 1개: Claude 요약이 있으면 그것, 없으면 자동 수집본
    best = {}
    for d in all_d:
        if d["date"] not in best or d["source"] == "claude":
            best[d["date"]] = d
    main_list = sorted(best.values(), key=lambda d: d["date"])
    pos = {id(d): i for i, d in enumerate(main_list)}
    for d in all_d:
        i = pos.get(id(d))
        prev_d = main_list[i - 1] if i is not None and i > 0 else None
        next_d = main_list[i + 1] if i is not None and i + 1 < len(main_list) else None
        with open(os.path.join(OUT, page_name(d)), "w", encoding="utf-8") as f:
            f.write(render_digest(d, prev_d, next_d))
    if main_list:
        latest = main_list[-1]
        prev_d = main_list[-2] if len(main_list) > 1 else None
        with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
            f.write(render_digest(latest, prev_d, None, active="today"))
    with open(os.path.join(OUT, "archive.html"), "w", encoding="utf-8") as f:
        f.write(render_archive(list(reversed(main_list))))
    print(f"built {len(all_d)} pages (+index, archive) into {OUT}")


if __name__ == "__main__":
    main()

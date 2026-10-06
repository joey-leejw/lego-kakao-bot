"""digests/ 의 JSON을 읽어 _site/ 에 GitHub Pages용 웹페이지를 만든다.

- {날짜}-{claude|rss}.html : 날짜별 소식
- index.html               : 가장 최근 소식
- deals.html / releases.html : 진행 중인 할인 / 신제품 전체 (기간이 끝날 때까지 모아 보여줌)
- n-{날짜}-{id}.html       : 국내·해외 소식을 브릭소리가 요약·번역한 기사 (출처 표시)
- archive.html             : 지난 소식 목록 + 전체 검색
카카오 메시지 링크는 '등록한 도메인'만 열리므로 기사 원문 링크는 모두 이 페이지에 모은다.
"""
import glob
import html
import json
import os
import re
from datetime import date as Date, timedelta

from common import (site_url, ROOT, SECTION_TITLES, load_json, page_name, item_id, item_link,
                    news_page, NEWS_KEYS, POOL_PAGES, POOL_PREFIX)

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
MAIN_LIMIT = 5          # 첫 화면에 보여줄 할인·신제품 개수
DEAL_DEFAULT_DAYS = 7   # 종료일을 모르는 할인은 처음 소개된 날부터 이 기간 동안 노출
RELEASE_KEEP_DAYS = 14  # 신제품 소식은 소개 후 이 기간 + 출시일까지 노출
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
.top nav a{text-decoration:none;font-size:.9rem;white-space:nowrap;color:var(--muted);padding:6px 10px;border-radius:8px}
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
h1 .d{color:var(--accent);margin-right:.25em}
.lead{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:10px;
padding:10px 14px;margin:10px 0 14px;font-weight:600;word-break:keep-all}
h2 a{text-decoration:none}h2 a:hover{text-decoration:underline}
.more{display:block;text-align:center;text-decoration:none;font-weight:700;font-size:.92rem;padding:11px;border-radius:10px;
background:var(--accent-soft);color:var(--accent);margin:8px 0 0}
.b.new{background:#1f9d55;color:#fff}.b.soon{background:var(--accent);color:#fff}
.sub{color:var(--muted);margin:-2px 0 12px;font-size:.92rem;word-break:keep-all}
.daygrp{font-size:.85rem;color:var(--muted);font-weight:700;margin:22px 0 4px}
.crumb{font-size:.88rem;color:var(--muted);margin:2px 0 6px}.crumb a{text-decoration:none;color:var(--accent);font-weight:600}
.nw{white-space:nowrap}.byline{color:var(--muted);font-size:.88rem;margin:4px 0 14px}.byline b{color:var(--fg)}
.hero{margin:0 0 16px}.hero img{width:100%;max-height:380px;object-fit:cover;border-radius:14px;background:var(--chip);display:block}
.hero figcaption{font-size:.78rem;color:var(--muted);margin-top:4px}
.points{background:var(--accent-soft);border-radius:12px;padding:12px 16px;margin:0 0 18px}
.points b{color:var(--accent)}.points ul{margin:6px 0 0;padding-left:1.15em}.points li{margin:3px 0;word-break:keep-all}
.article p{margin:0 0 1em;font-size:1.02rem;line-height:1.8;word-break:keep-all}
.source{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin:22px 0}
.source dl{display:grid;grid-template-columns:72px 1fr;gap:4px 10px;margin:8px 0 12px;font-size:.9rem}
.source dt{color:var(--muted)}.source dd{margin:0;word-break:break-word}
.source .orig{display:inline-block;text-decoration:none;font-weight:700;padding:9px 14px;border-radius:10px;border:1px solid var(--line)}
.source .note{color:var(--muted);font-size:.82rem;margin:10px 0 0;word-break:keep-all}
.rel a{display:block;text-decoration:none;padding:10px 0;border-bottom:1px solid var(--line);font-weight:600;word-break:keep-all}
.rel small{display:block;color:var(--muted);font-weight:400}
@media (max-width:520px){.top nav a{padding:6px 6px;font-size:.85rem}.top-in{gap:6px}}
@media (max-width:520px){h1{font-size:1.3rem}.thumb{width:72px;height:72px}.cal div{grid-template-columns:74px 1fr}.cal .p{grid-column:2;text-align:left}}
"""

FONT = ("<link rel='stylesheet' href='https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
        "dist/web/variable/pretendardvariable-dynamic-subset.min.css'>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap'>")




def page(title, body, active="", desc=None, image=None):
    links = [("index.html", "오늘", "today"), ("deals.html", "할인", "deals"),
             ("releases.html", "신제품", "releases"), ("archive.html", "지난 소식", "archive")]
    nav = "".join(f"<a href='{h}' class='{'on' if active == k else ''}'>{t}</a>" for h, t, k in links)
    cfg = json.dumps(CONFIG).replace("</", "<\\/")
    desc = desc or "매일 12시, 국내 레고 할인·전 세계 신제품 소식"
    og_img = image or f"{site_url()}/og-image.png"
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
            f"<title>{e(title)}</title><meta name='description' content='{e(desc)}'>"
            f"<meta name='theme-color' content='#FF6B2C'>"
            f"<link rel='manifest' href='manifest.webmanifest'>"
            f"<link rel='icon' href='favicon.svg' type='image/svg+xml'><link rel='icon' href='favicon-32.png' sizes='32x32'>"
            f"<link rel='apple-touch-icon' href='apple-touch-icon.png'>"
            f"<meta name='apple-mobile-web-app-capable' content='yes'>"
            f"<meta name='apple-mobile-web-app-title' content='{e(SITE_NAME)}'>"
            f"<meta property='og:site_name' content='{e(SITE_NAME)}'>"
            f"<meta property='og:title' content='{e(title)}'>"
            f"<meta property='og:description' content='{e(desc)}'>"
            f"<meta property='og:image' content='{e(og_img)}'>"
            f"{FONT}<style>{CSS}</style></head><body>"
            f"<header class='top'><div class='top-in'><a class='logo' href='index.html'>"
            f"<img src='favicon.svg' alt=''><span>{e(SITE_NAME)}</span></a><nav>{nav}</nav></div></header>"
            f"<main>{body}<footer>매일 낮 12시 업데이트 · 소식마다 출처를 밝히며, 원문 저작권은 각 매체에 있습니다</footer></main>"
            f"<script>window.LD_CONFIG={cfg}</script><script src='push.js' defer></script>"
            f"</body></html>")


def follow_links():
    links = []
    if KAKAO_CHANNEL_URL:
        links.append(f"<a class='kakao' href='{e(KAKAO_CHANNEL_URL)}' target='_blank' rel='noopener'>카카오톡 채널 추가</a>")
    if INSTAGRAM_URL:
        links.append(f"<a href='{e(INSTAGRAM_URL)}' target='_blank' rel='noopener'>인스타그램 팔로우</a>")
    return f"<div class='follow'>{''.join(links)}</div>" if links else ""


# ---------- 날짜 ----------
def to_date(s):
    try:
        y, m, d = map(int, str(s).split("-"))
        return Date(y, m, d)
    except Exception:
        return None


def kdate(s, year=True):
    dt = to_date(s)
    if not dt:
        return str(s)
    head = f"{dt.year}년 " if year else ""
    return f"{head}{dt.month}월 {dt.day}일 ({WEEK[dt.weekday()]})"


def dot(s):
    return str(s).replace("-", ".")


def md(dt):
    return f"{dt.month}/{dt.day}"


def cal_date(s):
    s = str(s or "")
    dt = to_date(s)
    if dt:
        return f"{md(dt)} ({WEEK[dt.weekday()]})"
    parts = s.split("-")
    return f"{int(parts[1])}월 중" if len(parts) == 2 and parts[1].isdigit() else s


def loose_date(s, as_of, month_end=False):
    """'2026-10-12', '2026-11', '10/12', '10.12', '10월 12일' → date. 연도가 없으면 as_of 기준으로 추정."""
    s = str(s or "").strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return to_date(s)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if not 1 <= mo <= 12:
            return None
        if not month_end:
            return Date(y, mo, 1)
        nxt = Date(y + (mo == 12), mo % 12 + 1, 1)
        return nxt - timedelta(days=1)
    pairs = re.findall(r"(\d{1,2})\s*(?:/|\.|월)\s*(\d{1,2})", s)
    if not pairs:
        return None
    mo, d = map(int, pairs[-1])  # 기간이면 마지막 날짜 = 종료일
    try:
        dt = Date(as_of.year, mo, d)
    except ValueError:
        return None
    if (as_of - dt).days > 180:  # 12월에 1월 행사 → 다음 해
        dt = Date(as_of.year + 1, mo, d)
    return dt


def deal_end(it, as_of):
    return loose_date(it.get("end"), as_of) or loose_date(it.get("period"), as_of)


def release_day(it, as_of):
    return (loose_date(it.get("release_date"), as_of, month_end=True)
            or loose_date(it.get("release"), as_of, month_end=True))


# ---------- 할인·신제품: 기간 동안 모아 보여주기 ----------
def build_pool(key, digests, as_of_str):
    """as_of 날짜까지의 다이제스트에서 key 섹션 항목을 모아, 아직 유효한 것만 최신순으로."""
    as_of = to_date(as_of_str)
    seen = {}
    for d in digests:
        if d["date"] > as_of_str:
            continue
        for s in d.get("sections", []):
            if s.get("key") != key:
                continue
            for i, it in enumerate(s.get("items", [])):
                iid = item_id(it)
                if iid in seen:  # 같은 소식이 다시 나오면 내용만 최신으로
                    seen[iid]["it"] = it
                else:
                    seen[iid] = {"it": it, "first": d["date"], "order": i}
    out = []
    for iid, v in seen.items():
        it, first = v["it"], to_date(v["first"])
        age = (as_of - first).days
        if key == "kr_deal":
            end = deal_end(it, as_of)
            alive = end >= as_of if end else age <= DEAL_DEFAULT_DAYS
            out.append({**v, "id": iid, "end": end, "alive": alive})
        else:
            rd = release_day(it, as_of)
            alive = age <= RELEASE_KEEP_DAYS or (rd is not None and rd >= as_of)
            out.append({**v, "id": iid, "rd": rd, "alive": alive})
    out = [x for x in out if x["alive"]]
    out.sort(key=lambda x: (x["first"], int(x["it"].get("importance", 1) or 1), -x["order"]), reverse=True)
    return out


def pool_badges(key, x, as_of):
    out = []
    if x["first"] == as_of.isoformat():
        out.append("<span class='b new'>NEW</span>")
    if key == "kr_deal" and x.get("end"):
        left = (x["end"] - as_of).days
        if left == 0:
            out.append("<span class='b soon'>오늘 마감</span>")
        elif left <= 3:
            out.append(f"<span class='b soon'>D-{left} 마감</span>")
        else:
            out.append(f"<span class='b'>~{md(x['end'])}까지</span>")
    if key == "new_release" and x.get("rd") and x["rd"] >= as_of:
        left = (x["rd"] - as_of).days
        out.append(f"<span class='b'>{'오늘 출시' if left == 0 else f'출시 D-{left}'}</span>")
    return out


# ---------- 카드 ----------
def badges(it, extra=()):
    out = list(extra)
    if int(it.get("importance", 0) or 0) >= 3:
        out.append("<span class='b hot'>핵심</span>")
    tag = it.get("tag")
    if tag:
        cls = "rumor" if tag == "루머" else "off" if tag in ("공식", "공식몰") else ""
        out.append(f"<span class='b {cls}'>{e(tag)}</span>")
    return f"<div class='badges'>{''.join(out)}</div>" if out else ""


def meta(it, keys=("discount", "period", "set", "theme", "price", "release")):
    chips = [f"<span>{e(str(it[k]))}</span>" for k in keys if it.get(k)]
    if it.get("source"):
        chips.append(f"<span class='src'>출처 · {e(it['source'])}</span>")
    return f"<div class='meta'>{''.join(chips)}</div>" if chips else ""


def card(anchor, it, href, external=True, extra=(), meta_keys=None):
    img = (f"<img class='thumb' src='{e(it['image'])}' alt='' loading='lazy' "
           f"referrerpolicy='no-referrer' onerror=\"this.remove()\">") if it.get("image") else ""
    tgt = " target='_blank' rel='noopener'" if external else ""
    m = meta(it) if meta_keys is None else meta(it, meta_keys)
    return (f"<article class='card' id='{anchor}'>{img}<div class='body'>{badges(it, extra)}"
            f"<a class='t' href='{e(href)}'{tgt}>{e(it['title'])}</a>"
            + (f"<p>{e(it['summary'])}</p>" if it.get("summary") else "")
            + m + "</div></article>")


def pool_card(key, x, as_of):
    return card(f"{POOL_PREFIX[key]}-{x['id']}", x["it"], x["it"]["url"], True, pool_badges(key, x, as_of))


def news_card(d, key, it):
    return card(f"n-{item_id(it)}", it, news_page(d["date"], it), False, (), meta_keys=())


# ---------- 날짜별 페이지 ----------
def render_digest(d, pools, prev_d=None, next_d=None, active=""):
    as_of = to_date(d["date"])
    by_key = {s["key"]: s.get("items", []) for s in d.get("sections", [])}
    parts = [f"<h1><span class='d'>{e(kdate(d['date'], year=False))}</span>오늘의 레고 소식</h1>"]
    if d.get("headline"):
        parts.append(f"<p class='lead'>{e(d['headline'])}</p>")
    parts += ["<section id='push' class='push' hidden></section>", follow_links()]

    def count(k):
        return len(pools[k]) if k in POOL_PAGES else len(by_key.get(k, []))

    chips = []
    for k in DISPLAY_ORDER:
        href = POOL_PAGES.get(k, f"#{k}")
        chips.append(f"<a href='{href}'>{e(SECTION_TITLES[k])}<b>{count(k)}</b></a>")
    if d.get("calendar"):
        chips.append("<a href='#calendar'>🗓️ 출시 캘린더</a>")
    parts.append(f"<nav class='chips'>{''.join(chips)}</nav>")

    for key in DISPLAY_ORDER:
        title = e(SECTION_TITLES[key])
        if key in POOL_PAGES:
            pool = pools[key]
            new_n = sum(1 for x in pool if x["first"] == d["date"])
            unit = "진행 중" if key == "kr_deal" else "소식"
            sub = f"{unit} {len(pool)}건" + (f" · 오늘 새로 {new_n}건" if new_n else "")
            parts.append(f"<h2 id='{key}'><a href='{POOL_PAGES[key]}'>{title} ›</a> <small>{sub}</small></h2>")
            if not pool:
                parts.append("<div class='empty'>지금은 진행 중인 소식이 없어요.</div>")
            parts += [pool_card(key, x, as_of) for x in pool[:MAIN_LIMIT]]
            if pool:
                label = "국내 할인" if key == "kr_deal" else "신제품 발매"
                parts.append(f"<a class='more' href='{POOL_PAGES[key]}'>{label} 전체 {len(pool)}건 보기 →</a>")
        else:
            items = by_key.get(key, [])
            parts.append(f"<h2 id='{key}'>{title} <small>{len(items)}건</small></h2>")
            if not items:
                parts.append("<div class='empty'>오늘은 새 소식이 없어요.</div>")
            parts += [news_card(d, key, it) for it in items]

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
    return page(f"{SITE_NAME} · {kdate(d['date'], year=False)} 오늘의 레고 소식", "".join(parts), active,
                desc=d.get("headline") or None)


# ---------- 할인·신제품 전체 페이지 ----------
def render_pool_page(key, pool, as_of_str):
    as_of = to_date(as_of_str)
    if key == "kr_deal":
        title, active = "🏷️ 국내 할인 전체", "deals"
        sub = "지금 진행 중인 할인·프로모션이에요. 행사가 끝나면 자동으로 빠지고, 새 소식이 맨 위에 올라와요."
    else:
        title, active = "🆕 신제품 발매 전체", "releases"
        sub = "전 세계 신제품 소식이에요. 출시일이 지나거나 2주가 지나면 자동으로 빠지고, 새 소식이 맨 위에 올라와요."
    parts = [f"<h1>{title} <small style='font-size:.6em;color:var(--muted)'>{len(pool)}건</small></h1>",
             f"<p class='sub'>{e(sub)}</p>"]
    if not pool:
        parts.append("<div class='empty'>지금은 진행 중인 소식이 없어요.</div>")
    last = None
    for x in pool:
        if x["first"] != last:
            last = x["first"]
            label = "오늘 새로 올라온 소식" if last == as_of_str else f"{kdate(last, year=False)} 소개"
            parts.append(f"<div class='daygrp'>{e(label)}</div>")
        parts.append(pool_card(key, x, as_of))
    return page(f"{SITE_NAME} · {title[2:].strip()}", "".join(parts), active)


# ---------- 국내·해외 소식 기사 페이지 ----------
def render_news(d, key, it, siblings):
    body = it.get("body") or []
    if isinstance(body, str):
        body = [p for p in body.split("\n") if p.strip()]
    auto = not body
    if auto:
        body = [it["summary"]] if it.get("summary") else []
    src = it.get("source") or "원문 매체"
    kind = "번역·요약" if key == "global_news" else "요약"
    sec = SECTION_TITLES[key]
    parts = [f"<nav class='crumb'><a href='{page_name(d)}#{key}'>← {e(kdate(d['date'], year=False))} 소식</a> · {e(sec)}</nav>",
             f"<h1>{e(it['title'])}</h1>",
             f"<div class='byline'><span class='nw'>출처 <b>{e(src)}</b></span>"
             + (f" · <span class='nw'>원문 {e(dot(it['published']))}</span>" if it.get("published") else "")
             + f" · <span class='nw'>{e(SITE_NAME)} 정리 {e(dot(d['date']))}</span></div>"]
    if it.get("image"):
        parts.append(f"<figure class='hero'><img src='{e(it['image'])}' alt='' referrerpolicy='no-referrer' "
                     f"onerror=\"this.parentNode.remove()\"><figcaption>이미지 출처: {e(src)}</figcaption></figure>")
    if it.get("points"):
        lis = "".join(f"<li>{e(p)}</li>" for p in it["points"])
        parts.append(f"<div class='points'><b>핵심 정리</b><ul>{lis}</ul></div>")
    if body:
        parts.append("<div class='article'>" + "".join(f"<p>{e(p)}</p>" for p in body) + "</div>")
    if auto:
        parts.append("<p class='sub'>자동 수집된 소식이라 짧은 소개만 있어요. 자세한 내용은 아래 원문에서 확인해 주세요.</p>")
    rows = [("매체", e(src))]
    if it.get("original_title"):
        rows.append(("원문 제목", e(it["original_title"])))
    if it.get("published"):
        rows.append(("게재일", e(it["published"])))
    rows.append(("원문 주소", f"<span style='color:var(--muted)'>{e(it['url'][:90])}{'…' if len(it['url']) > 90 else ''}</span>"))
    dl = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in rows)
    parts.append(
        f"<aside class='source'><b>출처</b><dl>{dl}</dl>"
        f"<a class='orig' href='{e(it['url'])}' target='_blank' rel='noopener nofollow'>원문 보기 ↗</a>"
        f"<p class='note'>이 글은 {e(SITE_NAME)}가 원문을 읽고 {kind}한 것이에요. 원문 저작권은 {e(src)}에 있으며, "
        f"원문 사이트에는 광고가 있을 수 있어요.</p></aside>")
    others = [(k, x) for k, x in siblings if x is not it]
    if others:
        links = "".join(f"<a href='{news_page(d['date'], x)}'>{e(x['title'])}<small>{e(SECTION_TITLES[k])} · {e(x.get('source', ''))}</small></a>"
                        for k, x in others)
        parts.append(f"<h2>같은 날 다른 소식</h2><div class='rel'>{links}</div>")
    parts.append("<section id='push' class='push' hidden></section>")
    return page(f"{it['title']} · {SITE_NAME}", "".join(parts), "",
                desc=it.get("summary") or None, image=it.get("image"))


def render_archive(main_digests):
    rows = []
    for d in main_digests:
        n = sum(len(s.get("items", [])) for s in d.get("sections", []))
        rows.append(f"<a class='day' href='{page_name(d)}'><b>{e(kdate(d['date']))}</b>"
                    f"<span>{e(d.get('headline') or '')} · {n}건</span></a>")
    index = [{"d": d["date"], "p": item_link(d, s["key"], it),
              "t": it["title"], "s": it.get("summary", "")}
             for d in main_digests for s in d.get("sections", []) for it in s.get("items", [])]
    data = json.dumps(index, ensure_ascii=False).replace("</", "<\\/")
    body = (
        "<h1>지난 소식</h1>"
        "<input class='search' id='q' placeholder='세트 이름·번호·행사로 검색'>"
        "<div id='hits'></div><div id='days'>" + "".join(rows) + "</div>"
        f"<script>const D={data};const q=document.getElementById('q'),h=document.getElementById('hits'),"
        "dy=document.getElementById('days');const esc=s=>s.replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
        "q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();dy.hidden=!!v;"
        "if(!v){h.innerHTML='';return}const r=D.filter(x=>(x.t+' '+x.s).toLowerCase().includes(v)).slice(0,100);"
        "h.innerHTML=r.length?r.map(x=>`<div class='hit'><a href='${x.p}'>${esc(x.t)}</a><small>${x.d} · ${esc(x.s)}</small></div>`).join('')"
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


def write(name, text):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(text)


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
    n_news = 0
    for d in all_d:
        i = pos.get(id(d))
        prev_d = main_list[i - 1] if i is not None and i > 0 else None
        next_d = main_list[i + 1] if i is not None and i + 1 < len(main_list) else None
        pools = {k: build_pool(k, main_list if i is not None else [d], d["date"]) for k in POOL_PAGES}
        write(page_name(d), render_digest(d, pools, prev_d, next_d))
        if i is None:
            continue
        news = [(s["key"], it) for s in d.get("sections", []) if s.get("key") in NEWS_KEYS
                for it in s.get("items", [])]
        for key, it in news:
            write(news_page(d["date"], it), render_news(d, key, it, news))
            n_news += 1
    if main_list:
        latest = main_list[-1]
        pools = {k: build_pool(k, main_list, latest["date"]) for k in POOL_PAGES}
        prev_d = main_list[-2] if len(main_list) > 1 else None
        write("index.html", render_digest(latest, pools, prev_d, None, active="today"))
        for k, fname in POOL_PAGES.items():
            write(fname, render_pool_page(k, pools[k], latest["date"]))
    else:
        from common import today_kst
        for k, fname in POOL_PAGES.items():
            write(fname, render_pool_page(k, [], today_kst()))
    write("archive.html", render_archive(list(reversed(main_list))))
    print(f"built {len(all_d)} day pages, {n_news} news pages (+index, deals, releases, archive) into {OUT}")


if __name__ == "__main__":
    main()

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
:root{--bg:#FBF8F3;--surface:#fff;--fg:#26231F;--muted:#6E675C;--line:#EFE9DF;--accent:#C2410C;
--accent-soft:#FFEADF;--yellow:#ffcf00;--chip:#F3EEE6;--shadow:none;--r:18px;
--deal-bg:#FFE4D3;--deal-fg:#B5400F;--deal-dot:#FFB892;--deal-head:#FFF4EC;
--soon-bg:#FFD9DE;--soon-fg:#A3243B;
--new-bg:#D7F2E3;--new-fg:#1F6B47;--new-dot:#8FD6AE;--new-head:#EEF9F2;
--news-bg:#DCEBFF;--news-fg:#2456A6;--news-dot:#A9C9F5;--news-head:#EEF5FF;
--cal-bg:#E9E1FB;--cal-fg:#5B3FB0;--line-bg:#FFF3C4;--line-fg:#6B5200}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--surface:#1D1C1A;--fg:#EEEBE5;--muted:#A8A196;
--line:#2E2C29;--accent:#FF8A57;--accent-soft:#3A2116;--chip:#2A2826;
--deal-bg:#3A271C;--deal-fg:#FFB892;--deal-dot:#FF9A66;--deal-head:#2A211B;
--soon-bg:#3D2228;--soon-fg:#FFB3BF;
--new-bg:#1E3328;--new-fg:#9FE0BB;--new-dot:#5FBF8A;--new-head:#1B2721;
--news-bg:#1E2B3D;--news-fg:#AACBFA;--news-dot:#6F9FE0;--news-head:#1B222D;
--cal-bg:#2A2340;--cal-fg:#C9B8FA;--line-bg:#3A3320;--line-fg:#F5DE8A}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);-webkit-font-smoothing:antialiased;
font:16px/1.6 Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
a{color:inherit}
.top{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--surface) 92%,transparent);
backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.top-in{max-width:1080px;margin:0 auto;padding:10px 16px;display:flex;align-items:center;gap:12px}
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
.card{display:flex;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:var(--r);
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
.hero-j{background:#1B1B1F;color:#F6F1E7;border-radius:18px;padding:28px 22px;margin:4px 0 18px}
.hero-j h1{color:#F6F1E7;font-family:'Black Han Sans',Pretendard,sans-serif;font-weight:400;font-size:2rem;margin:10px 0 8px}
.hero-j p{color:#C9C2B6;margin:0;word-break:keep-all}.hero-j img{width:52px;height:52px}
.ben{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:0 0 8px}
.ben div{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px}
.ben b{display:block;margin-bottom:2px}.ben span{color:var(--muted);font-size:.9rem;word-break:keep-all}
.faq details{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:8px 0}
.faq summary{cursor:pointer;font-weight:700}.faq p{margin:8px 0 0;color:var(--muted);word-break:keep-all}
.draft{background:#fff;color:#222;border:1px solid var(--line);border-radius:14px;padding:22px 20px;margin:10px 0}
.draft h3{font-size:1.15rem;margin:22px 0 8px}.draft p,.draft li{line-height:1.75}
.copybar{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
.copybar button{font:inherit;font-weight:700;border:0;border-radius:10px;padding:10px 14px;cursor:pointer;background:var(--accent);color:#fff}
.copybar button.sec{background:var(--chip);color:var(--fg)}
.tip{background:var(--accent-soft);border-radius:12px;padding:12px 16px;font-size:.92rem;word-break:keep-all}
.tip ol{margin:6px 0 0;padding-left:1.2em}
main.wide{max-width:1080px}
.bellpill{display:none;align-items:center;gap:5px;font-size:.75rem;font-weight:700;color:var(--new-fg);background:var(--new-bg);
padding:4px 9px;border-radius:999px;text-decoration:none;white-space:nowrap}
.ld-sub .bellpill{display:inline-flex}
.dhead{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin:4px 0 12px}
.dhead h1{margin:0;font-size:1.5rem;font-weight:900;letter-spacing:-.02em}.dhead span{color:var(--muted);font-size:.92rem}
.dash{display:grid;gap:12px}
.dash-main{display:grid;gap:12px;min-width:0}
.dash-side{display:grid;gap:12px;align-content:start}
@media (min-width:960px){.dash{grid-template-columns:minmax(0,1fr) 320px;align-items:start}.dash-side{position:sticky;top:70px}}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media (min-width:640px){.stats{grid-template-columns:repeat(4,minmax(0,1fr))}}
.stat{display:block;text-decoration:none;border-radius:var(--r);padding:14px}
.stat b{display:block;font-size:.82rem}.stat strong{display:block;font-family:'Black Han Sans',Pretendard,sans-serif;font-weight:400;font-size:2.5rem;line-height:1.1;color:var(--fg)}
.stat small{display:block;font-size:.76rem;font-weight:500;opacity:.9}
.s-deal{background:var(--deal-bg);color:var(--deal-fg)}.s-soon{background:var(--soon-bg);color:var(--soon-fg)}
.s-new{background:var(--new-bg);color:var(--new-fg)}.s-news{background:var(--news-bg);color:var(--news-fg)}
.oneline{background:var(--line-bg);border-radius:var(--r);padding:14px 16px}
.oneline b{font-size:.78rem;color:var(--line-fg)}.oneline p{margin:4px 0 0;font-weight:700;line-height:1.5;word-break:keep-all}
.box{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;scroll-margin-top:70px}
.box-h{display:flex;align-items:center;gap:8px;padding:13px 16px 11px;text-decoration:none}
.box-h h2{margin:0;font-size:1.05rem;font-weight:900}.box-h .n{font-size:.85rem;color:var(--muted)}
.box-h .all{margin-left:auto;font-size:.85rem;font-weight:700}
.box-h i{width:10px;height:10px;border-radius:3px;flex:none}
.b-deal .box-h{background:var(--deal-head)}.b-deal .box-h i{background:var(--deal-dot)}.b-deal .all{color:var(--deal-fg)}
.b-new .box-h{background:var(--new-head)}.b-new .box-h i{background:var(--new-dot)}.b-new .all{color:var(--new-fg)}
.b-news .box-h{background:var(--news-head)}.b-news .box-h i{background:var(--news-dot)}
.b-cal .box-h{background:var(--cal-bg)}.b-cal .box-h h2{color:var(--cal-fg)}
.li{display:flex;align-items:center;gap:12px;padding:11px 16px;border-top:1px solid var(--line);text-decoration:none;color:inherit}
.li:hover .rt{text-decoration:underline}
.li .rb{min-width:0;flex:1}.li .rt{display:block;font-size:.93rem;font-weight:700;line-height:1.4;word-break:keep-all}
.li .rm{display:block;font-size:.78rem;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.li .rs{flex:none;font-size:.75rem;color:var(--muted);max-width:80px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{flex:none;min-width:54px;text-align:center;font-size:.75rem;font-weight:700;padding:4px 6px;border-radius:8px}
.t-soon{background:var(--soon-bg);color:var(--soon-fg)}.t-deal{background:var(--deal-bg);color:var(--deal-fg)}
.t-new{background:var(--new-bg);color:var(--new-fg)}.t-kr{background:var(--deal-bg);color:var(--deal-fg)}.t-gl{background:var(--news-bg);color:var(--news-fg)}
.pill-new{flex:none;font-size:.7rem;font-weight:700;color:var(--new-fg);background:var(--new-bg);padding:2px 7px;border-radius:6px}
.th{flex:none;width:52px;height:52px;border-radius:12px;object-fit:cover;background:var(--new-bg)}
.thf{flex:none;width:52px;height:52px;border-radius:12px;background:var(--new-bg);color:var(--new-fg);display:flex;align-items:center;
justify-content:center;font-family:'Black Han Sans',Pretendard,sans-serif;font-size:.8rem;text-align:center;line-height:1.1;overflow:hidden}
.box .empty{border:0;border-top:1px solid var(--line);border-radius:0;padding:12px 16px}
.minis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.mini{display:block;text-decoration:none;border-radius:var(--r);padding:14px;min-width:0}
.mini b{display:block;font-size:.82rem;font-weight:900}.mini strong{font-family:'Black Han Sans',Pretendard,sans-serif;font-weight:400;font-size:1.6rem;color:var(--fg)}
.mini span{display:block;font-size:.85rem;font-weight:700;color:var(--fg);margin-top:4px;line-height:1.4;word-break:keep-all;
overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.mini small{display:block;font-size:.76rem;margin-top:3px;opacity:.9}
.m-cal{background:var(--cal-bg);color:var(--cal-fg)}.m-news{background:var(--news-bg);color:var(--news-fg)}
.calrow{display:grid;grid-template-columns:78px minmax(0,1fr);gap:4px 10px;padding:10px 16px;border-top:1px solid var(--line);font-size:.9rem}
.calrow .d{color:var(--cal-fg);font-weight:700;white-space:nowrap}.calrow>span:nth-child(2){word-break:keep-all;font-weight:600}
.calrow small{display:block;color:var(--muted);font-size:.78rem;font-weight:400}.calrow .p{grid-column:2;color:var(--muted);font-size:.8rem}.calrow .p:empty{display:none}
.dash-side .push{margin:0}.dash-side .follow{margin:0}
.subbar{position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--surface);border-top:1px solid var(--line);
padding:10px 16px calc(10px + env(safe-area-inset-bottom));display:flex;align-items:center;gap:12px}
.subbar p{flex:1;margin:0;font-size:.85rem;line-height:1.4;color:var(--muted)}.subbar p b{color:var(--fg)}
.subbar a{flex:none;text-decoration:none;font-weight:700;font-size:.92rem;padding:11px 16px;border-radius:12px;background:#FF6B2C;color:#1B1B1F}
.ld-sub .subbar{display:none}
@media (min-width:960px){.subbar{display:none}}
@media (max-width:520px){.li .rs{display:none}.li{gap:10px;padding:11px 14px}}
.st-bar{display:flex;align-items:center;gap:8px;margin:0 0 12px}
.st-range{display:flex;gap:4px;background:var(--chip);padding:4px;border-radius:12px}
.st-range button,.st-out{font:inherit;font-size:.88rem;border:0;border-radius:9px;padding:8px 14px;cursor:pointer;background:transparent;color:var(--fg)}
.st-range button.on{background:var(--surface);font-weight:700}.st-out{margin-left:auto;background:var(--chip)}
.st-tiles{margin-bottom:12px}.st-tiles .stat strong{font-size:2rem}
.st-card{margin:0 0 12px}.st-pad{padding:10px 14px 14px}
.st-grid{display:grid;gap:12px}@media (min-width:900px){.st-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.st-grid .st-card{margin:0}}
.st-grid{margin-bottom:12px}
.st-svg{width:100%;height:auto;display:block}.st-svg .grid{stroke:var(--line);stroke-width:1}
.st-svg .ax{fill:var(--muted);font-size:11px}.st-svg .mark{stroke:var(--muted);stroke-dasharray:4 4}
.hb{display:grid;gap:8px;margin:4px 0 10px}.hb-row{display:grid;grid-template-columns:96px minmax(0,1fr) 44px;gap:8px;align-items:center;font-size:.86rem}
.hb-l{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hb-t{height:12px;background:var(--chip);border-radius:6px;overflow:hidden}
.hb-t i{display:block;height:100%;border-radius:6px}.hb-n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700}
.st-table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:8px}.st-table th,.st-table td{padding:6px 4px;border-top:1px solid var(--line);text-align:right}
.st-table th:first-child,.st-table td:first-child{text-align:left}.st-pad details summary{cursor:pointer;color:var(--muted);font-size:.88rem;margin-top:6px}
.st-top{margin:0;padding:6px 16px 12px 36px}.st-top li{padding:7px 0;border-top:1px solid var(--line);font-size:.9rem}.st-top li:first-child{border-top:0}
.st-top a{text-decoration:none;font-weight:600;word-break:break-all}.st-top span{float:right;color:var(--muted);margin-left:8px}
.st-tip{position:fixed;z-index:20;pointer-events:none;background:var(--fg);color:var(--bg);font-size:.8rem;padding:6px 9px;border-radius:8px;white-space:nowrap}
.st-login{padding:20px;max-width:420px;margin:30px auto}.st-login h2{margin:0 0 6px}.st-login p{color:var(--muted);font-size:.92rem}
.st-login label{display:block;font-size:.85rem;font-weight:700;margin:12px 0 4px}
.st-login input{width:100%;font:inherit;padding:12px;border-radius:10px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
.st-login button{width:100%;font:inherit;font-weight:700;border:0;border-radius:10px;padding:12px;margin-top:10px;background:#FF6B2C;color:#1B1B1F;cursor:pointer}
.st-msg{min-height:1.2em}.st-sub{margin:4px 0 6px;font-size:.8rem;font-weight:700;color:var(--muted)}.st-note{color:var(--muted);font-size:.8rem}
@media (max-width:520px){h1{font-size:1.3rem}.thumb{width:72px;height:72px}.cal div{grid-template-columns:74px 1fr}.cal .p{grid-column:2;text-align:left}}
"""

FONT = ("<link rel='stylesheet' href='https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/"
        "dist/web/variable/pretendardvariable-dynamic-subset.min.css'>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Black+Han+Sans&display=swap'>")




def page(title, body, active="", desc=None, image=None, wide=False):
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
            f"<img src='favicon.svg' alt=''><span>{e(SITE_NAME)}</span></a>"
            f"<a class='bellpill' href='index.html#push'>🔔 알림 받는 중</a><nav>{nav}</nav></div></header>"
            f"<main class='{'wide' if wide else ''}'>{body}<footer><a href='join.html'>브릭소리 받아보기</a> · 매일 낮 12시 업데이트 · 소식마다 출처를 밝히며, 원문 저작권은 각 매체에 있습니다</footer></main>"
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


def meta(it, keys=("channel", "discount", "value", "period", "limit", "set", "theme", "price", "release")):
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


# ---------- 날짜별 페이지 (C2 대시보드) ----------
def short_store(it):
    s = (it.get("source") or "").split("·")[0].split("(")[0].strip()
    return s.replace("레고 공식몰", "공식몰")[:10]


def deal_row(x, as_of):
    it = x["it"]
    if x.get("end"):
        left = (x["end"] - as_of).days
        tag = ("t-soon", "오늘 마감") if left == 0 else ("t-soon", f"D-{left}") if left <= 3 else ("t-deal", f"~{md(x['end'])}")
    else:
        tag = ("t-deal", "진행 중")
    sub = " · ".join(v for v in [it.get("discount"), it.get("value"), it.get("limit") or it.get("period")] if v)
    new = "<span class='pill-new'>NEW</span>" if x["first"] == as_of.isoformat() else ""
    return (f"<a class='li' id='d-{x['id']}' href='{e(it['url'])}' target='_blank' rel='noopener'>"
            f"<span class='tag {tag[0]}'>{e(tag[1])}</span><span class='rb'><span class='rt'>{e(it['title'])}</span>"
            + (f"<span class='rm'>{e(sub)}</span>" if sub else "")
            + f"</span>{new or ''}<span class='rs'>{e(short_store(it))}</span></a>")


def release_row(x, as_of):
    it = x["it"]
    img = (f"<img class='th' src='{e(it['image'])}' alt='' loading='lazy' referrerpolicy='no-referrer' "
           f"onerror=\"this.outerHTML='<span class=thf>{e(it.get('set') or 'NEW')}</span>'\">") if it.get("image") \
        else f"<span class='thf'>{e(it.get('set') or 'NEW')}</span>"
    rel = x["rd"]
    when = (f"출시 D-{(rel - as_of).days}" if rel and rel > as_of else "오늘 출시" if rel == as_of
            else it.get("release") or "")
    sub = " · ".join(v for v in [it.get("theme"), it.get("tag"), it.get("price"), when] if v)
    new = "<span class='pill-new'>NEW</span>" if x["first"] == as_of.isoformat() else ""
    return (f"<a class='li' id='r-{x['id']}' href='{e(it['url'])}' target='_blank' rel='noopener'>{img}"
            f"<span class='rb'><span class='rt'>{e(it['title'])}</span><span class='rm'>{e(sub)}</span></span>{new}</a>")


def news_row(d, key, it):
    tag = ("t-kr", "국내") if key == "kr_news" else ("t-gl", "해외")
    return (f"<a class='li' id='n-{item_id(it)}' href='{news_page(d['date'], it)}'><span class='tag {tag[0]}'>{tag[1]}</span>"
            f"<span class='rb'><span class='rt'>{e(it['title'])}</span><span class='rm'>{e(it.get('source', ''))}</span></span></a>")


def render_digest(d, pools, prev_d=None, next_d=None, active=""):
    as_of = to_date(d["date"])
    by_key = {s["key"]: s.get("items", []) for s in d.get("sections", [])}
    deals, rels = pools["kr_deal"], pools["new_release"]
    news = [(k, it) for k in NEWS_KEYS for it in by_key.get(k, [])]
    soon = [x for x in deals if x.get("end") and (x["end"] - as_of).days <= 1]
    official = sum(1 for x in deals if "공식" in (x["it"].get("source", "") + x["it"].get("tag", "")))
    new_rel = sum(1 for x in rels if x["first"] == d["date"])
    kr_n, gl_n = len(by_key.get("kr_news", [])), len(by_key.get("global_news", []))

    stats = (
        "<div class='stats'>"
        f"<a class='stat s-deal' href='deals.html'><b>진행 중 할인</b><strong>{len(deals)}</strong>"
        f"<small>공식몰 {official} · 기타 {len(deals) - official}</small></a>"
        f"<a class='stat s-soon' href='deals.html'><b>오늘·내일 마감</b><strong>{len(soon)}</strong>"
        f"<small>{'놓치기 전에 확인' if soon else '급한 마감 없음'}</small></a>"
        f"<a class='stat s-new' href='releases.html'><b>신제품 소식</b><strong>{len(rels)}</strong>"
        f"<small>오늘 새로 {new_rel}</small></a>"
        f"<a class='stat s-news' href='#news'><b>국내·해외 소식</b><strong>{len(news)}</strong>"
        f"<small>국내 {kr_n} · 해외 {gl_n}</small></a></div>")

    def box(cls, bid, title, n, href, rows, empty):
        all_ = f"<span class='all'>전체 보기</span>" if href.endswith(".html") else ""
        body = "".join(rows) if rows else f"<div class='empty'>{empty}</div>"
        return (f"<section class='box {cls}' id='{bid}'><a class='box-h' href='{href}'><i></i><h2>{title}</h2>"
                f"<span class='n'>{n}</span>{all_}</a>{body}</section>")

    main_col = [
        stats,
        f"<section class='oneline'><b>오늘의 한 줄</b><p>{e(d['headline'])}</p></section>" if d.get("headline") else "",
        box("b-deal", "kr_deal", "국내 할인", len(deals), "deals.html",
            [deal_row(x, as_of) for x in deals[:MAIN_LIMIT]], "지금은 진행 중인 할인이 없어요."),
        box("b-new", "new_release", "신제품 발매", len(rels), "releases.html",
            [release_row(x, as_of) for x in rels[:MAIN_LIMIT]], "지금은 새 신제품 소식이 없어요."),
        box("b-news", "news", "국내·해외 소식", len(news), "#news",
            [news_row(d, k, it) for k, it in news], "오늘은 새 소식이 없어요."),
    ]
    cal = d.get("calendar") or []
    up = [c for c in cal if (loose_date(c.get("date"), as_of) or as_of) >= as_of] or cal
    first_news = news[0][1] if news else None
    minis = "<div class='minis'>"
    if up:
        c0 = up[0]
        minis += (f"<a class='mini m-cal' href='#calendar'><b>출시 캘린더</b><strong>{e(cal_date(c0.get('date')).split(' ')[0])}</strong>"
                  f"<span>{e(' '.join(v for v in [c0.get('set'), c0.get('name')] if v))}</span><small>다음 출시 · 총 {len(cal)}건</small></a>")
    else:
        minis += "<div class='mini m-cal'><b>출시 캘린더</b><span>예정된 출시가 아직 없어요</span></div>"
    if first_news:
        k0 = news[0][0]
        minis += (f"<a class='mini m-news' href='{news_page(d['date'], first_news)}'><b>{'해외' if k0 == 'global_news' else '국내'} 소식</b>"
                  f"<span>{e(first_news['title'])}</span><small>{'번역 요약' if k0 == 'global_news' else '요약'} · {e(first_news.get('source', ''))}</small></a>")
    else:
        minis += "<a class='mini m-news' href='archive.html'><b>지난 소식</b><span>날짜별 소식과 검색</span><small>전체 보기</small></a>"
    minis += "</div>"
    cal_box = ""
    if cal:
        rows = "".join(
            f"<div class='calrow'><span class='d'>{e(cal_date(c.get('date')))}</span>"
            f"<span>{e(c.get('name', ''))}<small>{e(' · '.join(x for x in [c.get('set'), c.get('theme'), c.get('region')] if x))}</small></span>"
            f"<span class='p'>{e(str(c.get('price', '')))}</span></div>" for c in cal)
        cal_box = (f"<section class='box b-cal' id='calendar'><div class='box-h'><i></i><h2>🗓️ 출시 캘린더</h2>"
                   f"<span class='n'>앞으로 60일</span></div>{rows}</section>")
    side = [minis, "<section id='push' class='push' hidden></section>", follow_links(), cal_box]
    nav = "<div class='pager'>"
    nav += f"<a href='{page_name(prev_d)}'>← {prev_d['date'][5:]}</a>" if prev_d else "<span></span>"
    nav += f"<a href='{page_name(next_d)}'>{next_d['date'][5:]} →</a>" if next_d else "<span></span>"
    nav += "</div>"
    body = (f"<div class='dhead'><h1>{e(kdate(d['date'], year=False))}</h1><span>오늘의 레고 소식</span></div>"
            f"<div class='dash'><div class='dash-main'>{''.join(main_col)}</div>"
            f"<aside class='dash-side'>{''.join(side)}</aside></div>{nav}"
            "<div class='subbar'><p><b>매일 12시</b> 할인·신제품 알림<br>무료로 받아보세요</p><a href='#push'>알림 받기</a></div>")
    return page(f"{SITE_NAME} · {kdate(d['date'], year=False)} 오늘의 레고 소식", body, active,
                desc=d.get("headline") or None, wide=True)


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


# ---------- 블로그에서 들어온 사람을 위한 안내 페이지 ----------
def render_join(pools, latest):
    picks = [("kr_deal", x) for x in pools["kr_deal"][:2]] + [("new_release", x) for x in pools["new_release"][:2]]
    prev = "".join(pool_card(k, x, to_date(latest["date"])) for k, x in picks) if latest else ""
    ways = []
    if KAKAO_CHANNEL_URL:
        ways.append(f"<a class='kakao' href='{e(KAKAO_CHANNEL_URL)}' target='_blank' rel='noopener'>카카오톡 채널 추가</a>")
    if INSTAGRAM_URL:
        ways.append(f"<a href='{e(INSTAGRAM_URL)}' target='_blank' rel='noopener'>인스타그램 팔로우</a>")
    body = (
        f"<section class='hero-j'><img src='favicon.svg' alt=''><h1>{e(SITE_NAME)}</h1>"
        "<p>매일 낮 12시, 놓치기 쉬운 레고 할인과 전 세계 신제품 소식을 한 번에 정리해 알려드려요. 모두 무료예요.</p></section>"
        "<div class='ben'>"
        "<div><b>🏷️ 국내 할인</b><span>레고 공식몰·공인스토어·이마트·롯데마트·쿠팡 등 행사를 시작·마감 순으로</span></div>"
        "<div><b>🆕 전 세계 신제품</b><span>공식 발표부터 신뢰도 높은 루머까지, 세트번호·가격·출시일 정리</span></div>"
        "<div><b>📰 국내·해외 소식</b><span>광고 없이 읽도록 핵심만 요약·번역, 출처는 정확히</span></div></div>"
        "<h2>① 휴대폰·PC 알림으로 받기 <small>추천</small></h2>"
        "<section id='push' class='push' hidden></section>"
        + (f"<h2>② 카카오톡·인스타그램으로 받기</h2><div class='follow'>{''.join(ways)}</div>" if ways else "")
        + (f"<h2>지금 진행 중인 소식 미리보기</h2>{prev}<a class='more' href='index.html'>오늘의 레고 소식 전체 보기 →</a>" if prev else "")
        + "<h2>자주 묻는 질문</h2><div class='faq'>"
        "<details><summary>정말 무료인가요?</summary><p>네, 가입이나 결제 없이 무료예요. 알림은 하루 한 번, 낮 12시쯤에만 가요.</p></details>"
        "<details><summary>알림은 어떻게 끄나요?</summary><p>이 사이트 위쪽 알림 상자에서 '알림 끄기'를 누르면 바로 멈춰요. 받을 분야(할인·신제품 등)도 고를 수 있어요.</p></details>"
        "<details><summary>아이폰도 되나요?</summary><p>사파리에서 공유 버튼 → '홈 화면에 추가'를 한 뒤, 홈 화면 아이콘으로 열어서 알림을 켜면 돼요.</p></details>"
        "</div>")
    return page(f"{SITE_NAME} · 매일 12시 레고 할인·신제품 알림", body, "",
                desc="레고 공식몰·마트·온라인몰 할인과 전 세계 신제품 소식을 매일 낮 12시에 무료로 알려드려요.")


# ---------- 네이버 블로그 주간 글 초안 ----------
def week_label(dt):
    names = ["첫째", "둘째", "셋째", "넷째", "다섯째"]
    return f"{dt.month}월 {names[min((dt.day - 1) // 7, 4)]} 주"


def render_blog_draft(main_list, pools, latest):
    as_of = to_date(latest["date"])
    since = (as_of - timedelta(days=6)).isoformat()
    week = [d for d in main_list if d["date"] >= since]
    base = site_url()
    q = "?src=blog_weekly"
    deals = pools["kr_deal"]
    rels = [x for x in pools["new_release"] if x["first"] >= since]
    news = [(d, s["key"], it) for d in reversed(week) for s in d.get("sections", [])
            if s.get("key") in NEWS_KEYS for it in s.get("items", [])][:6]
    title = f"[{SITE_NAME} 주간 정리] {week_label(as_of)} 레고 할인·신제품 총정리 ({md(as_of)} 기준)"
    H = []
    H.append(f"<p>안녕하세요! 이번 주 놓치기 쉬운 <b>레고 할인</b>과 <b>신제품 소식</b>을 정리했어요. "
             f"({md(to_date(since))}~{md(as_of)}, 진행 중인 할인 {len(deals)}건 · 새 신제품 소식 {len(rels)}건)</p>")
    H.append("<p>✍️ <b>이번 주 제 픽:</b> (여기에 직접 한두 줄 써 주세요. 예: 저는 ○○ 세트가 제일 끌리네요!)</p>")
    if deals:
        H.append("<h3>🏷️ 지금 진행 중인 레고 할인</h3><ul>")
        for x in deals[:10]:
            it = x["it"]
            info = " · ".join(v for v in [it.get("discount"), it.get("period")] if v)
            end = f" <b>({md(x['end'])} 마감)</b>" if x.get("end") else ""
            H.append(f"<li><b>{e(it['title'])}</b>{end}<br>{e(info)}"
                     + (f" — {e(it['summary'])}" if it.get("summary") else "") + f" <small>(출처: {e(it.get('source', ''))})</small></li>")
        H.append(f"</ul><p>👉 할인 전체 목록: <a href='{base}/deals.html{q}'>{base}/deals.html</a></p>")
    if rels:
        H.append("<h3>🆕 이번 주 신제품 소식</h3><ul>")
        for x in rels[:10]:
            it = x["it"]
            info = " · ".join(v for v in [it.get("set"), it.get("theme"), it.get("price"), it.get("release")] if v)
            tag = f"[{e(it['tag'])}] " if it.get("tag") else ""
            H.append(f"<li>{tag}<b>{e(it['title'])}</b><br>{e(info)}"
                     + (f" — {e(it['summary'])}" if it.get("summary") else "") + "</li>")
        H.append(f"</ul><p>👉 신제품 전체 목록: <a href='{base}/releases.html{q}'>{base}/releases.html</a></p>")
    if news:
        H.append("<h3>📰 국내·해외 레고 소식</h3><ul>")
        for d, k, it in news:
            H.append(f"<li><b>{e(it['title'])}</b> — {e(it.get('summary', ''))} "
                     f"<a href='{base}/{news_page(d['date'], it)}{q}'>자세히</a> <small>(출처: {e(it.get('source', ''))})</small></li>")
        H.append("</ul>")
    cal = [c for c in (latest.get("calendar") or [])][:8]
    if cal:
        H.append("<h3>🗓️ 다가오는 출시 일정</h3><ul>")
        for c in cal:
            H.append(f"<li><b>{e(cal_date(c.get('date')))}</b> {e(c.get('name', ''))} "
                     f"{e(' · '.join(v for v in [c.get('set'), c.get('price')] if v))}</li>")
        H.append("</ul>")
    H.append(f"<h3>🔔 매일 12시에 받아보기</h3><p>이런 소식을 <b>매일 낮 12시</b>에 휴대폰 알림·카카오톡으로 무료로 받아볼 수 있어요.<br>"
             f"👉 <a href='{base}/join.html{q}'>{base}/join.html</a></p>")
    H.append("<p><small>※ 할인 조건·기간은 판매처 사정으로 바뀔 수 있으니 구매 전 꼭 확인하세요.</small></p>")
    themes = sorted({x["it"].get("theme") for x in rels if x["it"].get("theme")})
    tags = ["레고", "레고할인", "레고신제품", "레고세일", "레고추천", "LEGO", "브릭소리"] + [f"레고{t.replace(' ', '')}" for t in themes][:5]
    tag_txt = " ".join(f"#{t}" for t in tags)
    draft = "".join(H)
    body = (
        "<h1>📝 네이버 블로그 주간 글 초안</h1>"
        "<div class='tip'><b>올리는 방법</b><ol>"
        "<li>[제목 복사] → 블로그 글쓰기 제목 칸에 붙여넣기</li>"
        "<li>[본문 복사] → 본문에 붙여넣기 (굵은 글씨·링크가 함께 들어가요)</li>"
        "<li>'✍️ 이번 주 제 픽' 줄에 내 생각을 한두 줄 쓰기 — 네이버가 '직접 쓴 글'로 봐서 노출에 유리해요</li>"
        "<li>맨 위에 대표 이미지(주간 썸네일), 맨 아래에 모집 배너를 넣고 배너에 링크 걸기</li>"
        "<li>[태그 복사] → 태그 칸에 붙여넣기</li></ol></div>"
        "<div class='copybar'><button data-copy='t'>제목 복사</button><button data-copy='b'>본문 복사</button>"
        "<button data-copy='g' class='sec'>태그 복사</button>"
        "<a class='more' style='margin:0;padding:10px 14px' href='blog-weekly-thumb.png' download>주간 썸네일 받기</a>"
        "<a class='more' style='margin:0;padding:10px 14px' href='blog-banner-wide.png' download>모집 배너 받기</a></div>"
        f"<p><b>제목</b></p><div class='draft' id='t'>{e(title)}</div>"
        f"<p><b>본문</b></p><div class='draft' id='b'>{draft}</div>"
        f"<p><b>태그</b></p><div class='draft' id='g'>{e(tag_txt)}</div>"
        "<script>document.querySelectorAll('[data-copy]').forEach(btn=>btn.onclick=async()=>{"
        "const el=document.getElementById(btn.dataset.copy),old=btn.textContent;"
        "try{if(btn.dataset.copy==='b'&&window.ClipboardItem){await navigator.clipboard.write([new ClipboardItem({"
        "'text/html':new Blob([el.innerHTML],{type:'text/html'}),'text/plain':new Blob([el.innerText],{type:'text/plain'})})])}"
        "else{await navigator.clipboard.writeText(el.innerText)}}catch(err){const r=document.createRange();r.selectNodeContents(el);"
        "const s=getSelection();s.removeAllRanges();s.addRange(r);document.execCommand('copy');s.removeAllRanges()}"
        "btn.textContent='복사됨 ✓';setTimeout(()=>btn.textContent=old,1500)});</script>")
    return page(f"{SITE_NAME} · 블로그 초안", body, "").replace(
        "<meta charset='utf-8'>", "<meta charset='utf-8'><meta name='robots' content='noindex'>", 1)


# ---------- 관리자 통계 페이지 (로그인한 허락된 이메일만 숫자가 보임) ----------
def source_stats(main_list, days=30):
    """최근 N일 동안 실린 소식의 출처별 개수 + 클릭 TOP 표시용 제목."""
    import collections
    recent = main_list[-days:]
    cnt = collections.Counter()
    titles = {}
    for d in recent:
        for s in d.get("sections", []):
            for it in s.get("items", []):
                src = (it.get("source") or "알 수 없음").split("·")[0].split("(")[0].strip()
                if src.startswith("네이버") and "뉴스" not in src:
                    src = src.split()[0] + " " + (src.split()[1] if len(src.split()) > 1 else "")
                cnt[src.strip()] += 1
                titles[it["url"]] = it["title"]
    return {"days": len(recent), "items": [{"source": k, "n": v} for k, v in cnt.most_common(12)], "titles": titles}


def render_stats(main_list):
    data = json.dumps(source_stats(main_list), ensure_ascii=False).replace("</", "<\\/")
    body = ("<div class='dhead'><h1>📊 브릭소리 통계</h1><span>관리자 전용</span></div>"
            "<div id='app'><p class='empty'>불러오는 중…</p></div>"
            f"<script>window.LD_SOURCES={data}</script>"
            "<script src='https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2'></script>"
            "<script src='stats.js' defer></script>")
    return page(f"{SITE_NAME} · 통계", body, "", wide=True).replace(
        "<meta charset='utf-8'>", "<meta charset='utf-8'><meta name='robots' content='noindex,nofollow'>", 1)


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
        write("join.html", render_join(pools, latest))
        write("blog-draft.html", render_blog_draft(main_list, pools, latest))
    else:
        from common import today_kst
        for k, fname in POOL_PAGES.items():
            write(fname, render_pool_page(k, [], today_kst()))
        write("join.html", render_join({k: [] for k in POOL_PAGES}, None))
    write("archive.html", render_archive(list(reversed(main_list))))
    write("stats.html", render_stats(main_list))
    print(f"built {len(all_d)} day pages, {n_news} news pages (+index, deals, releases, archive) into {OUT}")


if __name__ == "__main__":
    main()

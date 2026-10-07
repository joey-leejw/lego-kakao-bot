"""인스타그램 카드뉴스(1080x1350) 자동 생성.

오늘 다이제스트로 표지·할인·신제품·소식·구독 안내 카드를 PNG로 만들고,
_site/cards/{날짜}/ 와 _site/cards.html(복사용 캡션 + 내려받기)을 만든다.
build_site.py 다음에 실행. 필요: pip install playwright && playwright install chromium

사용법: python scripts/make_cards.py digests/claude/2026-10-07.json
"""
import html
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_site as B  # noqa: E402  (할인·신제품 모으기 규칙을 그대로 씀)
from common import ROOT, NEWS_KEYS, load_json, site_url  # noqa: E402

OUT = pathlib.Path(ROOT) / "_site"
# 글꼴 폴더: assets/fonts (권장) 또는 site_assets/fonts 어느 쪽에 있어도 됨
FONTS = next((p for p in (pathlib.Path(ROOT) / "assets" / "fonts", pathlib.Path(ROOT) / "site_assets" / "fonts")
              if (p / "Pretendard-Bold.subset.woff2").exists()), pathlib.Path(ROOT) / "assets" / "fonts")
W, H = 1080, 1350
e = html.escape

MARK = ('<svg viewBox="0 0 120 120" width="{s}" height="{s}"><rect width="120" height="120" rx="26" fill="#FF6B2C"/>'
        '<g transform="translate(14.64 10.68) scale(0.72)"><rect x="20" y="39" width="18" height="15" rx="4" fill="#fff"/>'
        '<rect x="49" y="39" width="18" height="15" rx="4" fill="#fff"/><rect x="12" y="50" width="63" height="42" rx="9" fill="#fff"/>'
        '<path d="M87 59 A16 16 0 0 1 87 83" fill="none" stroke="#1B1B1F" stroke-width="8" stroke-linecap="round"/>'
        '<path d="M99 48 A29 29 0 0 1 99 94" fill="none" stroke="#1B1B1F" stroke-width="8" stroke-linecap="round"/></g></svg>')

CSS = f"""
@font-face{{font-family:P;src:url({(FONTS / 'Pretendard-Medium.subset.woff2').as_uri()});font-weight:500}}
@font-face{{font-family:P;src:url({(FONTS / 'Pretendard-Bold.subset.woff2').as_uri()});font-weight:700}}
@font-face{{font-family:P;src:url({(FONTS / 'Pretendard-ExtraBold.subset.woff2').as_uri()});font-weight:800}}
@font-face{{font-family:BH;src:url({(FONTS / 'black-han-sans-korean-400-normal.woff2').as_uri()})}}
@font-face{{font-family:BH;src:url({(FONTS / 'black-han-sans-latin-400-normal.woff2').as_uri()});unicode-range:U+0000-00FF}}
*{{box-sizing:border-box}}html,body{{margin:0}}
body{{font-family:P,sans-serif;color:#26231F}}
.card{{width:{W}px;height:{H}px;background:#FBF8F3;padding:72px 72px 64px;display:flex;flex-direction:column;position:relative;overflow:hidden}}
.bh{{font-family:BH,P,sans-serif;font-weight:400}}
.top{{display:flex;align-items:center;gap:16px;font-size:30px;font-weight:700;color:#6E675C}}
.top .bh{{font-size:40px;color:#26231F}}.top .pg{{margin-left:auto;font-size:28px}}
.chip{{display:inline-block;font-size:30px;font-weight:800;padding:10px 24px;border-radius:999px}}
h1{{margin:0;font-family:BH,P,sans-serif;font-weight:400;font-size:92px;line-height:1.12;letter-spacing:-1px}}
.foot{{margin-top:auto;display:flex;align-items:center;gap:14px;font-size:28px;font-weight:700;color:#6E675C}}
.foot b{{color:#26231F}}
.row{{display:flex;align-items:center;gap:26px;background:#fff;border-radius:28px;padding:30px 32px;margin-top:20px}}
.tag{{flex:none;min-width:150px;text-align:center;font-size:30px;font-weight:800;padding:14px 10px;border-radius:18px}}
.rt{{font-size:38px;font-weight:800;line-height:1.3;word-break:keep-all;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.rm{{font-size:27px;font-weight:500;color:#6E675C;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:700px}}
.set{{flex:none;width:150px;height:150px;border-radius:26px;display:flex;align-items:center;justify-content:center;font-family:BH,P,sans-serif;font-size:40px;text-align:center;line-height:1.05;padding:8px;overflow:hidden}}
.set img{{width:100%;height:100%;object-fit:cover;border-radius:20px}}
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:44px}}
.tile{{border-radius:30px;padding:28px 26px}}.tile b{{display:block;font-size:28px}}.tile strong{{display:block;font-family:BH,P,sans-serif;font-weight:400;font-size:96px;line-height:1.05;color:#26231F}}
.lead{{background:#FFF3C4;border-radius:30px;padding:34px 36px;margin-top:28px}}
.lead b{{font-size:28px;color:#6B5200}}.lead p{{margin:10px 0 0;font-size:44px;font-weight:800;line-height:1.4;word-break:keep-all}}
.news{{background:#fff;border-radius:28px;padding:32px 34px;margin-top:20px}}
.news .src{{font-size:26px;font-weight:700}}.news .t{{font-size:38px;font-weight:800;line-height:1.3;margin-top:6px;word-break:keep-all}}
.news p{{margin:10px 0 0;font-size:28px;line-height:1.5;color:#4E483F;word-break:keep-all;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.more{{font-size:28px;font-weight:700;color:#6E675C;margin-top:22px}}
"""

DEAL = ("#FFE4D3", "#B5400F")
SOON = ("#FFD9DE", "#A3243B")
NEW = ("#D7F2E3", "#1F6B47")
NEWS = ("#DCEBFF", "#2456A6")
LINE = ("#FFF3C4", "#6B5200")


def header(page, total, label=None, color=None):
    chip = f"<span class='chip' style='background:{color[0]};color:{color[1]}'>{e(label)}</span>" if label else ""
    return (f"<div class='top'>{MARK.format(s=56)}<span class='bh'>브릭소리</span>{chip}"
            f"<span class='pg'>{page}/{total}</span></div>")


def footer(d):
    return (f"<div class='foot'>{e(B.kdate(d['date'], year=False))} · 매일 12시 레고 소식 "
            f"<b style='margin-left:auto'>bricksori.com</b></div>")


def cover(d, pools, n, total):
    as_of = B.to_date(d["date"])
    deals, rels = pools["kr_deal"], pools["new_release"]
    soon = [x for x in deals if x.get("end") and (x["end"] - as_of).days <= 1]
    lead = (f"<div class='lead'><b>오늘의 한 줄</b><p>{e(d['headline'])}</p></div>" if d.get("headline") else "")
    return (f"<div class='card'>{header(n, total)}"
            f"<div style='margin-top:90px;font-size:40px;font-weight:800;color:#B5400F'>{e(B.kdate(d['date'], year=False))}</div>"
            f"<h1 style='margin-top:10px'>오늘의<br>레고 소식</h1>"
            f"<div class='tiles'>"
            f"<div class='tile' style='background:{DEAL[0]};color:{DEAL[1]}'><b>진행 중 할인</b><strong>{len(deals)}</strong></div>"
            f"<div class='tile' style='background:{SOON[0]};color:{SOON[1]}'><b>오늘·내일 마감</b><strong>{len(soon)}</strong></div>"
            f"<div class='tile' style='background:{NEW[0]};color:{NEW[1]}'><b>신제품 소식</b><strong>{len(rels)}</strong></div>"
            f"</div>{lead}<div class='more'>옆으로 넘겨서 확인하세요 →</div>{footer(d)}</div>")


def deal_card(d, pools, n, total):
    as_of = B.to_date(d["date"])
    rows = []
    for x in pools["kr_deal"][:4]:
        it = x["it"]
        if x.get("end"):
            left = (x["end"] - as_of).days
            tag, col = ("오늘 마감", SOON) if left == 0 else (f"D-{left}", SOON) if left <= 3 else (f"~{B.md(x['end'])}", DEAL)
        else:
            tag, col = ("진행 중", DEAL)
        sub = " · ".join(v for v in [it.get("discount"), it.get("value"), B.short_store(it)] if v)
        rows.append(f"<div class='row'><span class='tag' style='background:{col[0]};color:{col[1]}'>{e(tag)}</span>"
                    f"<div style='min-width:0'><div class='rt'>{e(it['title'])}</div><div class='rm'>{e(sub)}</div></div></div>")
    more = len(pools["kr_deal"]) - 4
    return (f"<div class='card'>{header(n, total, '국내 할인', DEAL)}"
            f"<h1 style='font-size:76px;margin-top:44px'>지금 진행 중인<br>레고 할인</h1>{''.join(rows)}"
            + (f"<div class='more'>외 {more}건 더 · 프로필 링크에서 전체 보기</div>" if more > 0 else "")
            + f"{footer(d)}</div>")


def release_card(d, pools, n, total):
    as_of = B.to_date(d["date"])
    rows = []
    for x in pools["new_release"][:4]:
        it = x["it"]
        label = e(it.get("set") or "NEW")
        thumb = (f"<img src='{e(it['image'])}' referrerpolicy='no-referrer' "
                 f"onerror=\"this.replaceWith(document.createTextNode('{label}'))\">" if it.get("image") else label)
        rd = x.get("rd")
        when = (f"출시 D-{(rd - as_of).days}" if rd and rd > as_of else it.get("release") or "")
        sub = " · ".join(v for v in [it.get("theme"), it.get("tag"), it.get("price"), when] if v)
        rows.append(f"<div class='row'><span class='set' style='background:{NEW[0]};color:{NEW[1]}'>{thumb}</span>"
                    f"<div style='min-width:0'><div class='rt'>{e(it['title'])}</div><div class='rm'>{e(sub)}</div></div></div>")
    return (f"<div class='card'>{header(n, total, '신제품', NEW)}"
            f"<h1 style='font-size:76px;margin-top:44px'>전 세계<br>레고 신제품</h1>{''.join(rows)}{footer(d)}</div>")


def news_card(d, items, n, total):
    blocks = []
    for k, it in items[:3]:
        where = "해외 · 번역 요약" if k == "global_news" else "국내"
        blocks.append(f"<div class='news'><div class='src' style='color:{NEWS[1]}'>{where} · {e(it.get('source', ''))}</div>"
                      f"<div class='t'>{e(it['title'])}</div>" + (f"<p>{e(it['summary'])}</p>" if it.get("summary") else "") + "</div>")
    return (f"<div class='card'>{header(n, total, '레고 소식', NEWS)}"
            f"<h1 style='font-size:76px;margin-top:44px'>오늘의<br>국내·해외 소식</h1>{''.join(blocks)}{footer(d)}</div>")


def cta_card(d, n, total):
    return (f"<div class='card' style='background:#1B1B1F;color:#F6F1E7'>"
            f"<div class='top' style='color:#B8B0A2'>{MARK.format(s=56)}<span class='bh' style='color:#F6F1E7'>브릭소리</span>"
            f"<span class='pg'>{n}/{total}</span></div>"
            f"<div style='margin-top:150px'>{MARK.format(s=220)}</div>"
            f"<h1 style='margin-top:50px;color:#F6F1E7'>레고 할인,<br>이제 놓치지 마세요</h1>"
            f"<p style='font-size:40px;font-weight:700;line-height:1.5;color:#C9C2B6;margin:28px 0 0'>매일 낮 12시 할인·신제품 소식을<br>휴대폰 알림·카톡으로 무료로 받아보세요</p>"
            f"<div style='margin-top:50px;display:inline-flex;align-self:flex-start;background:#FF6B2C;color:#1B1B1F;font-size:40px;font-weight:800;padding:26px 44px;border-radius:999px'>프로필 링크에서 알림 받기 →</div>"
            f"<div class='foot' style='color:#B8B0A2'>저장해 두고 할인 마감 전에 확인하세요<b style='margin-left:auto;color:#F6F1E7'>@bricksori</b></div></div>")


def caption(d, pools, news):
    as_of = B.to_date(d["date"])
    lines = [f"🧱 {B.kdate(d['date'], year=False)} 오늘의 레고 소식", ""]
    if d.get("headline"):
        lines += [d["headline"], ""]
    if pools["kr_deal"]:
        lines.append("🏷️ 진행 중인 할인")
        for x in pools["kr_deal"][:4]:
            end = f" (~{B.md(x['end'])})" if x.get("end") else ""
            lines.append(f"· {x['it']['title']}{end}")
        lines.append("")
    if pools["new_release"]:
        lines.append("🆕 신제품")
        lines += [f"· {x['it']['title']}" for x in pools["new_release"][:4]]
        lines.append("")
    if news:
        lines.append("📰 소식")
        lines += [f"· {it['title']}" for _, it in news[:3]]
        lines.append("")
    lines += ["매일 12시 레고 할인·신제품 알림은 프로필 링크 👉 bricksori.com",
              "※ 할인 조건·기간은 판매처 사정으로 바뀔 수 있어요.", ""]
    themes = sorted({x["it"].get("theme", "").replace(" ", "") for x in pools["new_release"][:6] if x["it"].get("theme")})
    tags = ["레고", "레고할인", "레고신제품", "레고스타그램", "LEGO", "브릭소리", "레고덕후", "레고추천"] + [f"레고{t}" for t in themes][:4]
    lines.append(" ".join(f"#{t}" for t in tags))
    return "\n".join(lines)


def render_page(d, files, cap):
    imgs = "".join(f"<a href='cards/{d['date']}/{f}' download><img src='cards/{d['date']}/{f}' alt='카드 {i + 1}' loading='lazy'></a>"
                   for i, f in enumerate(files))
    body = ("<h1>📸 인스타그램 카드뉴스</h1>"
            "<div class='tip'><b>올리는 방법</b><ol>"
            "<li>카드를 하나씩 눌러 저장해요 (휴대폰은 길게 눌러 '이미지 저장')</li>"
            "<li>인스타그램 → 새 게시물 → 여러 장 선택에서 1번부터 순서대로 골라요</li>"
            "<li>[캡션 복사]를 눌러 문구 칸에 붙여넣어요</li></ol></div>"
            "<div class='copybar'><button data-copy='cap'>캡션 복사</button></div>"
            f"<div class='cards'>{imgs}</div>"
            f"<p><b>캡션</b></p><div class='draft' id='cap' style='white-space:pre-wrap'>{e(cap)}</div>"
            "<style>.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;margin:12px 0}"
            ".cards img{width:100%;border-radius:12px;display:block;border:1px solid var(--line)}</style>"
            "<script>document.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{const el=document.getElementById(b.dataset.copy),o=b.textContent;"
            "try{await navigator.clipboard.writeText(el.innerText)}catch(_){const r=document.createRange();r.selectNodeContents(el);"
            "const s=getSelection();s.removeAllRanges();s.addRange(r);document.execCommand('copy');s.removeAllRanges()}"
            "b.textContent='복사됨 ✓';setTimeout(()=>b.textContent=o,1500)});</script>")
    page = B.page(f"{B.SITE_NAME} · 카드뉴스 {d['date']}", body, "")
    return page.replace("<meta charset='utf-8'>", "<meta charset='utf-8'><meta name='robots' content='noindex'>", 1)


def main():
    from playwright.sync_api import sync_playwright
    d = load_json(sys.argv[1])
    if not d:
        sys.exit("다이제스트 없음")
    import glob
    all_d = [x for p in glob.glob(os.path.join(ROOT, "digests", "*", "*.json")) if (x := load_json(p)) and x.get("date")]
    best = {}
    for x in all_d:
        if x["date"] not in best or x["source"] == "claude":
            best[x["date"]] = x
    main_list = sorted(best.values(), key=lambda x: x["date"])
    pools = {k: B.build_pool(k, main_list, d["date"]) for k in B.POOL_PAGES}
    news = [(s["key"], it) for s in d.get("sections", []) if s.get("key") in NEWS_KEYS for it in s.get("items", [])]

    makers = [lambda n, t: cover(d, pools, n, t)]
    if pools["kr_deal"]:
        makers.append(lambda n, t: deal_card(d, pools, n, t))
    if pools["new_release"]:
        makers.append(lambda n, t: release_card(d, pools, n, t))
    if news:
        makers.append(lambda n, t: news_card(d, news, n, t))
    makers.append(lambda n, t: cta_card(d, n, t))

    out = OUT / "cards" / d["date"]
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_card.html"
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, mk in enumerate(makers):
            tmp.write_text(f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><style>{CSS}</style></head>"
                           f"<body>{mk(i + 1, len(makers))}</body></html>", encoding="utf-8")
            pg.goto(tmp.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(400)  # 썸네일 이미지 로딩 여유
            name = f"{i + 1:02d}.png"
            pg.screenshot(path=str(out / name), clip={"x": 0, "y": 0, "width": W, "height": H})
            files.append(name)
        b.close()
    tmp.unlink()
    cap = caption(d, pools, news)
    (out / "caption.txt").write_text(cap, encoding="utf-8")
    (OUT / "cards.html").write_text(render_page(d, files, cap), encoding="utf-8")
    print(f"카드뉴스 {len(files)}장 → {out}  ({site_url()}/cards.html)")


if __name__ == "__main__":
    main()

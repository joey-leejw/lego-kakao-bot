"""digests/ 의 JSON을 읽어 _site/ 에 GitHub Pages용 HTML을 만든다.

카카오 메시지의 링크는 '등록된 도메인'만 열리기 때문에,
모든 기사 링크를 이 페이지(github.io) 한 곳에 모아두고 메시지는 이 페이지로 연결한다.
"""
import glob
import html
import os

from common import ROOT, SECTIONS, SECTION_TITLES, SOURCE_LABELS, load_json, page_name

OUT = os.path.join(ROOT, "_site")

CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e6e4dc;--accent:#d01012}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#33322f;--accent:#ff5a4f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
main{max-width:720px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.1rem;margin:2em 0 .6em;border-bottom:2px solid var(--accent);padding-bottom:.3em}
.meta{color:var(--muted);font-size:.9rem}.headline{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin-top:16px}
.item{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:10px 0;scroll-margin-top:16px}
.item:target{outline:2px solid var(--accent)}
.item a{color:var(--fg);font-weight:600;text-decoration:none}.item a:hover{text-decoration:underline}
.item p{margin:.3em 0 0;color:var(--muted);font-size:.93rem}.src{font-size:.8rem;color:var(--muted)}
.empty{color:var(--muted);font-size:.9rem}ul.list{padding-left:1.2em}ul.list a{color:var(--fg)}
"""


def page(title, body):
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main></body></html>")


def render_digest(d):
    e = html.escape
    label = SOURCE_LABELS.get(d["source"], d["source"])
    parts = [f"<p class='meta'><a href='index.html'>← 전체 목록</a></p>",
             f"<h1>🧱 레고 데일리 {e(d['date'])}</h1><p class='meta'>{e(label)}</p>"]
    if d.get("headline"):
        parts.append(f"<div class='headline'>{e(d['headline'])}</div>")
    by_key = {s["key"]: s.get("items", []) for s in d.get("sections", [])}
    for key, title in SECTIONS:
        items = by_key.get(key, [])
        parts.append(f"<h2>{e(title)}</h2>")
        if not items:
            parts.append("<p class='empty'>새 소식 없음</p>")
        for i, it in enumerate(items):
            parts.append(
                f"<div class='item' id='{key}-{i}'>"
                f"<a href='{e(it['url'])}' target='_blank' rel='noopener'>{e(it['title'])}</a>"
                + (f"<p>{e(it['summary'])}</p>" if it.get("summary") else "")
                + (f"<div class='src'>{e(it['source'])}</div>" if it.get("source") else "")
                + "</div>")
    return page(f"레고 데일리 {d['date']}", "".join(parts))


def main():
    os.makedirs(OUT, exist_ok=True)
    digests = []
    for path in glob.glob(os.path.join(ROOT, "digests", "*", "*.json")):
        d = load_json(path)
        if d and d.get("date"):
            digests.append(d)
            with open(os.path.join(OUT, page_name(d)), "w", encoding="utf-8") as f:
                f.write(render_digest(d))
    digests.sort(key=lambda d: (d["date"], d["source"]), reverse=True)
    rows = "".join(
        f"<li><a href='{page_name(d)}'>{d['date']} · {SOURCE_LABELS.get(d['source'], d['source'])}</a></li>"
        for d in digests)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("레고 데일리", f"<h1>🧱 레고 데일리</h1><ul class='list'>{rows}</ul>"))
    print(f"built {len(digests)} pages into {OUT}")


if __name__ == "__main__":
    main()

"""방식 2: 무료 자동 수집 스크립트.

Google 뉴스 RSS, 뽐뿌 핫딜 RSS, 해외 레고 전문 블로그 RSS에서
최근 레고 소식을 모아 digests/rss/YYYY-MM-DD.json 으로 저장한다.
외부 라이브러리 없이 파이썬 표준 라이브러리만 사용.
"""
import hashlib
import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from common import ROOT, SECTIONS, digest_path, load_json, save_json, today_kst

UA = "Mozilla/5.0 (lego-kakao-bot; +https://github.com)"
MAX_PER_SECTION = 5
MAX_AGE_HOURS = 36
SEEN_PATH = f"{ROOT}/state/seen.json"
SEEN_KEEP_DAYS = 14

LEGO_RE = re.compile(r"레고|lego", re.I)


def gnews(q, lang="ko"):
    if lang == "ko":
        params = {"q": q, "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    else:
        params = {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(params)


# 섹션별 수집 소스: (url, 출처표시, 제목 필터 정규식 또는 None)
SOURCES = {
    "kr_deal": [
        ("https://www.ppomppu.co.kr/rss.php?id=ppomppu", "뽐뿌", LEGO_RE),
        ("https://www.ppomppu.co.kr/rss.php?id=ppomppu4", "해외뽐뿌", LEGO_RE),
        (gnews("레고 할인 OR 특가 OR 세일 when:2d"), None, LEGO_RE),
    ],
    "new_release": [
        ("https://www.brickfanatics.com/feed/", "Brick Fanatics",
         re.compile(r"reveal|official|new|announce|launch|release", re.I)),
        (gnews('LEGO "new set" OR revealed OR announced when:2d', "en"), None, LEGO_RE),
        (gnews("레고 신제품 OR 출시 when:3d"), None, LEGO_RE),
    ],
    "kr_news": [
        (gnews("레고 -레고랜드 when:1d"), None, LEGO_RE),
    ],
    "global_news": [
        (gnews("LEGO when:1d", "en"), None, LEGO_RE),
    ],
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_xml(raw: bytes):
    """EUC-KR 등 expat이 모르는 인코딩도 처리."""
    m = re.match(rb'<\?xml[^>]*encoding=["\']([\w-]+)["\']', raw)
    enc = m.group(1).decode() if m else "utf-8"
    text = raw.decode(enc, errors="replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    return ET.fromstring(text)


def clean(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_items(url, source_label, title_filter):
    try:
        root = parse_xml(fetch(url))
    except Exception as e:  # 한 소스가 실패해도 계속 진행
        print(f"[warn] {url[:80]} 실패: {e}", file=sys.stderr)
        return []
    now = datetime.now(timezone.utc)
    items = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        src = source_label
        src_el = it.find("source")
        if src_el is not None and src_el.text:
            src = src_el.text.strip()
            # 구글뉴스 제목 끝의 " - 언론사" 제거
            title = re.sub(r"\s+-\s+" + re.escape(src) + r"$", "", title)
        if title_filter and not title_filter.search(title):
            continue
        pub = it.findtext("pubDate")
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if now - dt > timedelta(hours=MAX_AGE_HOURS):
                    continue
            except Exception:
                pass
        summary = clean(it.findtext("description"))
        if summary.startswith(title[:20]):  # 구글뉴스 description은 제목 반복
            summary = ""
        items.append({
            "title": title[:120],
            "summary": summary[:160],
            "url": link,
            "source": src or "",
        })
    return items


def key_of(item):
    norm = re.sub(r"\W+", "", item["title"].lower())[:40]
    return hashlib.md5(norm.encode()).hexdigest()[:12]


def main():
    date = today_kst()
    seen = load_json(SEEN_PATH, {}) or {}
    cutoff = (datetime.now() - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    used = set()

    # 신제품을 먼저 채워서 해외소식과 중복되지 않게
    order = ["kr_deal", "new_release", "kr_news", "global_news"]
    result = {}
    for sec in order:
        picked = []
        for url, label, flt in SOURCES[sec]:
            for item in parse_items(url, label, flt):
                k = key_of(item)
                if k in seen or k in used:
                    continue
                used.add(k)
                picked.append(item)
                if len(picked) >= MAX_PER_SECTION:
                    break
            if len(picked) >= MAX_PER_SECTION:
                break
        result[sec] = picked

    for k in used:
        seen[k] = date

    digest = {
        "date": date,
        "source": "rss",
        "headline": "",
        "sections": [{"key": k, "items": result.get(k, [])} for k, _ in SECTIONS],
    }
    save_json(digest_path("rss", date), digest)
    save_json(SEEN_PATH, seen)
    print(f"saved {digest_path('rss', date)}: " +
          ", ".join(f"{k}={len(result[k])}" for k in order))


if __name__ == "__main__":
    main()

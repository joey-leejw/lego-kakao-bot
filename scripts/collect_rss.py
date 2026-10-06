"""방식 2: 무료 자동 수집 스크립트.

Google 뉴스 RSS, 뽐뿌 핫딜 RSS, 해외 레고 전문 블로그 RSS에서
최근 레고 소식을 모아 digests/rss/YYYY-MM-DD.json 으로 저장한다.
외부 라이브러리 없이 파이썬 표준 라이브러리만 사용.
"""
import hashlib
import os
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
MAX_PER_SECTION = int(os.environ.get("RSS_MAX_PER_SECTION", "5"))
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
# 일부 피드가 막히거나 주소가 바뀌어도 나머지는 계속 수집된다.
ANY = None
DEAL_RE = re.compile(r"레고|lego", re.I)


def youtube(channel_id):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


# 매장·마트별 검색어. '레스'는 레고 스토어 줄임말이라 '레고'와 같이 검색
STORE_QUERIES = ["토이저러스 레고", "레고 스토어", "레스 레고", "이마트 레고", "홈플러스 레고"]
NO_LAND_RE = re.compile(r"^(?!.*레고랜드)(?=.*(?:레고|lego)).+", re.I | re.S)
KUPI = "UCmA7038F43v888Q82sNTNCw"  # 레고도사꾸삐 (@kupibricks)
YT_AGE = 72  # 유튜브는 매일 올라오지 않으니 3일치까지
SALE_RE = re.compile(r"할인|세일|특가|사은품|증정|핫딜|프로모션|쿠폰|최저가|포인트")
NOT_SALE_RE = re.compile(r"^(?!.*(?:할인|세일|특가|사은품|증정|핫딜|프로모션|쿠폰|최저가)).+", re.S)
SOURCES = {
    "kr_deal": [
        # 핫딜 커뮤니티
        ("https://www.ppomppu.co.kr/rss.php?id=ppomppu", "뽐뿌", DEAL_RE),
        ("https://www.ppomppu.co.kr/rss.php?id=ppomppu4", "해외뽐뿌", DEAL_RE),
        ("https://bbs.ruliweb.com/market/board/1020/rss", "루리웹 핫딜", DEAL_RE),
        # 공식몰·대형마트·온라인몰 프로모션 기사
        (gnews("레고 프로모션 OR 사은품 OR 더블포인트 OR 레고스토어 when:3d"), None, LEGO_RE),
        (gnews("레고 (이마트 OR 롯데마트 OR 토이저러스 OR 홈플러스 OR 쿠팡) 할인 when:3d"), None, LEGO_RE),
        # 추천 유튜브: 할인·행사 영상만
        (youtube(KUPI), "유튜브 레고도사꾸삐", SALE_RE, YT_AGE),
        # 네이버 검색 API: 마트·매장 행사 후기, 동호회 카페 제보
        ("naver", "blog", "레고 사은품", LEGO_RE),
        ("naver", "blog", "레고 할인 행사", LEGO_RE),
        ("naver", "cafearticle", "레고 사은품", LEGO_RE),
        ("naver", "cafearticle", "레고 행사", LEGO_RE),
        ("naver", "news", "레고 할인", NO_LAND_RE),
        # 매장·마트별 (블로그 + 카페)
        *[("naver", kind, q, LEGO_RE) for q in STORE_QUERIES for kind in ("blog", "cafearticle")],
    ],
    "new_release": [
        # 해외 레고 전문 매체 (영·독·불) — 신제품 공개가 가장 빠른 곳들
        ("https://www.brickfanatics.com/feed/", "Brick Fanatics", ANY),
        ("https://brickset.com/feed/", "Brickset", ANY),
        ("https://www.thebrickfan.com/feed/", "The Brick Fan", ANY),
        ("https://jaysbrickblog.com/feed/", "Jay's Brick Blog", ANY),
        ("https://www.promobricks.de/feed/", "Promobricks(독일)", ANY),
        ("https://www.hothbricks.com/feed/", "HothBricks(프랑스)", ANY),
        ("https://www.newelementary.com/feeds/posts/default", "New Elementary", ANY),
        (gnews('LEGO "new set" OR revealed OR announced OR "officially revealed" when:2d', "en"), None, LEGO_RE),
        (gnews("레고 신제품 OR 출시 when:3d"), None, LEGO_RE),
        # 추천 유튜브: 할인 영상을 뺀 나머지(신제품·리뷰)
        (youtube(KUPI), "유튜브 레고도사꾸삐", NOT_SALE_RE, YT_AGE),
        ("naver", "news", "레고 신제품", NO_LAND_RE),
    ],
    "kr_news": [
        (gnews("레고 -레고랜드 when:1d"), None, LEGO_RE),
        ("naver", "news", "레고", NO_LAND_RE),
    ],
    "global_news": [
        (gnews("\"LEGO Group\" OR LEGO when:1d", "en"), None, LEGO_RE),
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


ATOM = "{http://www.w3.org/2005/Atom}"
MEDIA = "{http://search.yahoo.com/mrss/}"


def entries(root):
    """RSS <item> 과 Atom <entry>(유튜브 등)를 같은 모양으로 돌려준다."""
    for it in root.iter("item"):
        yield {"title": it.findtext("title"), "link": it.findtext("link"), "pub": it.findtext("pubDate"),
               "desc": it.findtext("description"), "source": it.find("source")}
    for it in root.iter(ATOM + "entry"):
        link_el = it.find(ATOM + "link")
        desc = it.findtext(f"{MEDIA}group/{MEDIA}description") or it.findtext(ATOM + "summary")
        yield {"title": it.findtext(ATOM + "title"), "link": link_el.get("href") if link_el is not None else "",
               "pub": it.findtext(ATOM + "published") or it.findtext(ATOM + "updated"),
               "desc": desc, "source": None}


def parse_date(s):
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_items(url, source_label, title_filter, max_age=None):
    try:
        root = parse_xml(fetch(url))
    except Exception as e:  # 한 소스가 실패해도 계속 진행
        print(f"[warn] {url[:80]} 실패: {e}", file=sys.stderr)
        return []
    now = datetime.now(timezone.utc)
    items = []
    max_age = max_age or MAX_AGE_HOURS
    for it in entries(root):
        title = clean(it["title"])
        link = (it["link"] or "").strip()
        if not title or not link:
            continue
        src = source_label
        src_el = it["source"]
        if src_el is not None and src_el.text:
            src = src_el.text.strip()
            # 구글뉴스 제목 끝의 " - 언론사" 제거
            title = re.sub(r"\s+-\s+" + re.escape(src) + r"$", "", title)
        if title_filter and not title_filter.search(title):
            continue
        if it["pub"]:
            try:
                if now - parse_date(it["pub"]) > timedelta(hours=max_age):
                    continue
            except Exception:
                pass
        summary = clean(it["desc"])
        if summary.startswith(title[:20]):  # 구글뉴스 description은 제목 반복
            summary = ""
        items.append({
            "title": title[:120],
            "summary": summary[:160],
            "url": link,
            "source": src or "",
        })
    return items


# ---------- 네이버 검색 API (NAVER API HUB, 예전 개발자센터 키도 지원) ----------
NAVER_ID = (os.environ.get("NAVER_CLIENT_ID") or "").strip()
NAVER_SECRET = (os.environ.get("NAVER_CLIENT_SECRET") or "").strip()
NAVER_SEEN_PATH = f"{ROOT}/state/naver_seen.json"
NAVER_LABEL = {"blog": "네이버 블로그", "cafearticle": "네이버 카페", "news": "네이버 뉴스"}
_naver_seen = None
_naver_stats = {}


def naver_seen():
    global _naver_seen
    if _naver_seen is None:
        cutoff = (datetime.now() - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")
        _naver_seen = {k: v for k, v in (load_json(NAVER_SEEN_PATH, {}) or {}).items() if v >= cutoff}
    return _naver_seen


def naver_call(kind, query, display=30):
    import json
    q = urllib.parse.urlencode({"query": query, "display": display, "sort": "date"})
    tries = [
        (f"https://naverapihub.apigw.ntruss.com/search/v1/{kind}?{q}",
         {"X-NCP-APIGW-API-KEY-ID": NAVER_ID, "X-NCP-APIGW-API-KEY": NAVER_SECRET}),
        (f"https://openapi.naver.com/v1/search/{kind}.json?{q}",
         {"X-Naver-Client-Id": NAVER_ID, "X-Naver-Client-Secret": NAVER_SECRET}),
    ]
    last = None
    for url, headers in tries:
        try:
            req = urllib.request.Request(url, headers={**headers, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8")).get("items", [])
        except Exception as e:  # API HUB 키가 아니면 예전 주소로 한 번 더
            last = e
    raise RuntimeError(last)


def naver_items(kind, query, title_filter):
    if not (NAVER_ID and NAVER_SECRET):
        return []
    try:
        raw = naver_call(kind, query)
    except Exception as e:
        print(f"[warn] 네이버 {kind} '{query}' 실패: {e}", file=sys.stderr)
        _naver_stats[kind] = _naver_stats.get(kind, 0)
        return []
    now = datetime.now(timezone.utc)
    today = today_kst()
    seen = naver_seen()
    items = []
    for it in raw:
        title = clean(it.get("title"))
        link = (it.get("originallink") or it.get("link") or "").strip()
        desc = clean(it.get("description"))
        if not title or not link or (title_filter and not title_filter.search(title + " " + desc)):
            continue
        # 최근 글만: 블로그는 작성일, 뉴스는 게재 시각, 카페는 '처음 본 날' 기준
        if it.get("postdate"):
            try:
                pd = datetime.strptime(it["postdate"], "%Y%m%d").replace(tzinfo=timezone(timedelta(hours=9)))
                if now - pd > timedelta(hours=60):
                    continue
            except ValueError:
                pass
        elif it.get("pubDate"):
            try:
                if now - parse_date(it["pubDate"]) > timedelta(hours=MAX_AGE_HOURS):
                    continue
            except Exception:
                pass
        if seen.get(link, today) != today:  # 전에 이미 후보로 넘긴 글
            continue
        seen[link] = today
        who = it.get("bloggername") or it.get("cafename") or ""
        src = NAVER_LABEL.get(kind, "네이버") + (f" · {who}" if who else "")
        if kind == "news":
            src = "네이버 뉴스"
        items.append({"title": title[:120], "summary": desc[:160], "url": link, "source": src})
    _naver_stats[kind] = _naver_stats.get(kind, 0) + len(items)
    return items


def key_of(item):
    norm = re.sub(r"\W+", "", item["title"].lower())[:40]
    return hashlib.md5(norm.encode()).hexdigest()[:12]


CANDIDATE_PATH = f"{ROOT}/state/candidates.json"
CANDIDATES_PER_SECTION = 25


def gather(sec):
    """섹션의 모든 소스를 동시에 가져와서 소스별로 번갈아 섞는다(한 곳이 독점하지 않게)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        lists = list(ex.map(lambda src: naver_items(*src[1:]) if src[0] == "naver" else parse_items(*src),
                            SOURCES[sec]))
    mixed, i = [], 0
    while any(i < len(l) for l in lists):
        for l in lists:
            if i < len(l):
                mixed.append(l[i])
        i += 1
    return mixed


def main():
    date = today_kst()
    seen = load_json(SEEN_PATH, {}) or {}
    cutoff = (datetime.now() - timedelta(days=SEEN_KEEP_DAYS)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    used = set()

    # 신제품을 먼저 채워서 해외소식과 중복되지 않게
    order = ["kr_deal", "new_release", "kr_news", "global_news"]
    result, candidates = {}, {}
    for sec in order:
        pool = []
        for item in gather(sec):
            k = key_of(item)
            if k in seen or k in used:
                continue
            used.add(k)
            pool.append(item)
        candidates[sec] = pool[:CANDIDATES_PER_SECTION]
        result[sec] = pool[:MAX_PER_SECTION]

    for sec in order:
        for item in result[sec]:
            seen[key_of(item)] = date

    digest = {
        "date": date,
        "source": "rss",
        "headline": "",
        "sections": [{"key": k, "items": result.get(k, [])} for k, _ in SECTIONS],
    }
    save_json(digest_path("rss", date), digest)
    save_json(SEEN_PATH, seen)
    save_json(CANDIDATE_PATH, {"date": date, "sections": candidates})
    if NAVER_ID:
        save_json(NAVER_SEEN_PATH, naver_seen())
        print("네이버 검색: " + " · ".join(f"{NAVER_LABEL[k]} {_naver_stats.get(k, 0)}건" for k in NAVER_LABEL))
    else:
        print("네이버 검색: 키 없음(NAVER_CLIENT_ID) → 건너뜀")
    print(f"saved {digest_path('rss', date)}: " +
          ", ".join(f"{k}={len(result[k])}/{len(candidates[k])}" for k in order))


if __name__ == "__main__":
    main()

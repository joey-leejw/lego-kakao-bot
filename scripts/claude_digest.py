"""방식 1: Claude가 웹 검색 + 중요도 판단으로 오늘의 레고 다이제스트를 만든다.

GitHub Actions에서 실행. 필요 환경변수:
  ANTHROPIC_API_KEY   Claude API 키 (없으면 아무것도 안 하고 종료 → RSS 다이제스트로 대체)
  CLAUDE_MODEL        (선택) 기본 claude-sonnet-5-5
  CLAUDE_MAX_SEARCHES (선택) 하루 웹 검색 최대 횟수, 기본 12  (검색 1,000회당 $10)
결과: digests/claude/YYYY-MM-DD.json  (성공 시 경로를 stdout 마지막 줄에 출력)
"""
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

from common import ROOT, SECTIONS, digest_path, load_json, save_json, today_kst

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_SEARCHES = int(os.environ.get("CLAUDE_MAX_SEARCHES", "12"))
SEARCH_TOOL = os.environ.get("CLAUDE_SEARCH_TOOL", "web_search_20250305")
HISTORY_DAYS = 7

SYSTEM = """너는 한국 레고 팬을 위한 '레고 데일리' 편집장이다.
독자는 레고를 사고 모으는 한국 성인 팬이다. 매일 '진짜 쓸모 있고 보고 싶은' 소식만 고른다.
웹 검색으로 사실을 확인하고, 확인 못 한 내용은 쓰지 않는다. 출력은 반드시 한국어.

[섹션별 편집 기준]
1) kr_deal — 국내 할인·프로모션 (가장 중요)
   - 우선순위: ①레고 공식몰(lego.com/ko-kr)·레고 공인스토어 프로모션(사은품 GWP, 더블 인사이더 포인트, 시즌 세일, 블랙프라이데이 등)
     ②대형마트 행사(이마트·롯데마트/토이저러스·홈플러스·트레이더스·코스트코) ③온라인몰 기획전(쿠팡·네이버 레고 공식스토어·SSG·11번가·G마켓·컬리 등)
     ④카드사·간편결제 추가 할인. 핫딜 커뮤니티(뽐뿌·루리웹 등)는 위 행사를 발견하는 실마리로 쓴다.
   - '새로 시작한' 또는 '곧 끝나는' 행사를 우선. 행사 기간·대상 세트·할인율/사은품을 반드시 적는다.
   - 단품 1개 짧은 핫딜은 정말 좋은 가격(역대가 수준)일 때만.
   - 사은품 행사는 사은품 세트번호·상당 가격, 최소 구매 금액, 수량 제한(한 가구당 1개 등), '재고 소진 시 조기 종료' 여부를 적는다.
   - 온라인 행사인지 오프라인(매장) 행사인지 channel에 적는다.
   - 후보의 '네이버 블로그·카페' 글은 매장·마트 행사를 찾는 단서다. 체험단·협찬·개인 판매 글은 그대로 싣지 말고,
     공식몰·판매처·기사로 행사를 확인한 뒤 싣는다. 공식 확인이 안 되는 매장 행사는 '매장 제보'라고 밝히고 source에 블로그·카페 이름을 적는다.
   - 국내 행사를 잘 모아 두는 곳: 브릭도감(brickdogam.com/sale/stores). 매일 확인해 새 행사를 찾되,
     반드시 레고 공식몰·판매처 원문으로 확인하고 url·source는 원 판매처로 적는다. 원문 확인이 안 되면 source를 '브릭도감'으로 밝힌다.
     문장·설명은 베끼지 말고 사실(행사명·기간·조건)만 쓴다.
2) new_release — 전 세계 신제품 (공식 발표 > 공식 이미지 공개 > 신뢰도 높은 유출/루머 순)
   - 확인할 곳: LEGO 공식 뉴스룸·lego.com '출시 예정', Brickset, Brick Fanatics, The Brick Fan, Jay's Brick Blog,
     Promobricks(독일), HothBricks(프랑스), New Elementary, LEGO Ideas 공식 발표, BrickLink Designer Program.
   - 후보 중 '유튜브 레고도사꾸삐' 영상은 한국 팬 관점의 신제품·할인 단서다. 영상 제목·설명 속 사실을 웹 검색으로 확인해서 쓰고,
     영상 자체가 볼 만하면(국내 출시 정보, 실물 리뷰) 그 항목의 url을 영상 주소로, source를 '유튜브 레고도사꾸삐'로 적어도 된다.
   - 세트번호·이름·테마·피스 수·가격(현지 통화, 알면 한국 가격)·출시일을 최대한 채운다. 루머면 tag를 '루머'로.
3) kr_news — 국내 소식: 레고코리아, 국내 매장 오픈·행사·전시·팝업, 국내 언론 보도. 레고랜드 테마파크 재무 이슈는 제외.
4) global_news — 해외 소식: LEGO Group 실적·경영·지속가능성·대형 콜라보·소송 등 업계 흐름.

[공통 규칙]
- 섹션당 0~5개. 억지로 채우지 말고 없으면 빈 배열. 중요한 것부터.
- '최근 7일간 이미 보낸 소식' 목록에 있는 것은 제외. 단 내용이 바뀌었으면(가격 인하, 기간 연장, 공식 확정 등) tag '업데이트'로 포함.
- url은 검색으로 실제 확인한 원문 주소만. 추측해서 만들지 않는다.
- title ≤ 45자(핵심이 먼저 보이게), summary ≤ 90자.
- importance: 3=꼭 봐야 함, 2=볼 만함, 1=참고.
- 날짜는 확인되는 대로 YYYY-MM-DD로 적는다(할인 시작·종료일, 출시일, 원문 게재일). 모르면 빈칸.

[국내·해외 소식은 브릭소리 자체 기사로 싣는다]
- 독자가 광고 많은 원문으로 넘어가지 않아도 되도록, 원문을 직접 읽고 '브릭소리' 기사로 다시 쓴다.
- body: 3~4문단, 600~900자. 무슨 일인지 → 핵심 내용(숫자·날짜·세트명) → 한국 팬에게 의미 순서.
  원문 문장을 그대로 옮기지 말고 자기 문장으로 요약한다. 해외 기사는 자연스러운 한국어로 번역·요약한다.
- points: 핵심 3가지(각 40자 이내).
- 출처를 정확히: source=매체명, original_title=원문 제목(원어 그대로), published=원문 게재일, url=원문 주소.
- 원문에 없는 추측·의견은 넣지 않는다. 불확실하면 '~로 알려졌다'처럼 출처의 말임을 밝힌다.
"""

SCHEMA = """마지막에 아래 형식의 JSON만 <json>...</json> 태그 안에 출력해라(설명 없이).
{
 "headline": "오늘 가장 중요한 소식 한 문장(70자 이내)",
 "sections": [
  {"key":"kr_deal","items":[{"title":"","summary":"","url":"","source":"출처명",
     "tag":"공식몰|마트|온라인몰|카드|핫딜|업데이트 중 하나",
     "period":"행사 기간(예: 10/3~10/12, 모르면 빈칸)","start":"YYYY-MM-DD","end":"YYYY-MM-DD(종료일, 모르면 빈칸)",
     "discount":"할인율·사은품 요약(예: 최대 30%)","channel":"온라인|오프라인|온·오프라인",
     "value":"사은품 상당 가격(예: 46,900원 상당)","limit":"조건(예: 21만 원 이상 · 한 가구당 1개 · 재고 소진 시 조기 종료)",
     "importance":3}]},
  {"key":"new_release","items":[{"title":"","summary":"","url":"","source":"",
     "tag":"공식|공개|루머|업데이트","set":"세트번호","theme":"테마","price":"가격","release":"출시일(사람이 읽는 표기)",
     "release_date":"YYYY-MM-DD 또는 YYYY-MM",
     "importance":2}]},
  {"key":"kr_news","items":[{"title":"한국어 제목","summary":"한 줄 요약","url":"원문 주소","source":"매체명",
     "original_title":"원문 제목","published":"YYYY-MM-DD","body":["문단1","문단2","문단3"],
     "points":["핵심1","핵심2","핵심3"],"importance":2}]},
  {"key":"global_news","items":[{"title":"한국어 제목","summary":"한 줄 요약","url":"원문 주소","source":"매체명",
     "original_title":"원문 제목","published":"YYYY-MM-DD","body":["문단1","문단2","문단3"],
     "points":["핵심1","핵심2","핵심3"],"importance":2}]}
 ],
 "calendar": [
  {"date":"YYYY-MM-DD(모르면 YYYY-MM)","set":"세트번호","name":"세트 이름(한국어)","theme":"테마",
   "price":"가격","region":"글로벌|한국|미국 등"}
 ]
}
calendar에는 오늘 이후 약 60일 안에 출시 예정인 주요 세트를 날짜순으로 최대 15개 넣는다(확인된 것만)."""


def recent_history(today):
    """최근 7일 동안 보낸 제목들 (중복 방지용)."""
    titles = []
    for path in sorted(glob.glob(os.path.join(ROOT, "digests", "claude", "*.json")))[-HISTORY_DAYS:]:
        d = load_json(path) or {}
        if d.get("date") == today:
            continue
        for sec in d.get("sections", []):
            for it in sec.get("items", []):
                titles.append(f"[{d['date']}] {it.get('title', '')}")
    return titles


def candidate_text():
    c = load_json(os.path.join(ROOT, "state", "candidates.json"), {}) or {}
    lines = []
    for key, title in SECTIONS:
        items = (c.get("sections") or {}).get(key, [])
        if not items:
            continue
        lines.append(f"## {title} 후보")
        for it in items:
            extra = f" | {it['summary'][:80]}" if it.get("summary") and any(w in (it.get("source") or "") for w in ("유튜브", "네이버")) else ""
            lines.append(f"- {it['title']} | {it.get('source', '')} | {it['url']}{extra}")
    return "\n".join(lines)


def call_api(messages):
    body = {
        "model": MODEL,
        "max_tokens": 16000,
        "system": SYSTEM,
        "messages": messages,
        "tools": [{
            "type": SEARCH_TOOL, "name": "web_search", "max_uses": MAX_SEARCHES,
            "user_location": {"type": "approximate", "city": "Seoul", "country": "KR",
                              "timezone": "Asia/Seoul"},
        }],
    }
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API {e.code}: {e.read().decode(errors='replace')[:500]}")


def run_claude(prompt):
    user = {"role": "user", "content": prompt}
    messages = [user]
    done = []  # pause_turn 동안 쌓인 응답 블록
    usage = {"input_tokens": 0, "output_tokens": 0, "searches": 0}
    for _ in range(6):  # pause_turn 이면 이어서 진행
        res = call_api(messages)
        u = res.get("usage", {})
        usage["input_tokens"] += u.get("input_tokens", 0)
        usage["output_tokens"] += u.get("output_tokens", 0)
        usage["searches"] += (u.get("server_tool_use") or {}).get("web_search_requests", 0)
        done += res.get("content", [])
        if res.get("stop_reason") == "pause_turn":
            messages = [user, {"role": "assistant", "content": done}]
            continue
        text = "".join(b.get("text", "") for b in done if b.get("type") == "text")
        return text, usage
    raise RuntimeError("pause_turn 반복 한도 초과")


def parse_json(text):
    m = re.search(r"<json>\s*(\{.*\})\s*</json>", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("응답에서 JSON을 찾지 못함")
    return json.loads(m.group(1))


def clean_digest(raw, date):
    keys = [k for k, _ in SECTIONS]
    by_key = {s.get("key"): s.get("items") or [] for s in raw.get("sections", [])}
    sections = []
    for k in keys:
        items = []
        for it in by_key.get(k, []):
            url = str(it.get("url", "")).strip()
            if not it.get("title") or not url.startswith("http"):
                continue
            it = {kk: ([str(x).strip() for x in v if str(x).strip()] if isinstance(v, list)
                       else v if isinstance(v, (int, float)) else str(v).strip())
                  for kk, v in it.items() if v not in (None, "", [])}
            if isinstance(it.get("body"), str):
                it["body"] = [p.strip() for p in it["body"].split("\n") if p.strip()]
            items.append(it)
        items.sort(key=lambda x: -int(x.get("importance", 1) or 1))
        sections.append({"key": k, "items": items[:5]})
    cal = [c for c in raw.get("calendar", []) if isinstance(c, dict) and c.get("name")]
    cal.sort(key=lambda c: str(c.get("date", "9999")))
    return {"date": date, "source": "claude", "headline": str(raw.get("headline", ""))[:120],
            "sections": sections, "calendar": cal[:15]}


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY 없음 → Claude 요약 건너뜀")
        return
    date = today_kst()
    hist = recent_history(date)
    prompt = (
        f"오늘은 {date} (한국 시간)이다. 최근 24~48시간의 레고 소식으로 오늘의 다이제스트를 만들어라.\n\n"
        "아래는 RSS로 자동 수집한 후보다. 참고만 하고, 반드시 웹 검색으로 직접 더 찾아 보완·검증해라. "
        "특히 국내 할인(공식몰·마트·온라인몰 프로모션)과 전 세계 신제품은 후보에 없어도 검색해서 찾아라.\n\n"
        f"{candidate_text() or '(후보 없음)'}\n\n"
        "## 최근 7일간 이미 보낸 소식 (제외 대상)\n" + ("\n".join(hist) or "(없음)") + "\n\n" + SCHEMA
    )
    try:
        text, usage = run_claude(prompt)
        digest = clean_digest(parse_json(text), date)
    except Exception as e:
        print(f"::warning::Claude 요약 실패 → 자동 수집본으로 대체: {e}")
        return
    digest["usage"] = {**usage, "model": MODEL}
    path = digest_path("claude", date)
    save_json(path, digest)
    n = sum(len(s["items"]) for s in digest["sections"])
    print(f"Claude 요약 완료: {n}건, 캘린더 {len(digest['calendar'])}건, "
          f"검색 {usage['searches']}회, 토큰 in {usage['input_tokens']:,} / out {usage['output_tokens']:,}")
    print(path)


if __name__ == "__main__":
    main()

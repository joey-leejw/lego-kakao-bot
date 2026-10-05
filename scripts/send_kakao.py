"""다이제스트 JSON을 카카오톡 '나에게 보내기'로 전송.

사용법: python send_kakao.py digests/claude/2026-10-05.json
필요 환경변수:
  KAKAO_REST_API_KEY   카카오 앱 REST API 키
  KAKAO_REFRESH_TOKEN  get_token.py로 발급받은 리프레시 토큰
  KAKAO_CLIENT_SECRET  (앱에서 Client Secret을 켰을 때만)
  GH_PAT               (선택) 리프레시 토큰이 갱신되면 GitHub Secret을 자동 업데이트
  DRY_RUN=1            실제 전송 없이 메시지 내용만 출력
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

from common import SECTION_TITLES, SOURCE_LABELS, load_json, page_name, site_url

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url} → {e.code} {e.read().decode(errors='replace')}")


def get_access_token():
    data = {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_API_KEY"],
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    }
    if os.environ.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    res = post(TOKEN_URL, data)
    new_rt = res.get("refresh_token")
    if new_rt:  # 만료 1개월 전부터 새 리프레시 토큰이 내려옴 → 자동 저장
        if os.environ.get("GH_PAT") and os.environ.get("GITHUB_REPOSITORY"):
            subprocess.run(
                ["gh", "secret", "set", "KAKAO_REFRESH_TOKEN",
                 "--repo", os.environ["GITHUB_REPOSITORY"], "--body", new_rt],
                env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]}, check=True)
            print("리프레시 토큰 갱신 → GitHub Secret 업데이트 완료")
        else:
            print("::warning::새 리프레시 토큰이 발급됐습니다. GH_PAT가 없어 자동 저장 못함. "
                  "get_token.py로 재발급해 KAKAO_REFRESH_TOKEN을 바꿔주세요.")
    return res["access_token"]


def cut(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def link(url):
    return {"web_url": url, "mobile_web_url": url}


def build_messages(d):
    """섹션마다 1개 메시지. 항목 2개 이상이면 리스트형, 1개면 텍스트형."""
    base = f"{site_url()}/{page_name(d)}"
    label = SOURCE_LABELS.get(d["source"], d["source"])
    md = d["date"][5:].replace("-", "/")
    msgs = []
    for sec in d.get("sections", []):
        items = sec.get("items") or []
        if not items:
            continue
        title = SECTION_TITLES.get(sec["key"], sec["key"])
        header = cut(f"{title} · {md} ({label})", 40)
        sec_url = f"{base}#{sec['key']}-0"
        if len(items) >= 2:
            contents = []
            for i, it in enumerate(items[:3]):
                desc = it.get("summary") or it.get("source") or ""
                contents.append({
                    "title": cut(it["title"], 50),
                    "description": cut(desc, 40),
                    "link": link(f"{base}#{sec['key']}-{i}"),
                })
            more = f" (+{len(items) - 3}건)" if len(items) > 3 else ""
            msgs.append({
                "object_type": "list",
                "header_title": header,
                "header_link": link(sec_url),
                "contents": contents,
                "buttons": [{"title": f"전체 보기{more}", "link": link(sec_url)}],
            })
        else:
            it = items[0]
            msgs.append({
                "object_type": "text",
                "text": cut(f"{header}\n\n• {it['title']}\n{it.get('summary', '')}", 200),
                "link": link(sec_url),
                "button_title": "자세히 보기",
            })
    if d.get("headline"):
        msgs.insert(0, {
            "object_type": "text",
            "text": cut(f"🧱 오늘의 레고 한 줄 ({md})\n\n{d['headline']}", 200),
            "link": link(base),
            "button_title": "오늘 소식 전체",
        })
    if not msgs:
        msgs.append({
            "object_type": "text",
            "text": f"🧱 {md} 레고 소식 ({label})\n\n오늘은 새로운 소식이 없어요.",
            "link": link(site_url()),
        })
    return msgs


def text_fallback(tpl):
    """리스트형 전송이 실패할 때 텍스트형으로 대체."""
    lines = [tpl["header_title"], ""] + [f"• {c['title']}" for c in tpl["contents"]]
    return {"object_type": "text", "text": cut("\n".join(lines), 200),
            "link": tpl["header_link"], "button_title": "전체 보기"}


def main():
    path = sys.argv[1]
    d = load_json(path)
    if not d:
        sys.exit(f"다이제스트를 읽을 수 없음: {path}")
    msgs = build_messages(d)
    if os.environ.get("DRY_RUN"):
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
        return
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    for tpl in msgs:
        try:
            post(MEMO_URL, {"template_object": json.dumps(tpl, ensure_ascii=False)}, headers)
        except RuntimeError as e:
            if tpl["object_type"] != "list":
                raise
            print(f"[warn] 리스트형 실패, 텍스트로 재시도: {e}")
            post(MEMO_URL, {"template_object": json.dumps(text_fallback(tpl), ensure_ascii=False)}, headers)
    print(f"카카오톡 전송 완료: {len(msgs)}개 메시지 ({path})")


if __name__ == "__main__":
    main()

"""최초 1회: 카카오 리프레시 토큰 발급 도우미 (내 컴퓨터에서 실행).

1) python3 get_token.py           → 열린 브라우저에서 카카오 로그인/동의
2) 이동된 주소창의  ...?code=XXXX  에서 XXXX 를 복사해 붙여넣기
3) 출력된 refresh_token 을 GitHub Secret KAKAO_REFRESH_TOKEN 에 저장
"""
import json
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://localhost:3000/oauth"  # 카카오 앱에 등록한 Redirect URI와 같아야 함

key = input("REST API 키: ").strip()
secret = input("Client Secret (안 켰으면 엔터): ").strip()

auth_url = "https://kauth.kakao.com/oauth/authorize?" + urllib.parse.urlencode({
    "client_id": key, "redirect_uri": REDIRECT_URI,
    "response_type": "code", "scope": "talk_message"})
print("\n아래 주소가 열립니다. 로그인·동의 후 '연결할 수 없음' 페이지가 떠도 정상입니다.\n" + auth_url)
webbrowser.open(auth_url)

raw = input("\n주소창 전체 또는 code 값을 붙여넣기: ").strip()
code = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query).get("code", [raw])[0]

data = {"grant_type": "authorization_code", "client_id": key,
        "redirect_uri": REDIRECT_URI, "code": code}
if secret:
    data["client_secret"] = secret
req = urllib.request.Request("https://kauth.kakao.com/oauth/token",
                             data=urllib.parse.urlencode(data).encode())
try:
    res = json.loads(urllib.request.urlopen(req).read().decode())
except urllib.error.HTTPError as e:
    raise SystemExit(f"실패: {e.code} {e.read().decode()}")

# 1) 토큰부터 먼저 출력 (테스트 전송이 실패해도 토큰은 남도록)
print("\n받은 권한(scope):", res.get("scope", "(없음)"))
print("\nKAKAO_REFRESH_TOKEN =", res["refresh_token"])
print(f"(유효기간 약 {res.get('refresh_token_expires_in', 0) // 86400}일, 이후 자동 갱신)")

# 2) 테스트 메시지
tpl = {"object_type": "text", "text": "🧱 레고 소식 봇 연결 완료!", "link": {}}
req = urllib.request.Request(
    "https://kapi.kakao.com/v2/api/talk/memo/default/send",
    data=urllib.parse.urlencode({"template_object": json.dumps(tpl, ensure_ascii=False)}).encode(),
    headers={"Authorization": f"Bearer {res['access_token']}"})
try:
    urllib.request.urlopen(req)
    print("\n✅ 카카오톡 '나와의 채팅'에 테스트 메시지를 보냈습니다.")
except urllib.error.HTTPError as e:
    print(f"\n❌ 테스트 메시지 실패: {e.code} {e.read().decode(errors='replace')}")
    if "talk_message" not in res.get("scope", ""):
        print("→ 원인: 카카오톡 메시지 전송 권한(talk_message)이 없습니다. "
              "동의항목에서 '카카오톡 메시지 전송'을 켜고, 로그인 동의 화면에서 체크했는지 확인하세요.")

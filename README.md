# 🧱 레고 데일리 카톡 봇

매일 점심 12시쯤 카카오톡 **나와의 채팅**으로 레고 소식(국내 할인 · 국내 소식 · 해외 소식 · 신제품)을 보내줍니다.
두 가지 방식이 같이 돌아가서 매일 2세트를 받고, 비교해 보고 하나만 남기면 됩니다.

| | 방식 1: Claude 요약 | 방식 2: 자동 스크립트 |
|---|---|---|
| 만드는 곳 | Claude 예약 작업(11:45) → GitHub에 요약 업로드 | GitHub Actions(12:00) RSS 수집 |
| 품질 | 웹 검색 + 요약·가격 정리 | 제목 목록 위주 |
| 비용 | Claude 사용량 차감 | 완전 무료 |

```
[Claude 11:45] ─┐
                ├─> GitHub 저장소 ─> 웹페이지(github.io) 갱신 ─> 카카오 '나에게 보내기'
[Actions 12:00]─┘
```
> 카카오 메시지 링크는 앱에 **등록한 도메인만** 열립니다. 그래서 기사 링크는 github.io 페이지에 모아두고, 카톡에서는 그 페이지로 연결합니다.

---

## 1단계. 카카오 앱 만들기 (10분)

1. https://developers.kakao.com 로그인 → **내 애플리케이션 → 애플리케이션 추가하기** (이름: 레고봇)
2. **앱 키**에서 `REST API 키` 복사해 두기
3. **카카오 로그인 → 활성화 설정 ON**
4. **앱 → 플랫폼 키 → REST API 키**를 눌러 **리다이렉트 URI**에 `http://localhost:3000/oauth` 등록
5. **카카오 로그인 → 동의항목 → 카카오톡 메시지 전송(talk_message)** → *선택 동의*로 설정
6. **앱 → 제품 링크 관리 → 웹 도메인**에 `https://<깃허브아이디>.github.io` 등록 (소문자, 기본 도메인으로 선택)
7. **앱 → 플랫폼 키 → REST API 키** 화면에 Client Secret이 켜져 있으면 코드 값을 복사해 두기 (꺼져 있으면 생략)

## 2단계. 리프레시 토큰 받기 (내 맥에서 1회)

```bash
cd lego-kakao-bot/scripts
python3 get_token.py
```
- 브라우저에서 로그인·동의 → "사이트에 연결할 수 없음"이 떠도 정상 → **주소창 전체를 복사**해 붙여넣기
- 카톡 '나와의 채팅'에 "연결 완료!"가 오면 성공. 출력된 `KAKAO_REFRESH_TOKEN` 값을 복사.

## 3단계. GitHub 저장소 만들기

1. GitHub에서 **새 저장소 `lego-kakao-bot`** 생성 (**Public** — 무료 GitHub Pages 사용. 비밀값은 저장소에 안 들어감)
2. 이 폴더 전체를 업로드 (웹에서 *Add file → Upload files*로 드래그해도 됨. `.github` 폴더 포함 확인)
3. **Settings → Pages → Source: GitHub Actions**
4. **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|---|---|
| `KAKAO_REST_API_KEY` | 1단계 REST API 키 |
| `KAKAO_REFRESH_TOKEN` | 2단계 토큰 |
| `KAKAO_CLIENT_SECRET` | (켰을 때만) |
| `GH_PAT` | 아래 토큰 A (토큰 자동 갱신용, 권장) |

### 개인 액세스 토큰(PAT) 2개 만들기
GitHub → Settings → Developer settings → **Fine-grained tokens → Generate new token**, *Only select repositories: lego-kakao-bot*, 만료 1년

- **토큰 A (GH_PAT)**: Repository permissions → **Secrets: Read and write** → 위 Secret에 저장
- **토큰 B (Claude용)**: Repository permissions → **Contents: Read and write** → Claude에게 전달

## 4단계. 테스트

- **Actions 탭 → 레고 데일리 소식 → Run workflow (mode: rss)** → 1~2분 뒤 카톡 도착 확인
- 이후 매일 12시 자동 실행 (GitHub 사정상 5~20분 늦을 수 있음)

## 5단계. Claude 예약 작업 연결

Claude에게 **깃허브 아이디, 저장소 이름, 토큰 B**를 알려주면 매일 11:45 예약 작업을 등록합니다. (`claude_task_prompt.md` 내용으로 실행)

---

## 알아두기
- **리프레시 토큰 유효기간 2개월**: 만료 1개월 전부터 실행 시 새 토큰이 나오고 `GH_PAT`가 있으면 자동 저장됩니다. GH_PAT가 없으면 2달마다 2단계를 다시 하세요.
- '나와의 채팅'은 알림이 조용할 수 있습니다. 카톡에서 나와의 채팅을 **상단 고정**해 두면 편합니다.
- 한쪽 방식만 남기려면: 방식 2 끄기 → 워크플로 파일의 `schedule:` 두 줄 삭제 / 방식 1 끄기 → Claude 예약 작업 삭제
- 지난 소식 모아보기: `https://<아이디>.github.io/lego-kakao-bot/`

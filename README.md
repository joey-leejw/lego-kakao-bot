# 🧱 레고 데일리 카톡 봇

매일 낮 12시쯤 카카오톡 **나와의 채팅**으로 레고 소식을 보내주고, 같은 내용을 웹페이지(`https://joey-leejw.github.io/lego-kakao-bot/`)에도 올립니다.

## 매일 이렇게 돌아가요 (11:30 시작)

1. **후보 수집**: 핫딜 커뮤니티, 레고 프로모션 기사, 해외 레고 전문 매체 7곳(영·독·불)의 RSS에서 후보를 모아요
2. **Claude 요약**: Claude가 후보를 참고하고 **직접 웹 검색**도 해요. 중요한 것만 골라 한국어로 정리하고, 지난 7일간 보낸 소식은 빼요
   - 국내 할인: 레고 공식몰 → 대형마트 → 온라인몰 → 카드사 순으로 행사 기간과 할인율을 정리
   - 신제품: 전 세계 공식 발표·공개·루머를 구분하고 **출시 캘린더(앞으로 60일)**를 만들어요
3. **썸네일**: 기사마다 대표 이미지를 찾아 붙여요
4. **웹페이지 갱신 → 카톡 전송**

Claude 키가 없거나 요약이 실패하면, 자동으로 RSS 수집본을 대신 보내요.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `scripts/collect_rss.py` | RSS 후보 수집 |
| `scripts/claude_digest.py` | Claude 웹 검색 + 요약 (편집 기준은 파일 안 `SYSTEM` 글에 있음) |
| `scripts/enrich_images.py` | 썸네일 찾기 |
| `scripts/build_site.py` | 웹페이지 생성 (오늘 / 지난 소식 + 검색) |
| `scripts/send_kakao.py` | 카톡 전송 |
| `scripts/get_token.py` | 카카오 토큰 최초 발급 (내 컴퓨터에서 1회) |

## 비밀값 (Settings → Secrets and variables → Actions → Secrets)

| 이름 | 값 |
|---|---|
| `KAKAO_REST_API_KEY` | 카카오 REST API 키 |
| `KAKAO_REFRESH_TOKEN` | get_token.py로 받은 토큰 (자동 갱신됨) |
| `KAKAO_CLIENT_SECRET` | 카카오 Client Secret (켠 경우) |
| `GH_PAT` | 카카오 토큰 자동 갱신용 GitHub 토큰 |
| `ANTHROPIC_API_KEY` | Claude API 키 |

## 선택 설정 (같은 화면 → Variables 탭)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | 더 저렴하게: `claude-haiku-4-5-20251001` |
| `CLAUDE_MAX_SEARCHES` | `12` | 하루 웹 검색 최대 횟수 (1,000회당 $10) |

## 수동 실행
**Actions → 레고 데일리 소식 → Run workflow**를 누르세요.
- `auto`: Claude 요약 (실패하면 자동 수집본)
- `rss`: 자동 수집만

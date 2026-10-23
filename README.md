# 코인니스 관심 코인 속보 알림

코인니스 속보(https://coinness.com/news) 중 아래 소식만 골라 휴대폰 푸시로 보냅니다.

- 관심 코인: NEAR, HBAR(헤데라), ONDO, ALGO(알고랜드), LINK(체인링크), AVAX(아발란체), SUI, DOGE
- 상장폐지 관련: 상장폐지, 상폐, 거래지원 종료, 유의종목 지정, 디리스팅

코인 판별은 코인니스가 속보마다 붙이는 코인 코드를 우선 쓰고, 제목·본문의 티커/코인 이름도 함께 봅니다.
코인을 바꾸려면 `coinness_alert.py`의 `COINS`, 키워드는 `DELIST_KEYWORDS`를 고치면 됩니다.

## 1. 휴대폰 알림 받기 (ntfy, 가입 불필요)

1. 앱스토어/플레이스토어에서 **ntfy** 설치
2. 앱에서 `+` → 토픽 이름 입력 (남이 못 맞히게 길게, 예: `coinness-pro-7x9k2q`) → 구독
3. 이 토픽 이름이 `NTFY_TOPIC` 값입니다.

텔레그램을 원하면 @BotFather로 봇을 만들어 토큰을 받고, 봇에게 아무 메시지나 보낸 뒤
`https://api.telegram.org/bot<토큰>/getUpdates`에서 `chat.id`를 확인해 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`로 씁니다.

## 2-A. GitHub Actions로 실행 (PC 꺼져 있어도 동작, 무료)

1. GitHub에 새 저장소를 만들고 이 폴더의 파일(`.github` 폴더 포함)을 올립니다.
   공개(public) 저장소면 실행 시간 무제한 무료, 비공개면 월 2,000분 무료 한도(5분마다 실행 시 초과 가능)라 공개를 권장합니다. 토픽/토큰은 코드가 아니라 Secrets에 들어가므로 노출되지 않습니다.
2. 저장소 Settings → Secrets and variables → Actions → New repository secret 에서 `NTFY_TOPIC` 추가
3. Actions 탭 → coinness-alert → Run workflow 로 한 번 실행해 확인
4. 이후 5분마다 자동 실행됩니다. (GitHub 스케줄은 몇 분씩 늦어질 수 있음)

## 2-B. 내 PC/서버에서 상시 실행 (1분 간격, 더 빠름)

```bash
NTFY_TOPIC=coinness-pro-7x9k2q python3 coinness_alert.py
```

Python 3.8+ 표준 라이브러리만 사용합니다. `python3 coinness_alert.py --test` 는 최근 속보 중 걸러지는 것만 출력합니다(알림 없음).

## 알림 테스트

Actions 탭 → coinness-alert → Run workflow 에서 **테스트 알림만 보내기**를 체크하고 실행하면 휴대폰에 테스트 알림이 1개 옵니다.

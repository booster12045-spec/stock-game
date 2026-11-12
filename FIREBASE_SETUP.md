# Firebase 설정

웹앱과 Pygame 앱은 같은 Firebase 프로젝트와 Firestore 컬렉션을 사용합니다. Google 계정마다 `players/{uid}` 프로필 하나와 `rankings/{uid}` 랭킹 문서 하나를 저장합니다. 랭킹 저장 시 기존 문서를 새 최고 현금 기록으로 갱신합니다.

## Firebase 프로젝트 준비

1. Firebase Console에서 프로젝트를 만들거나 기존 프로젝트를 엽니다.
2. Authentication에서 Google 로그인 제공업체를 사용 설정합니다.
3. Authentication의 승인된 도메인에 `localhost`와 실제 웹앱을 올릴 도메인을 추가합니다.
4. Cloud Firestore 데이터베이스를 만들고 저장소의 `firestore.rules`를 게시합니다.
5. Firebase 프로젝트 설정 > 내 앱에서 웹 앱을 등록하고 웹 앱 설정 객체의 `apiKey`, `authDomain`, `projectId`, `appId`를 복사해 `firebase_config.js`의 값에 입력합니다.

Firebase 웹 설정의 API 키는 클라이언트 앱을 식별하기 위한 값입니다. 서비스 계정 키나 비밀키를 브라우저 코드에 넣지 말고, 데이터 접근은 Firestore 규칙으로 보호하세요.

## 웹앱 실행

저장소 폴더에서 다음 명령을 실행하고 브라우저에서 `http://localhost:8000`을 엽니다.

```powershell
python -m http.server 8000
```

브라우저 ES 모듈은 `file://` 주소에서 제한될 수 있으므로 로컬 웹 서버로 실행합니다. 웹앱은 Firebase JavaScript SDK를 Google CDN에서 가져오기 때문에 인터넷 연결이 필요합니다. 정적 호스팅에 저장소의 웹 파일을 올려도 됩니다.

## Pygame 데스크톱 앱 설정

기존 `파이썬_주식게임_UTF_8저장본.py`도 계속 사용할 수 있습니다.

1. Google Cloud Console의 API 및 서비스 > 사용자 인증 정보에서 OAuth 클라이언트 ID를 만들고 애플리케이션 유형을 **데스크톱 앱**으로 선택합니다.
2. `firebase_config.example.json`을 `firebase_config.json`으로 복사하고 Firebase 웹 API 키, 프로젝트 ID, Google 데스크톱 OAuth 클라이언트 ID를 입력합니다.
3. Python 환경에 `pygame`을 설치하고 게임 파일을 실행합니다.

## 랭킹 동작과 한계

- 최초 Google 로그인 후 닉네임을 정합니다. 이후 같은 계정은 저장된 닉네임을 불러옵니다.
- 랭킹에는 보유 현금 기준 상위 20개 기록을 표시합니다.
- `랭킹 등재` 후 저장을 확인하면 계정의 이전 기록을 갱신하고 새 게임을 시작합니다.
- 게임 점수는 클라이언트에서 전달되므로 엄격한 부정 방지 기능은 아닙니다. 공개 경쟁 랭킹으로 운영할 때는 서버 측 검증을 추가해야 합니다.

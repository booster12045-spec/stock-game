# 주식 투자 게임

브라우저 웹앱과 기존 Pygame 버전을 함께 제공합니다. 웹앱은 별도의 빌드 도구 없이 정적 파일로 동작합니다.

## 웹앱 시작

1. `firebase_config.js`의 `apiKey`, `authDomain`, `projectId`, `appId`를 Firebase 웹 앱 설정값으로 바꿉니다.
2. Firebase Authentication에서 Google 로그인을 켜고, Cloud Firestore를 만든 뒤 `firestore.rules`를 게시합니다.
3. 저장소 폴더에서 아래 명령을 실행합니다.

   ```powershell
   python -m http.server 8000
   ```

4. 브라우저에서 `http://localhost:8000`을 엽니다. 브라우저에서 로그인하려면 Firebase Authentication의 승인된 도메인에 `localhost`와 배포 도메인을 추가해야 합니다.

`index.html`을 파일 탐색기에서 직접 여는 `file://` 방식은 ES 모듈 로딩이 제한될 수 있어 로컬 웹 서버를 사용합니다. 배포할 때는 이 폴더를 Firebase Hosting이나 다른 정적 호스팅에 올리면 됩니다.

## 게임

Google 계정으로 로그인한 뒤 처음 한 번 닉네임을 설정합니다. 가상 주가와 뉴스는 1초마다 갱신됩니다. 랭킹 점수는 보유 현금의 최고 기록이며, 계정당 한 문서를 사용해 새로 등재할 때 기존 기록을 갱신합니다. 저장을 확정하면 현재 게임을 초기화하고 새 게임을 시작합니다.

Firebase 프로젝트 생성, 보안 규칙, 기존 데스크톱 게임 설정은 [FIREBASE_SETUP.md](FIREBASE_SETUP.md)를 참고하세요.

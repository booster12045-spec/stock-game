import random
import json
import hashlib
import base64
import secrets
import threading
import urllib.parse
import urllib.request
import urllib.error
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
import time
from collections import deque

import pygame


WIDTH, HEIGHT = 1320, 930
BG = (15, 21, 34)
PANEL = (25, 33, 49)
PANEL2 = (32, 42, 61)
LINE = (51, 63, 83)
WHITE = (237, 242, 250)
MUTED = (148, 163, 185)
GREEN = (57, 203, 142)
RED = (245, 103, 117)
BLUE = (92, 151, 255)
GOLD = (255, 205, 92)

CONFIG_PATH = Path(__file__).with_name("firebase_config.json")


class FirebaseService:
    """Google OAuth and Firebase Auth/Firestore REST client."""
    def __init__(self):
        if not CONFIG_PATH.exists():
            raise RuntimeError("firebase_config.json 설정 파일이 없습니다. FIREBASE_SETUP.md 안내를 따라 설정해 주세요.")
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.api_key = config.get("api_key", "").strip()
        self.project_id = config.get("project_id", "").strip()
        self.client_id = config.get("google_oauth_client_id", "").strip()
        if not all((self.api_key, self.project_id, self.client_id)):
            raise RuntimeError("firebase_config.json에 api_key, project_id, google_oauth_client_id를 입력해 주세요.")
        self.id_token = None
        self.refresh_token = None
        self.token_expires_at = 0
        self.uid = None
        self.email = None

    def _json_request(self, url, data=None, method=None, headers=None):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(detail).get("error", {}).get("message", detail)
            except (ValueError, AttributeError):
                pass
            raise RuntimeError(f"Firebase 요청 실패: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"인터넷 연결을 확인해 주세요: {exc.reason}") from exc

    def google_sign_in(self):
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        callback = {}
        ready = threading.Event()

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(handler):
                parsed = urllib.parse.urlparse(handler.path)
                params = urllib.parse.parse_qs(parsed.query)
                callback.update({key: values[0] for key, values in params.items()})
                handler.send_response(200)
                handler.send_header("Content-Type", "text/html; charset=utf-8")
                handler.end_headers()
                handler.wfile.write("<meta charset='utf-8'><h2>로그인 완료</h2><p>이 창을 닫고 주식 게임으로 돌아가세요.</p>".encode())
                ready.set()
            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
        server.timeout = 1
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        params = {
            "client_id": self.client_id, "redirect_uri": redirect_uri,
            "response_type": "code", "scope": "openid email profile",
            "state": state, "code_challenge": challenge,
            "code_challenge_method": "S256", "prompt": "select_account",
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        webbrowser.open(auth_url)
        try:
            while not ready.is_set():
                server.handle_request()
        finally:
            server.server_close()
        if callback.get("state") != state or "code" not in callback:
            raise RuntimeError("Google 로그인이 취소되었거나 확인에 실패했습니다.")
        token = self._json_request("https://oauth2.googleapis.com/token", {
            "client_id": self.client_id, "code": callback["code"],
            "code_verifier": verifier, "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        })
        # Firebase accepts a Google OAuth access token here; using it avoids
        # requiring the desktop OAuth client's ID-token audience to match the
        # web client ID configured by Firebase Authentication.
        idp = urllib.parse.urlencode({"access_token": token["access_token"], "providerId": "google.com"})
        result = self._json_request(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={self.api_key}",
            {"postBody": idp, "requestUri": redirect_uri, "returnIdpCredential": True, "returnSecureToken": True},
        )
        self.id_token = result["idToken"]
        self.refresh_token = result["refreshToken"]
        self.token_expires_at = time.monotonic() + int(result.get("expiresIn", "3600"))
        self.uid = result["localId"]
        self.email = result.get("email", "")

    def _auth(self):
        if self.token_expires_at and time.monotonic() >= self.token_expires_at - 60:
            token = self._json_request(f"https://securetoken.googleapis.com/v1/token?key={self.api_key}", {
                "grant_type": "refresh_token", "refresh_token": self.refresh_token,
            }, method="POST")
            self.id_token = token["id_token"]
            self.refresh_token = token.get("refresh_token", self.refresh_token)
            self.token_expires_at = time.monotonic() + int(token.get("expires_in", "3600"))
        return {"Authorization": f"Bearer {self.id_token}"}

    def _document_url(self, collection, document_id):
        return f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents/{collection}/{urllib.parse.quote(document_id, safe='')}"

    def get_profile(self):
        try:
            doc = self._json_request(self._document_url("players", self.uid), headers=self._auth())
            return doc.get("fields", {}).get("nickname", {}).get("stringValue")
        except RuntimeError as exc:
            if "NOT_FOUND" in str(exc):
                return None
            raise

    def set_nickname(self, nickname):
        fields = {"nickname": {"stringValue": nickname}, "email": {"stringValue": self.email or ""}}
        self._json_request(self._document_url("players", self.uid), {"fields": fields}, method="PATCH", headers=self._auth())

    def get_leaderboard(self):
        url = f"https://firestore.googleapis.com/v1/projects/{self.project_id}/databases/(default)/documents:runQuery"
        query = {"structuredQuery": {
            "from": [{"collectionId": "rankings"}],
            "orderBy": [{"field": {"fieldPath": "score"}, "direction": "DESCENDING"}],
            "limit": 20,
        }}
        rows = self._json_request(url, query, method="POST", headers=self._auth())
        results = []
        for row in rows:
            doc = row.get("document")
            if not doc:
                continue
            fields = doc.get("fields", {})
            results.append({
                "nickname": fields.get("nickname", {}).get("stringValue", "익명"),
                "score": int(fields.get("score", {}).get("integerValue", "0")),
                "updated_at": fields.get("updatedAt", {}).get("timestampValue", ""),
                "uid": doc["name"].rsplit("/", 1)[-1],
            })
        return results

    def save_score(self, nickname, score):
        fields = {
            "nickname": {"stringValue": nickname},
            "score": {"integerValue": str(int(score))},
            "updatedAt": {"timestampValue": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        }
        self._json_request(self._document_url("rankings", self.uid), {"fields": fields}, method="PATCH", headers=self._auth())

NAMES = ["삼성전자", "애플", "테슬라", "아마존", "로블록스", "SK하이닉스", "대한항공", "코스트코", "코카콜라", "한국전력"]
PRICES = [270500, 445969, 668437, 395650, 64184, 1819000, 26050, 1571201, 121058, 38750]
RANGES = [(-2, 2), (-3, 3), (-12, 12), (-5, 5), (-15, 15), (-7, 7), (-6, 6), (-2, 2), (-1, 1), (-4, 4)]
NEWS_HEADLINES = [
    (["갤럭시 신제품 사전 예약 판매 호조", "차세대 메모리 공급 계약 확대", "AI 반도체 수요 증가에 실적 기대감"], ["메모리 가격 약세에 수익성 우려", "신제품 출시 일정 조정 가능성 제기", "반도체 업황 둔화 전망에 투자심리 위축"]),
    (["신형 아이폰 공개 후 초기 판매 호조", "서비스 부문 매출 성장세 지속", "차세대 기기 공급망 확대"], ["주요 시장 스마트폰 판매 둔화", "앱스토어 규제 강화 가능성 부각", "신제품 생산 비용 증가 우려"]),
    (["신형 전기차 주문량 예상치 상회", "자율주행 기능 업데이트 공개", "배터리 생산 효율 개선 발표"], ["전기차 가격 인하로 수익성 우려", "신차 출시 일정 지연 가능성", "주요 시장 판매량 감소 전망"]),
    (["클라우드 사업 성장에 실적 기대", "물류 자동화 투자 확대 발표", "신규 AI 서비스 이용 증가"], ["물류 비용 증가로 마진 부담", "클라우드 시장 경쟁 심화", "대형 투자 계획에 비용 우려"]),
    (["신규 게임 동시 접속자 기록 경신", "인기 콘텐츠 업데이트 호평", "해외 이용자 증가세 확인"], ["일부 지역 이용자 성장 둔화", "신작 출시 일정 변경", "콘텐츠 운영 비용 증가 우려"]),
    (["고대역폭 메모리 공급 확대 기대", "AI 서버용 메모리 수요 급증", "차세대 메모리 양산 계획 발표"], ["메모리 가격 조정 가능성 제기", "생산 설비 투자 부담 확대", "주요 고객사 재고 조정 소식"]),
    (["국제선 여객 수요 회복세 지속", "신규 노선 취항으로 예약 증가 기대", "화물 사업 매출 증가세 확인"], ["항공유 가격 상승으로 비용 부담", "운임 경쟁 심화에 수익성 우려", "일부 노선 운항 조정 발표"]),
    (["회원 갱신율 상승으로 매출 기대", "온라인 주문 증가세 확인", "신규 점포 출점 계획 공개"], ["소비 둔화로 객단가 하락 우려", "인건비와 물류비 부담 확대", "일부 상품 가격 인하 검토"]),
    (["신규 음료 제품 출시 계획 발표", "해외 시장 판매량 증가", "원재료 비용 안정으로 수익 개선 기대"], ["주요 원재료 가격 상승 우려", "일부 시장 판매 감소", "환율 변동에 비용 부담 확대"]),
    (["전력 수요 증가로 판매량 확대 기대", "연료비 안정에 실적 개선 전망", "전력망 투자 계획 발표"], ["연료비 상승에 비용 부담", "전력 요금 조정 지연 우려", "설비 정비 비용 증가 전망"]),
]


def font(size, bold=False):
    path = r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf"
    try:
        return pygame.font.Font(path, size)
    except (OSError, pygame.error):
        return pygame.font.SysFont("malgungothic,arial", size, bold=bold)


def won(value):
    return f"{int(value):,}원"


class StockGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("주식 투자 게임")
        display_info = pygame.display.Info()
        available_width = display_info.current_w or WIDTH
        available_height = max(1, (display_info.current_h or HEIGHT) - 80)
        scale = min(1.0, available_width / WIDTH, available_height / HEIGHT)
        self.window = pygame.display.set_mode((round(WIDTH * scale), round(HEIGHT * scale)), pygame.RESIZABLE)
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.f = font(17)
        self.small = font(14)
        self.medium = font(20, True)
        self.title = font(29, True)
        self.large = font(31, True)
        self.cash = 5_000_000
        self.holdings = [0] * len(NAMES)
        self.cost_basis = [0.0] * len(NAMES)
        self.realized_profit = [0.0] * len(NAMES)
        self.history = [[float(price)] for price in PRICES]
        self.trend_direction = [0] * len(NAMES)
        self.trend_remaining = [0] * len(NAMES)
        self.trend_duration = [0] * len(NAMES)
        self.trend_strength = [0.0] * len(NAMES)
        self.bubble_remaining = [0] * len(NAMES)
        self.selected = 0
        self.quantity = "1"
        self.input_active = False
        self.message = ""
        self.message_color = MUTED
        self.message_started = None
        self.news = [deque(maxlen=5) for _ in NAMES]
        self.latest_news_type = [None] * len(NAMES)
        self.add_news(0, True, "갤럭시 신제품 공개 기대감에 관심 집중")
        self.add_news(5, True, "AI 메모리 수요 확대 전망")
        self.add_news(2, False, "전기차 가격 경쟁 심화 우려")
        self.last_update = time.monotonic()
        self.scroll = 0
        self.buy_rect = pygame.Rect(894, 615, 170, 55)
        self.sell_rect = pygame.Rect(1078, 615, 170, 55)
        self.minus_rect = pygame.Rect(894, 535, 48, 48)
        self.plus_rect = pygame.Rect(1200, 535, 48, 48)
        self.qty_rect = pygame.Rect(954, 535, 236, 48)
        self.rows_rect = pygame.Rect(32, 166, 330, 556)
        self.firebase = None
        self.nickname = ""
        self.view = "login"
        self.auth_error = ""
        self.nickname_input = ""
        self.confirm_action = None
        self.leaderboard = []
        self.leaderboard_error = ""
        self.login_rect = pygame.Rect(475, 490, 370, 62)
        self.nickname_rect = pygame.Rect(475, 470, 370, 56)
        self.nickname_submit_rect = pygame.Rect(475, 550, 370, 58)
        self.ranking_tab_rect = pygame.Rect(730, 38, 150, 42)
        self.enroll_rect = pygame.Rect(1076, 116, 172, 42)
        self.confirm_save_rect = pygame.Rect(600, 510, 190, 54)
        self.confirm_cancel_rect = pygame.Rect(810, 510, 190, 54)
        self.best_score = self.cash
        self.best_time = time.strftime("%Y-%m-%d %H:%M:%S")

    def reset_game(self):
        PRICES[:] = [270500, 445969, 668437, 395650, 64184, 1819000, 26050, 1571201, 121058, 38750]
        self.cash = 5_000_000
        self.holdings = [0] * len(NAMES)
        self.cost_basis = [0.0] * len(NAMES)
        self.realized_profit = [0.0] * len(NAMES)
        self.history = [[float(price)] for price in PRICES]
        self.trend_direction = [0] * len(NAMES)
        self.trend_remaining = [0] * len(NAMES)
        self.trend_duration = [0] * len(NAMES)
        self.trend_strength = [0.0] * len(NAMES)
        self.bubble_remaining = [0] * len(NAMES)
        self.news = [deque(maxlen=5) for _ in NAMES]
        self.latest_news_type = [None] * len(NAMES)
        self.add_news(0, True, "갤럭시 신제품 공개 기대감에 관심 집중")
        self.add_news(5, True, "AI 메모리 수요 확대 전망")
        self.add_news(2, False, "전기차 가격 경쟁 심화 우려")
        self.selected = 0
        self.quantity = "1"
        self.best_score = self.cash
        self.best_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.last_update = time.monotonic()
        self.view = "game"
        self.set_message("새 게임을 시작했습니다.", GREEN)

    def begin_google_login(self):
        try:
            self.firebase = FirebaseService()
            self.firebase.google_sign_in()
            nickname = self.firebase.get_profile()
            if nickname:
                self.nickname = nickname
                self.view = "game"
                self.set_message(f"{nickname}님, 로그인했습니다.", GREEN)
            else:
                self.view = "nickname"
        except Exception as exc:
            self.auth_error = str(exc)

    def submit_nickname(self):
        nickname = self.nickname_input.strip()
        if not 2 <= len(nickname) <= 12:
            self.auth_error = "닉네임은 2~12자로 입력해 주세요."
            return
        try:
            self.firebase.set_nickname(nickname)
            self.nickname = nickname
            self.auth_error = ""
            self.view = "game"
            self.set_message(f"{nickname}님, 게임을 시작합니다.", GREEN)
        except Exception as exc:
            self.auth_error = str(exc)

    def refresh_leaderboard(self):
        try:
            self.leaderboard = self.firebase.get_leaderboard()
            self.leaderboard_error = ""
        except Exception as exc:
            self.leaderboard_error = str(exc)

    def enroll_score(self):
        try:
            self.firebase.save_score(self.nickname, self.best_score)
            self.reset_game()
        except Exception as exc:
            self.view = "game"
            self.set_message(str(exc), RED)

    def update_best_score(self):
        if self.cash > self.best_score:
            self.best_score = self.cash
            self.best_time = time.strftime("%Y-%m-%d %H:%M:%S")

    def price(self, i):
        return PRICES[i]

    def total_assets(self):
        return self.cash + sum(self.holdings[i] * PRICES[i] for i in range(len(NAMES)))

    def change_quantity(self, amount):
        try:
            n = int(self.quantity or "0")
        except ValueError:
            n = 0
        self.quantity = str(max(1, min(9999, n + amount)))

    def trade(self, buy):
        try:
            qty = int(self.quantity)
        except ValueError:
            qty = 0
        if qty <= 0:
            self.set_message("주문 수량은 1주 이상이어야 합니다.", RED)
            return
        i = self.selected
        amount = int(PRICES[i]) * qty
        if buy:
            if amount > self.cash:
                self.set_message("매수할 수 없습니다.", RED)
                return
            self.cash -= amount
            self.holdings[i] += qty
            self.cost_basis[i] += amount
            self.set_message(f"{NAMES[i]} {qty:,}주를 매수했습니다.", GREEN)
        else:
            if qty > self.holdings[i]:
                self.set_message("보유 주식 수가 부족합니다.", RED)
                return
            average_cost = self.cost_basis[i] / self.holdings[i]
            removed_cost = average_cost * qty
            self.holdings[i] -= qty
            self.cost_basis[i] -= removed_cost
            self.realized_profit[i] += amount - removed_cost
            if self.holdings[i] == 0:
                self.cost_basis[i] = 0.0
            self.cash += amount
            self.set_message(f"{NAMES[i]} {qty:,}주를 매도했습니다.", GREEN)

    def set_message(self, message, color):
        self.message, self.message_color = message, color
        self.message_started = time.monotonic()

    def draw_trade_message(self, pos):
        if not self.message or self.message_started is None:
            return
        elapsed = time.monotonic() - self.message_started
        if elapsed >= 4:
            return
        alpha = 255 if elapsed < 2 else round(255 * (4 - elapsed) / 2)
        text = self.message
        if self.small.size(text)[0] > 302:
            while text and self.small.size(text + "...")[0] > 302:
                text = text[:-1]
            text += "..."
        image = self.small.render(text, True, self.message_color)
        image.set_alpha(alpha)
        self.screen.blit(image, pos)

    def duration_for_news(self, headline, positive):
        duration_rules = [
            (("기록 경신", "계약 확대", "수요 급증", "매출 성장", "판매 호조", "공급 확대"), (24, 40)),
            (("비용 부담", "경쟁 심화", "규제 강화", "재고 조정", "판매 감소", "수요 둔화"), (20, 36)),
            (("출시", "공개", "업데이트", "신규 노선", "출점"), (14, 26)),
            (("계획", "기대", "전망", "호평"), (10, 20)),
        ]
        for keywords, duration_range in duration_rules:
            if any(keyword in headline for keyword in keywords):
                return random.randint(*duration_range)
        return random.randint(12, 25)

    def add_news(self, index, positive, headline=None, kind=None, duration=None):
        if headline is None:
            choices = NEWS_HEADLINES[index][0 if positive else 1]
            headline = random.choice(choices)
        self.latest_news_type[index] = kind or ("호재" if positive else "악재")
        self.news[index].appendleft((time.strftime("%H:%M:%S"), index, positive, headline, kind, duration))

    def tick_market(self):
        for i, price in enumerate(PRICES):
            rate = random.randint(*RANGES[i]) / 100

            if self.bubble_remaining[i] > 0:
                # Bubble phase: rapid speculative rise, followed by a sharp correction.
                price *= 1 + random.uniform(0.01, 0.025)
                self.bubble_remaining[i] -= 1
                if self.bubble_remaining[i] == 0:
                    price *= 1 - random.uniform(0.20, 0.35)
                    duration = random.randint(8, 16)
                    self.add_news(i, False, "과열된 매수세가 식으며 버블 붕괴, 차익 실현 매물 출회", "버블", duration)
                    self.trend_direction[i] = -1
                    self.trend_remaining[i] = duration
                    self.trend_duration[i] = duration
                    self.trend_strength[i] = random.uniform(0.001, 0.003)
            else:
                if self.trend_remaining[i] > 0:
                    strength = self.trend_strength[i]
                    phase = self.trend_remaining[i] / max(1, self.trend_duration[i])
                    fade = 0.55 + 0.45 * phase
                    # Keep a directional bias, but let ordinary price noise create small
                    # pullbacks and stronger bursts instead of a straight line.
                    rate += self.trend_direction[i] * strength * fade * random.uniform(0.35, 1.45)
                    rate += random.uniform(-strength * 1.5, strength * 1.5)
                    self.trend_remaining[i] -= 1
                    if self.trend_remaining[i] == 0:
                        self.trend_direction[i] = 0
                        self.trend_strength[i] = 0.0
                price *= 1 + rate

                news = random.random() * 100
                if news <= 1.2:
                    price *= 1 + random.uniform(0.015, 0.04)
                    headline = random.choice(NEWS_HEADLINES[i][0])
                    duration = self.duration_for_news(headline, True)
                    self.add_news(i, True, headline, duration=duration)
                    self.trend_direction[i] = 1
                    self.trend_remaining[i] = duration
                    self.trend_duration[i] = duration
                    self.trend_strength[i] = random.uniform(0.0015, 0.004)
                elif news >= 98.8:
                    price *= 1 - random.uniform(0.015, 0.04)
                    headline = random.choice(NEWS_HEADLINES[i][1])
                    duration = self.duration_for_news(headline, False)
                    self.add_news(i, False, headline, duration=duration)
                    self.trend_direction[i] = -1
                    self.trend_remaining[i] = duration
                    self.trend_duration[i] = duration
                    self.trend_strength[i] = random.uniform(0.0015, 0.004)

                # A rare speculative surge can start independently of ordinary news.
                if random.random() < 0.0025:
                    price *= 1.02
                    self.bubble_remaining[i] = random.randint(8, 14)
                    self.add_news(i, True, "테마 매수세 급증, 단기간 급등에 버블 우려 확산", "버블")
            PRICES[i] = round(max(10, price))
            self.history[i].append(float(PRICES[i]))
            if len(self.history[i]) > 100:
                self.history[i].pop(0)

    def draw_text(self, value, pos, f=None, color=WHITE):
        self.screen.blit((f or self.f).render(str(value), True, color), pos)

    def draw_text_fit(self, value, pos, f, max_width, color=WHITE):
        text = str(value)
        if f.size(text)[0] > max_width:
            suffix = "..."
            while text and f.size(text + suffix)[0] > max_width:
                text = text[:-1]
            text = text + suffix if text else suffix
        self.draw_text(text, pos, f, color)

    def panel(self, rect, title_text, subtitle=None):
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=15)
        self.draw_text_fit(title_text, (rect.x + 20, rect.y + 18), self.medium, rect.w - 40)
        if subtitle:
            self.draw_text_fit(subtitle, (rect.x + 20, rect.y + 48), self.small, rect.w - 40, MUTED)

    def draw_header(self):
        self.draw_text("주식 투자 게임", (32, 25), self.title)
        self.draw_text("실시간으로 변하는 가상 시장에서 투자해 보세요", (34, 67), self.small, MUTED)
        self.draw_text_fit(f"로그인: {self.nickname}", (420, 43), self.small, 280, MUTED)
        self.draw_button(self.ranking_tab_rect, "랭킹", BLUE)
        pygame.draw.rect(self.screen, PANEL, (902, 25, 346, 74), border_radius=12)
        self.draw_text("총 자산", (922, 37), self.small, MUTED)
        self.draw_text_fit(won(self.total_assets()), (922, 59), self.medium, 306)

    def draw_login(self):
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, PANEL, (435, 235, 450, 390), border_radius=18)
        self.draw_text("주식 투자 게임", (475, 280), self.title)
        self.draw_text("Google 계정으로 로그인하고 최고 기록을 저장하세요.", (475, 345), self.small, MUTED)
        self.draw_button(self.login_rect, "Google 계정으로 로그인", BLUE)
        if self.auth_error:
            self.draw_text_fit(self.auth_error, (475, 575), self.small, 370, RED)

    def draw_nickname(self):
        self.screen.fill(BG)
        pygame.draw.rect(self.screen, PANEL, (435, 245, 450, 390), border_radius=18)
        self.draw_text("닉네임 설정", (475, 285), self.title)
        self.draw_text("랭킹에 표시할 닉네임을 정해 주세요. (2~12자)", (475, 345), self.small, MUTED)
        pygame.draw.rect(self.screen, (19, 27, 41), self.nickname_rect, border_radius=8)
        val = self.nickname_input + ("|" if pygame.time.get_ticks() % 1000 < 500 else "")
        image = self.f.render(val or "닉네임 입력", True, WHITE if val else MUTED)
        self.screen.blit(image, image.get_rect(center=self.nickname_rect.center))
        self.draw_button(self.nickname_submit_rect, "게임 시작", BLUE)
        if self.auth_error:
            self.draw_text_fit(self.auth_error, (475, 620), self.small, 370, RED)

    def draw_ranking(self):
        self.screen.fill(BG)
        self.draw_text("주식 투자 게임", (32, 25), self.title)
        self.draw_text_fit(f"랭킹 · {self.nickname}님", (32, 67), self.small, 900, MUTED)
        pygame.draw.rect(self.screen, PANEL, (200, 125, 920, 730), border_radius=16)
        self.draw_text("보유 현금 최고 기록 랭킹", (240, 155), self.title)
        self.draw_text("순위", (250, 220), self.small, MUTED)
        self.draw_text("닉네임", (340, 220), self.small, MUTED)
        self.draw_text("점수 (보유 현금)", (710, 220), self.small, MUTED)
        self.draw_text("기록 시각", (960, 220), self.small, MUTED)
        if self.leaderboard_error:
            self.draw_text_fit(self.leaderboard_error, (250, 270), self.small, 820, RED)
        elif not self.leaderboard:
            self.draw_text("아직 등록된 기록이 없습니다.", (250, 270), self.f, MUTED)
        for i, row in enumerate(self.leaderboard[:20]):
            y = 255 + i * 27
            if row["uid"] == self.firebase.uid:
                pygame.draw.rect(self.screen, (42, 59, 86), (235, y - 4, 850, 26), border_radius=5)
            self.draw_text(f"{i + 1:>2}위", (250, y), self.small, GOLD if i < 3 else WHITE)
            self.draw_text_fit(row["nickname"], (340, y), self.small, 300)
            self.draw_text_fit(won(row["score"]), (710, y), self.small, 210)
            stamp = row["updated_at"].replace("T", " ").replace("Z", " UTC")
            self.draw_text_fit(stamp, (960, y), self.small, 130, MUTED)
        self.draw_button(pygame.Rect(32, 116, 155, 48), "게임으로", PANEL2)

    def draw_confirm(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, PANEL, (480, 350, 560, 250), border_radius=16)
        self.draw_text("랭킹에 기록할까요?", (520, 385), self.title)
        self.draw_text("저장하면 현재 게임이 초기화되고 새 게임이 시작됩니다.", (520, 445), self.small, MUTED)
        self.draw_text_fit(f"저장 점수: {won(self.best_score)}", (520, 475), self.small, 480, GOLD)
        self.draw_button(self.confirm_save_rect, "저장 후 새 게임", BLUE)
        self.draw_button(self.confirm_cancel_rect, "취소", PANEL2)

    def draw_stocks(self):
        self.panel(pygame.Rect(32, 116, 330, 606), "종목 목록", "종목을 클릭하면 그래프가 바뀝니다")
        self.draw_text("종목", (52, 188), self.small, MUTED)
        self.draw_text("현재가", (136, 188), self.small, MUTED)
        self.draw_text("뉴스", (222, 188), self.small, MUTED)
        self.draw_text("보유", (304, 188), self.small, MUTED)
        for visible in range(10):
            i = visible
            y = 216 + visible * 48
            row = pygame.Rect(44, y, 306, 43)
            if i == self.selected:
                pygame.draw.rect(self.screen, (42, 59, 86), row, border_radius=8)
            change_color = GREEN if len(self.history[i]) < 2 or self.history[i][-1] >= self.history[i][-2] else RED
            self.draw_text_fit(NAMES[i], (54, y + 11), self.small, 76)
            self.draw_text_fit(f"{PRICES[i]:,}", (136, y + 11), self.small, 78, change_color)
            news_type = self.latest_news_type[i] or "-"
            news_color = (187, 139, 255) if news_type == "버블" else (GREEN if news_type == "호재" else RED if news_type == "악재" else MUTED)
            self.draw_text_fit(news_type, (222, y + 11), self.small, 50, news_color)
            self.draw_text_fit(f"{self.holdings[i]}주", (300, y + 11), self.small, 50, MUTED)

    def draw_chart(self):
        rect = pygame.Rect(382, 116, 500, 606)
        self.panel(rect, "주가 그래프", "최근 100회 시세 · 1초마다 업데이트")
        i = self.selected
        values = self.history[i]
        self.draw_text(NAMES[i], (rect.x + 22, rect.y + 91), self.f, MUTED)
        self.draw_text(won(PRICES[i]), (rect.x + 22, rect.y + 116), self.large)
        delta = values[-1] - values[0]
        pct = delta / values[0] * 100 if values[0] else 0
        trend = GREEN if delta >= 0 else RED
        self.draw_text(f"{delta:+,.0f}원  ({pct:+.2f}%)", (rect.x + 24, rect.y + 158), self.small, trend)
        plot = pygame.Rect(rect.x + 22, rect.y + 205, rect.w - 44, 340)
        pygame.draw.rect(self.screen, (19, 27, 41), plot, border_radius=9)
        lo, hi = min(values), max(values)
        margin = max((hi - lo) * 0.12, 1)
        lo -= margin
        hi += margin
        for n in range(1, 5):
            y = plot.y + n * plot.h // 5
            pygame.draw.line(self.screen, (43, 54, 72), (plot.x, y), (plot.right, y), 1)
        points = []
        for j, value in enumerate(values):
            x = plot.x + j * plot.w / max(1, len(values) - 1)
            y = plot.bottom - (value - lo) / (hi - lo) * plot.h
            points.append((round(x), round(y)))
        if len(points) > 1:
            pygame.draw.lines(self.screen, trend, False, points, 3)
            pygame.draw.circle(self.screen, trend, points[-1], 5)
        self.draw_text("이전", (plot.x, plot.bottom + 12), self.small, MUTED)
        self.draw_text("현재", (plot.right - 35, plot.bottom + 12), self.small, MUTED)

    def draw_news(self):
        rect = pygame.Rect(32, 742, 1216, 166)
        self.panel(rect, f"시장 뉴스 · {NAMES[self.selected]}", "선택 종목의 가상 뉴스 · 실제 기업 뉴스가 아닙니다")
        selected_news = list(self.news[self.selected])
        if not selected_news:
            self.draw_text("선택 종목의 뉴스가 아직 없습니다.", (rect.x + 22, rect.y + 82), self.small, MUTED)
            return
        for line, (stamp, index, positive, headline, kind, duration) in enumerate(selected_news[:5]):
            y = rect.y + 70 + line * 19
            color = (187, 139, 255) if kind == "버블" else (GREEN if positive else RED)
            tag = kind or ("호재" if positive else "악재")
            self.draw_text(stamp, (rect.x + 22, y), self.small, MUTED)
            self.draw_text(f"[{tag}]", (rect.x + 105, y), self.small, color)
            self.draw_text(NAMES[index], (rect.x + 158, y), self.small, WHITE)
            self.draw_text_fit(headline, (rect.x + 270, y), self.small, rect.w - 390, WHITE)
            if duration:
                suffix = f"추세 {duration}초"
                self.draw_text(suffix, (rect.right - 100, y), self.small, color)

    def draw_portfolio_trade(self):
        rect = pygame.Rect(902, 116, 346, 606)
        self.panel(rect, "내 자산", "현금과 보유 주식 평가액")
        self.draw_text_fit(f"최고 기록: {won(self.best_score)} · {self.best_time}", (rect.x + 20, rect.y + 75), self.small, 320, GOLD)
        self.draw_button(self.enroll_rect, "랭킹 등재", (120, 103, 54))
        self.draw_text("보유 현금", (rect.x + 22, rect.y + 91), self.small, MUTED)
        self.draw_text_fit(won(self.cash), (rect.x + 22, rect.y + 116), self.medium, rect.w - 44)
        i = self.selected
        value = self.holdings[i] * PRICES[i]
        unrealized = value - self.cost_basis[i]
        unrealized_percent = (unrealized / self.cost_basis[i] * 100) if self.cost_basis[i] else 0
        unrealized_color = GREEN if unrealized > 0 else RED if unrealized < 0 else MUTED
        pygame.draw.line(self.screen, LINE, (rect.x + 20, rect.y + 162), (rect.right - 20, rect.y + 162), 1)
        self.draw_text(f"{NAMES[i]} 보유", (rect.x + 22, rect.y + 182), self.small, MUTED)
        self.draw_text(f"{self.holdings[i]:,}주", (rect.x + 22, rect.y + 207), self.medium)
        self.draw_text("평가 금액", (rect.x + 176, rect.y + 182), self.small, MUTED)
        self.draw_text_fit(won(value), (rect.x + 176, rect.y + 207), self.small, 148)
        self.draw_text("평가손익", (rect.x + 22, rect.y + 234), self.small, MUTED)
        self.draw_text_fit(f"{unrealized:+,.0f}원", (rect.x + 98, rect.y + 234), self.small, 132, unrealized_color)
        self.draw_text(f"({unrealized_percent:+.1f}%)", (rect.x + 236, rect.y + 234), self.small, unrealized_color)
        realized_color = GREEN if self.realized_profit[i] > 0 else RED if self.realized_profit[i] < 0 else MUTED
        self.draw_text("실현손익", (rect.x + 22, rect.y + 258), self.small, MUTED)
        self.draw_text_fit(f"{self.realized_profit[i]:+,.0f}원", (rect.x + 98, rect.y + 258), self.small, 210, realized_color)
        pygame.draw.line(self.screen, LINE, (rect.x + 20, rect.y + 282), (rect.right - 20, rect.y + 282), 1)
        self.draw_text("주문 수량", (rect.x + 22, rect.y + 294), self.small, MUTED)
        for r, label in ((self.minus_rect, "-"), (self.plus_rect, "+")):
            pygame.draw.rect(self.screen, PANEL2, r, border_radius=8)
            self.screen.blit(self.medium.render(label, True, WHITE), self.medium.render(label, True, WHITE).get_rect(center=r.center))
        pygame.draw.rect(self.screen, (19, 27, 41), self.qty_rect, border_radius=8)
        shown_qty = self.quantity + ("|" if self.input_active and pygame.time.get_ticks() % 1000 < 500 else "")
        image = self.f.render(shown_qty, True, WHITE)
        self.screen.blit(image, image.get_rect(center=self.qty_rect.center))
        self.draw_text_fit("- / + 또는 숫자 입력으로 수량 조절", (rect.x + 22, rect.y + 337), self.small, rect.w - 44, MUTED)
        self.draw_text("수량은 매수·매도에 공통 적용", (rect.x + 22, rect.y + 359), self.small, MUTED)
        self.draw_button(self.buy_rect, "매수", (33, 151, 107))
        self.draw_button(self.sell_rect, "매도", (183, 68, 83))
        self.draw_trade_message((rect.x + 22, rect.y + 565))
        self.draw_text(f"선택 종목 현재가: {won(PRICES[i])}", (rect.x + 22, rect.y + 469), self.small, MUTED)

    def draw_button(self, rect, text, color):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        window_w, window_h = self.window.get_size()
        logical_mouse = (mouse_x * WIDTH / window_w, mouse_y * HEIGHT / window_h)
        hover = rect.collidepoint(logical_mouse)
        fill = tuple(min(255, c + 20) for c in color) if hover else color
        pygame.draw.rect(self.screen, fill, rect, border_radius=9)
        image = self.medium.render(text, True, WHITE)
        self.screen.blit(image, image.get_rect(center=rect.center))

    def draw(self):
        self.screen.fill(BG)
        if self.view == "login":
            self.draw_login()
        elif self.view == "nickname":
            self.draw_nickname()
        elif self.view == "ranking":
            self.draw_ranking()
        else:
            self.draw_header()
            self.draw_stocks()
            self.draw_chart()
            self.draw_portfolio_trade()
            self.draw_news()
            if self.view == "confirm":
                self.draw_confirm()
        scaled = pygame.transform.smoothscale(self.screen, self.window.get_size())
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def handle_click(self, pos):
        pos = (int(pos[0]), int(pos[1]))
        if self.view == "login":
            if self.login_rect.collidepoint(pos):
                self.begin_google_login()
            return
        if self.view == "nickname":
            if self.nickname_submit_rect.collidepoint(pos):
                self.submit_nickname()
            return
        if self.view == "confirm":
            if self.confirm_save_rect.collidepoint(pos):
                self.enroll_score()
            elif self.confirm_cancel_rect.collidepoint(pos):
                self.view = "game"
            return
        if self.view == "ranking":
            if pygame.Rect(32, 116, 155, 48).collidepoint(pos):
                self.view = "game"
            return
        if self.ranking_tab_rect.collidepoint(pos):
            self.view = "ranking"
            self.refresh_leaderboard()
            return
        if self.enroll_rect.collidepoint(pos):
            self.view = "confirm"
            return
        if self.rows_rect.collidepoint(pos):
            row = (pos[1] - 216) // 48
            if 0 <= row < 10:
                self.selected = int(row)
            return
        if self.minus_rect.collidepoint(pos):
            self.change_quantity(-1)
        elif self.plus_rect.collidepoint(pos):
            self.change_quantity(1)
        elif self.qty_rect.collidepoint(pos):
            self.input_active = True
        else:
            self.input_active = False
            if self.buy_rect.collidepoint(pos):
                self.trade(True)
            elif self.sell_rect.collidepoint(pos):
                self.trade(False)

    def run(self):
        running = True
        while running:
            now = time.monotonic()
            if self.view in ("game", "confirm") and now - self.last_update >= 1:
                self.tick_market()
                self.last_update = now
            if self.view in ("game", "confirm"):
                self.update_best_score()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        window_w, window_h = self.window.get_size()
                        logical_pos = (round(event.pos[0] * WIDTH / window_w), round(event.pos[1] * HEIGHT / window_h))
                        self.handle_click(logical_pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE and self.view == "confirm":
                        self.view = "game"
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    elif self.view == "nickname":
                        if event.key == pygame.K_BACKSPACE:
                            self.nickname_input = self.nickname_input[:-1]
                        elif event.key == pygame.K_RETURN:
                            self.submit_nickname()
                        elif event.unicode.isprintable() and len(self.nickname_input) < 12:
                            self.nickname_input += event.unicode
                    elif self.input_active:
                        if event.key == pygame.K_BACKSPACE:
                            self.quantity = self.quantity[:-1]
                        elif event.key == pygame.K_RETURN:
                            self.input_active = False
                        elif event.unicode.isdigit() and len(self.quantity) < 4:
                            self.quantity = (self.quantity + event.unicode).lstrip("0") or "0"
            self.draw()
            self.clock.tick(60)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    StockGame().run()

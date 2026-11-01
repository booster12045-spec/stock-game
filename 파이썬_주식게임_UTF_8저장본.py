import random
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
        pygame.draw.rect(self.screen, PANEL, (902, 25, 346, 74), border_radius=12)
        self.draw_text("총 자산", (922, 37), self.small, MUTED)
        self.draw_text_fit(won(self.total_assets()), (922, 59), self.medium, 306)

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
        self.draw_header()
        self.draw_stocks()
        self.draw_chart()
        self.draw_portfolio_trade()
        self.draw_news()
        scaled = pygame.transform.smoothscale(self.screen, self.window.get_size())
        self.window.blit(scaled, (0, 0))
        pygame.display.flip()

    def handle_click(self, pos):
        pos = (int(pos[0]), int(pos[1]))
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
            if now - self.last_update >= 1:
                self.tick_market()
                self.last_update = now
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        window_w, window_h = self.window.get_size()
                        logical_pos = (round(event.pos[0] * WIDTH / window_w), round(event.pos[1] * HEIGHT / window_h))
                        self.handle_click(logical_pos)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
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

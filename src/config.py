# -*- coding: utf-8 -*-
"""백테스트 파라미터 — backtest_spec.md 와 1:1 대응."""
import os

# ---------------- 전략 버전 ----------------
# 리포트 제목에 쓰인다. 스펙 버전을 올릴 때 여기도 함께 갱신할 것.
STRATEGY_NAME = "52주 신고가 모멘텀 v14 (20일선 이탈을 +24% 도달 이후에만)"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DAUM_DIR = os.path.join(DATA, "daum")
NAVER_DIR = os.path.join(DATA, "naver")
OUT = os.path.join(ROOT, "output")

# ---------------- 기간 (§2) ----------------
DATA_START = "20150101"      # 지표 워밍업 포함 데이터 확보 시작
TEST_START = "2016-01-01"    # 실제 매매 시작
TEST_END = "2026-07-31"

# ---------------- 유니버스 (§1) ----------------
MARKETS = ("STK", "KSQ")     # KOSPI, KOSDAQ (KONEX 제외)
MIN_MARKET_CAP = 1_000_000_000_000   # 1조원 (v3에서 복원 — v2의 소형주 편입이 성과를 훼손)
MIN_PRICE = 1_000                    # 1,000원
MIN_LISTED_DAYS = 250                # 상장 250거래일 미만 제외
UNIVERSE_REBAL = "M"                 # 매월 말 유니버스 재구성

EXCLUDE_NAME_TOKENS = ("스팩", "기업인수목적", "리츠")

# ---------------- 진입 (§3) ----------------
HIGH_LOOKBACK = 250          # 52주 신고가 룩백 (당일 제외)
ATR_PERIOD = 14              # Wilder ATR
VALUE_MA_PERIOD = 20         # 거래대금 이동평균 기간 (당일 제외)
VALUE_MULTIPLE = 1.3         # 거래대금 >= 20일평균 x 이 값 (v8~ 1.3 확정)
UPPER_LIMIT_PCT = 0.295      # 상한가 판정 (+29.5% 이상 마감 시 제외)

# ---------------- RS 상대강도 (§3-1 조건4) ----------------
# O'Neil RS Rating: (직전 1분기 종가비 x2) + 2~4분기 전 종가비. 63거래일 = 1분기.
INDEX_DIR = os.path.join(DATA, "index")
MARKET_INDEX = {"STK": "KOSPI", "KSQ": "KOSDAQ"}   # 종목 시장별 벤치마크 지수
RS_QUARTER_DAYS = 63

# ---------------- 청산 (§4) ----------------
# v6~: 트레일링을 끄고 손절선을 진입가 기준 -8% 에 고정한다.
#   트레일링(고점 대비 -8%)은 상승 중 정상적인 조정에도 청산돼 수익을 짧게 잘랐다.
#   삼성전기 2026-04 사례: 트레일링 -8% 는 +73.8%(29일)에 청산됐으나,
#   고정손절+20일선이탈은 +268.9%(86일)까지 보유했다.
TRAILING_STOP = False        # True 면 고점 대비(v1~v5), False 면 진입가 대비 고정
TRAIL_PCT = 0.08             # 손절폭 -8%
PARTIAL_TP_PCT = 0.24        # +24% 도달 시
PARTIAL_TP_RATIO = 0.30      # 보유 수량의 30% 익절
MA_EXIT_PERIOD = 20          # 종가가 20일선 하향 이탈 시 전량
# v14: 20일선 이탈 청산을 '+24% 도달 이후'에만 적용한다.
#   True  면 +24% 에 닿기 전에는 20일선을 깨도 홀딩하고 -8% 고정손절만 유효
#   False 면 도달 여부와 무관하게 20일선 이탈 시 청산 (v6~v13)
MA_EXIT_AFTER_TP = True

# ---------------- 자금 관리 (§5) ----------------
INITIAL_CAPITAL = 100_000_000
MAX_POSITIONS = 8

# --- v12: Max 2% Rule (R 구성요소 1~3R) ---
# 1R = (2%/8%)/6 = 자산의 4.1667%. 구성요소 각각 1~3R, 합계 2~6R (최대 투입 25%).
# ⚠️ 최대 6R(25%)이면 4종목만으로 자산이 소진돼 현금부족이 발생한다(v9 에서 34.1%).
R_UNIT_PCT = (0.02 / 0.08) / 6      # 0.041667 — 1R
R_MIN_UNITS = 1              # 각 구성요소의 하한
R_MAX_UNITS = 3              # 각 구성요소의 상한
R_STEP = 1                   # 성공/실패 시 증감 폭
MAX_POSITION_PCT = R_UNIT_PCT * R_MAX_UNITS * 2   # 0.25 — 최대 투입 (6R)
MAX_LOSS_PCT = MAX_POSITION_PCT * TRAIL_PCT       # 0.02 — Max 2% Rule

# --- v12: 시장 국면 판정을 '시장폭(breadth)' 으로 변경 ---
#   REGIME_MODE = "breadth" : 종가가 200일선 **아래**인 종목의 비율로 판정 (v12~)
#   REGIME_MODE = "index"   : 지수 자신의 MA200 위치 + 기울기로 판정 (v4~v11)
REGIME_MODE = "breadth"
BREADTH_MA = 200             # 종목별 기준 이동평균
BREADTH_BULL_MAX = 0.45      # 200일선 아래 비율 < 45%  -> 강세장
BREADTH_BEAR_MIN = 0.70      # 200일선 아래 비율 > 70%  -> 하락장 (사이는 횡보장)
REGIME_MA_PERIOD = 200       # (index 모드용) 지수 이동평균
REGIME_SLOPE_DAYS = 20       # (index 모드용) MA200 기울기 판정 기간
REGIME_BEAR, REGIME_SIDE, REGIME_BULL = 1, 2, 3   # 각 국면의 R 배정

# --- v12: 시장 필터 — 시장별로 다른 기준선 ---
# 코스피 종목은 코스피 60일선, 코스닥 종목은 코스닥 120일선 아래면 신규 진입 중단.
# 보유 포지션은 기존 청산 규칙(고정손절 / 20일선 이탈)을 그대로 따른다.
MARKET_FILTER = True
MARKET_FILTER_MA = {"KOSPI": 60, "KOSDAQ": 120}

# ---------------- 비용 (§6) ----------------
FEE_BUY = 0.00015
FEE_SELL = 0.00015
TAX_SELL = 0.0018
SLIPPAGE = 0.001             # 매수/매도 각각

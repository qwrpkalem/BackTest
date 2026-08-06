# -*- coding: utf-8 -*-
"""백테스트 파라미터 — backtest_spec.md 와 1:1 대응."""
import os

# ---------------- 전략 버전 ----------------
# 리포트 제목에 쓰인다. 스펙 버전을 올릴 때 여기도 함께 갱신할 것.
STRATEGY_NAME = "52주 신고가 모멘텀 v10 (v9 + 코스피 60일선 시장필터)"

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

# ---------------- 자금 관리 (§5) ----------------
INITIAL_CAPITAL = 100_000_000
MAX_POSITIONS = 8

# --- v9: Max 2% Rule 복원 (R 구성요소를 1R 단위로) ---
# Max 2% Rule: 1회 최대 손실 = 자산의 2%. 손절폭 -8% 이므로 최대 투입 = 2%/8% = 25%.
# 이 25% 를 6R 로 보아 1R = 4.1667%. 구성요소는 각각 1~3R, 합계 2~6R.
#   v5~v8 은 구성요소를 0.5~1.5R 로 줄여 최대 투입이 12.5%(= 실질 Max 1% Rule)였다.
# ⚠️ 최대 6R(25%)이면 4종목만으로 자산이 소진되므로 현금 부족이 다시 발생할 수 있다
#    (v4 에서 23.9% 가 목표 R 미달). trades.csv 의 capped 컬럼으로 확인할 것.
R_UNIT_PCT = (0.02 / 0.08) / 6      # 0.041667 — 1R
R_MIN_UNITS = 1              # 각 구성요소의 하한
R_MAX_UNITS = 3              # 각 구성요소의 상한
R_STEP = 1                   # 성공/실패 시 증감 폭
MAX_POSITION_PCT = R_UNIT_PCT * R_MAX_UNITS * 2   # 0.25 — 최대 투입 (6R)
MAX_LOSS_PCT = MAX_POSITION_PCT * TRAIL_PCT       # 0.02 — Max 2% Rule

# --- 시장 국면 판정 (강세 3R / 횡보 2R / 약세 1R) ---
# 강세: 지수 > MA200 이고 MA200 상승 중 / 약세: 지수 < MA200 이고 MA200 하락 중
REGIME_MA_PERIOD = 200       # 국면 판정용 지수 이동평균
REGIME_SLOPE_DAYS = 20       # MA200 기울기를 재는 기간 (며칠 전과 비교할지)
REGIME_BEAR, REGIME_SIDE, REGIME_BULL = 1, 2, 3   # 각 국면의 R 배정

# --- v10: 시장 필터 — 코스피가 60일선 아래면 신규 진입 중단 ---
# 보유 포지션은 기존 청산 규칙(고정손절 / 20일선 이탈)을 그대로 따른다.
MARKET_FILTER = True         # v10: 코스피가 60일선 아래면 신규 진입 중단
MARKET_FILTER_INDEX = "KOSPI"
MARKET_FILTER_MA = 60

# ---------------- 비용 (§6) ----------------
FEE_BUY = 0.00015
FEE_SELL = 0.00015
TAX_SELL = 0.0018
SLIPPAGE = 0.001             # 매수/매도 각각

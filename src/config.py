# -*- coding: utf-8 -*-
"""백테스트 파라미터 — backtest_spec.md 와 1:1 대응."""
import os

# ---------------- 전략 버전 ----------------
# 리포트 제목에 쓰인다. 스펙 버전을 올릴 때 여기도 함께 갱신할 것.
STRATEGY_NAME = "52주 신고가 모멘텀 v4 (R 기반 포지션 사이징)"

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
VALUE_MULTIPLE = 2.5         # 거래대금 >= 20일평균 x 2.5
UPPER_LIMIT_PCT = 0.295      # 상한가 판정 (+29.5% 이상 마감 시 제외)

# ---------------- RS 상대강도 (§3-1 조건4) ----------------
# O'Neil RS Rating: (직전 1분기 종가비 x2) + 2~4분기 전 종가비. 63거래일 = 1분기.
INDEX_DIR = os.path.join(DATA, "index")
MARKET_INDEX = {"STK": "KOSPI", "KSQ": "KOSDAQ"}   # 종목 시장별 벤치마크 지수
RS_QUARTER_DAYS = 63

# ---------------- 청산 (§4) ----------------
TRAIL_PCT = 0.08             # 고점 대비 -8% 트레일링 스탑
PARTIAL_TP_PCT = 0.24        # +24% 도달 시
PARTIAL_TP_RATIO = 0.30      # 보유 수량의 30% 익절
MA_EXIT_PERIOD = 20          # 종가가 20일선 하향 이탈 시 전량

# ---------------- 자금 관리 (§5) ----------------
INITIAL_CAPITAL = 100_000_000
MAX_POSITIONS = 8

# --- v4: Max 2% Rule + R 기반 포지션 사이징 ---
# 1회 매매 최대 손실을 자산의 2%로 제한한다. 손절폭이 TRAIL_PCT(-8%)이므로
# 최대 투입금 = 2% / 8% = 자산의 25%. 이 25%를 6R 로 보아 1R 을 정한다.
MAX_LOSS_PCT = 0.02          # Max 2% Rule — 1회 매매 최대 손실 (자산 대비)
R_TOTAL_UNITS = 6            # 최대 투입금 = 6R (시장국면 3R + 연속성 3R)
R_MIN_UNITS = 1              # 각 구성요소의 하한
R_MAX_UNITS = 3              # 각 구성요소의 상한
MAX_POSITION_PCT = MAX_LOSS_PCT / TRAIL_PCT      # 0.25 — 6R 에 해당
R_UNIT_PCT = MAX_POSITION_PCT / R_TOTAL_UNITS    # 0.041667 — 1R

# --- v4: 시장 국면 판정 (강세 3R / 횡보 2R / 약세 1R) ---
# 강세: 지수 > MA200 이고 MA200 상승 중 / 약세: 지수 < MA200 이고 MA200 하락 중
REGIME_MA_PERIOD = 200       # 국면 판정용 지수 이동평균
REGIME_SLOPE_DAYS = 20       # MA200 기울기를 재는 기간 (며칠 전과 비교할지)
REGIME_BEAR, REGIME_SIDE, REGIME_BULL = 1, 2, 3   # 각 국면의 R 배정

# ---------------- 비용 (§6) ----------------
FEE_BUY = 0.00015
FEE_SELL = 0.00015
TAX_SELL = 0.0018
SLIPPAGE = 0.001             # 매수/매도 각각

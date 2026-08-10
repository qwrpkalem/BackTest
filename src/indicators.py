# -*- coding: utf-8 -*-
"""종목별 일봉 로딩 + 지표 계산 + 진입 시그널 생성.

주가(수정주가)는 네이버, 금액(거래대금·시가총액)은 다음 원본값을 쓴다.
  - 수정주가라야 52주 신고가/ATR/이동평균이 액면분할에 왜곡되지 않는다.
  - 거래대금·시가총액은 '금액'이라 분할과 무관하게 원본값이 정확하다.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C


def load_merged(code):
    """네이버 수정주가 + 다음 금액 데이터를 날짜로 결합."""
    np_path = os.path.join(C.NAVER_DIR, "%s.csv" % code)
    dp_path = os.path.join(C.DAUM_DIR, "%s.csv" % code)
    if not (os.path.exists(np_path) and os.path.exists(dp_path)):
        return None

    n = pd.read_csv(np_path, parse_dates=["date"])
    d = pd.read_csv(dp_path, parse_dates=["date"])

    # 거래정지/휴장으로 0이 박힌 행 제거
    n = n[(n["close"] > 0) & (n["high"] > 0) & (n["low"] > 0) & (n["open"] > 0)]
    d = d[d["close_r"] > 0]

    df = pd.merge(n, d[["date", "value", "marcap", "shares", "close_r"]],
                  on="date", how="inner")
    if len(df) < C.HIGH_LOOKBACK + 5:
        return None
    return df.sort_values("date").reset_index(drop=True)


def wilder_atr(high, low, close, period):
    """Wilder 평활 ATR. TR = max(H-L, |H-PC|, |L-PC|)"""
    pc = close.shift(1)
    tr = pd.concat([high - low, (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    # Wilder RMA = EMA(alpha = 1/period)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rs_raw_score(close, q=C.RS_QUARTER_DAYS):
    """O'Neil RS Rating의 raw score. 최근 분기 종가비에 2배 가중, 이전 3개
    분기는 1배씩. 백분위 변환은 종목 간 비교가 필요해 여기서는 하지 않는다."""
    s1 = close / close.shift(q)
    s2 = close.shift(q) / close.shift(2 * q)
    s3 = close.shift(2 * q) / close.shift(3 * q)
    s4 = close.shift(3 * q) / close.shift(4 * q)
    return 2.0 * s1 + s2 + s3 + s4


def add_indicators(df):
    """지표 3종 + 청산용 SMA20 + RS raw score. 기준값은 모두 '당일 제외' 과거 데이터로 계산."""
    c, h, l = df["close"], df["high"], df["low"]

    df["atr"] = wilder_atr(h, l, c, C.ATR_PERIOD)
    df["prev_close"] = c.shift(1)
    df["gain"] = c - df["prev_close"]

    # 52주 신고가 기준: 당일 제외 직전 250거래일 최고 '고가' (장중 기준)
    # v38: 신고가를 무엇으로 재는가 — 장중 고가(v1~v37) 대 종가(v38~)
    #   "high"  : 직전 N일의 장중 고가 최댓값을 당일 장중 고가가 넘는가
    #   "close" : 직전 N일의 종가 최댓값을 당일 종가가 넘는가 ("신고가 마감")
    base = c if C.HIGH_BASIS == "close" else h
    df["high_250"] = base.shift(1).rolling(C.HIGH_LOOKBACK).max()

    # 거래대금 20일 평균: 당일 제외
    df["value_ma"] = df["value"].shift(1).rolling(C.VALUE_MA_PERIOD).mean()

    # 청산용 20일 이동평균 (당일 포함)
    df["sma20"] = c.rolling(C.MA_EXIT_PERIOD).mean()

    # v12: 시장폭(breadth) 집계용 200일 이동평균
    df["sma_breadth"] = c.rolling(C.BREADTH_MA).mean()

    # v22: 음봉 청산의 추세 확인용 단기 이동평균 (5일선)
    df["sma_bear"] = (c.rolling(C.BEAR_MA_PERIOD).mean()
                      if C.BEAR_MA_PERIOD else pd.Series(np.nan, index=c.index))

    # RS(상대강도) raw score — 지수 대비 백분위는 prepare.py에서 cross-sectional 계산
    df["rs_raw"] = rs_raw_score(c)

    # 상장 경과 거래일
    # --- v45: 베이스(건전한 조정) 판정 ---
    # 책의 매매법은 "그냥 신고가"가 아니라 **큰 상승 -> 건전한 조정 -> 재돌파** 다.
    # 조정 구간(베이스) 없이 계속 신고가를 갱신하며 오르는 종목은 사지 않는다.
    #   ① 베이스 길이 : 직전 신고가 이후 BASE_MIN_DAYS 거래일 이상 경과
    #   ② 조정 깊이   : 룩백 구간의 (고점-저점)/고점 이 BASE_MAX_DEPTH 이내 (건전한 조정)
    #   ③ 선행 상승   : 베이스 시작 전 PRIOR_GAIN_DAYS 동안 PRIOR_GAIN_PCT 이상 상승
    n = len(df)
    idx = np.arange(n)
    base = c if C.HIGH_BASIS == "close" else h
    was_high = (base >= base.shift(1).rolling(C.HIGH_LOOKBACK).max()).fillna(False)
    last_hi = pd.Series(np.where(was_high.values, idx, np.nan), index=df.index).ffill()
    df["base_days"] = idx - last_hi.shift(1)          # 직전 신고가 이후 경과 거래일

    # 조정 깊이는 '최근 조정 구간'(BASE_WINDOW)에서 잰다. 룩백 전체(250일)로 재면
    # 거의 모든 종목이 35% 를 넘어 시그널이 사라진다.
    W = C.BASE_WINDOW
    win_hi = base.shift(1).rolling(W).max()
    win_lo = base.shift(1).rolling(W).min()
    df["base_depth"] = 1.0 - win_lo / win_hi

    # 선행 상승은 베이스가 시작되기 '전' 구간에서 잰다.
    df["prior_gain"] = c.shift(W) / c.shift(W + C.PRIOR_GAIN_DAYS) - 1.0

    df["bars"] = np.arange(len(df))
    return df


def add_signal(df):
    """§3-1 진입 시그널 3조건 AND + 극단 급등일 제외 (RS 조건 제외 — signal_base).

    RS는 같은 날 다른 종목/지수와 비교해야 하는 cross-sectional 조건이라
    종목 단독으로는 계산할 수 없다. prepare.py가 signal_base & rs_ok로
    최종 signal을 만든다.
    """
    # v38: HIGH_BASIS 에 맞춰 같은 축으로 비교한다 (high_250 도 그 축으로 계산됨)
    cond_high = (df["close"] if C.HIGH_BASIS == "close" else df["high"]) > df["high_250"]
    cond_atr = df["gain"] >= df["atr"]                              # ATR 이상 상승
    cond_val = df["value"] >= df["value_ma"] * C.VALUE_MULTIPLE      # 거래대금 급증
    # v35: 이름을 바로잡았다 — 상한가 판정이 아니라 극단 급등일 제외다.
    not_limit = (df["close"] / df["prev_close"] - 1.0) < C.EXTREME_GAIN_PCT
    enough_bars = df["bars"] >= C.MIN_LISTED_DAYS

    # v45: 베이스 조건 — 큰 상승 -> 건전한 조정 -> 재돌파
    if C.BASE_FILTER:
        cond_base = ((df["base_days"] >= C.BASE_MIN_DAYS)
                     & (df["base_depth"] <= C.BASE_MAX_DEPTH)
                     & (df["prior_gain"] >= C.PRIOR_GAIN_PCT)).fillna(False)
    else:
        cond_base = True

    df["signal_base"] = (cond_high & cond_atr & cond_val & not_limit
                         & enough_bars & cond_base).fillna(False)
    return df


def build(code):
    """한 종목의 지표·시그널까지 완성된 DataFrame 반환 (실패 시 None)."""
    df = load_merged(code)
    if df is None:
        return None
    df = add_indicators(df)
    df = add_signal(df)
    return df


def market_regime(close, ma_period=C.REGIME_MA_PERIOD,
                  slope_days=C.REGIME_SLOPE_DAYS):
    """시장 국면 판정 — 약세 1 / 횡보 2 / 강세 3 (그대로 R 단위로 쓰인다).

      강세: 지수가 MA200 위에 있고, MA200 이 상승 중
      약세: 지수가 MA200 아래에 있고, MA200 이 하락 중
      횡보: 그 외 (위치와 기울기가 엇갈리는 구간)

    기울기는 MA200 을 slope_days 전과 비교해 판단한다. 하루 차분은 추세 전환
    부근에서 부호가 자주 뒤집혀 국면이 요동치므로 약 1개월치를 본다.
    워밍업 구간(지표 계산 불가)은 횡보로 둔다.
    """
    ma = close.rolling(ma_period).mean()
    slope = ma - ma.shift(slope_days)
    r = pd.Series(float(C.REGIME_SIDE), index=close.index)
    r[(close > ma) & (slope > 0)] = float(C.REGIME_BULL)
    r[(close < ma) & (slope < 0)] = float(C.REGIME_BEAR)
    r[ma.isna() | slope.isna()] = float(C.REGIME_SIDE)
    return r


def build_index(path):
    """지수(코스피/코스닥) CSV -> RS 벤치마크(rs_raw) + 시장 국면(regime)."""
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df["close"] > 0].sort_values("date").reset_index(drop=True)
    df["rs_raw"] = rs_raw_score(df["close"])
    df["regime"] = market_regime(df["close"])
    return df

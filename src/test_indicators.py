# -*- coding: utf-8 -*-
"""지표·시그널 로직 검증 — 실제 종목 몇 개로 손계산 대조."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import fetch
import indicators as IND

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 30)

CODES = ["005930", "000660", "035720"]

os.makedirs(C.NAVER_DIR, exist_ok=True)
for code in CODES:
    p = os.path.join(C.NAVER_DIR, "%s.csv" % code)
    if not os.path.exists(p):
        df = fetch.fetch_naver(code, C.DATA_START, C.TEST_END.replace("-", ""))
        if df is not None:
            df.to_csv(p, index=False)
            print("[받음] %s naver %d행" % (code, len(df)))

for code in CODES:
    print("\n" + "=" * 100)
    df = IND.build(code)
    if df is None:
        print("%s: 데이터 부족 (다음 데이터 아직 미수집일 수 있음)" % code)
        continue
    print("%s  총 %d행  %s ~ %s  시그널 %d건"
          % (code, len(df), df["date"].iloc[0].date(), df["date"].iloc[-1].date(),
             int(df["signal"].sum())))

    cols = ["date", "high", "close", "prev_close", "gain", "atr", "high_250",
            "value", "value_ma", "sma20", "signal"]
    sig = df[df["signal"]]
    if len(sig):
        print("\n  [시그널 발생일 상위 5건]")
        s = sig[cols].head(5).copy()
        s["value"] = (s["value"] / 1e8).round(0)
        s["value_ma"] = (s["value_ma"] / 1e8).round(0)
        s["배수"] = (sig["value"] / sig["value_ma"]).head(5).round(2)
        s["ATR충족"] = (sig["gain"] >= sig["atr"]).head(5)
        s["신고가"] = (sig["high"] > sig["high_250"]).head(5)
        print(s.to_string(index=False))
        print("  * value/value_ma 단위: 억원")

        # 손계산 검증: 첫 시그널일을 직접 재계산
        r = sig.iloc[0]
        i = df.index[df["date"] == r["date"]][0]
        past250 = df["high"].iloc[max(0, i - C.HIGH_LOOKBACK):i]
        past20v = df["value"].iloc[max(0, i - C.VALUE_MA_PERIOD):i]
        print("\n  [검증] %s" % r["date"].date())
        print("    52주 신고가: 고가 %.0f > 직전250일 최고고가 %.0f  -> %s"
              % (r["high"], past250.max(), r["high"] > past250.max()))
        print("    ATR 상승  : 상승폭 %.0f >= ATR %.1f  -> %s"
              % (r["gain"], r["atr"], r["gain"] >= r["atr"]))
        print("    거래대금  : %.0f억 >= 20일평균 %.0f억 x 2.5 = %.0f억  -> %s"
              % (r["value"] / 1e8, past20v.mean() / 1e8,
                 past20v.mean() * 2.5 / 1e8, r["value"] >= past20v.mean() * 2.5))
    else:
        print("  시그널 없음")

# -*- coding: utf-8 -*-
"""결과 진단 — 어디서 돈이 새는지 찾는다."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import indicators as IND

pd.set_option("display.width", 240)

tr = pd.read_csv(os.path.join(C.OUT, "trades.csv"), dtype={"code": str},
                 parse_dates=["entry_date", "exit_date"])

# 진입일의 봉 정보 수집
recs = []
cache = {}
for _, t in tr.iterrows():
    code = t["code"]
    if code not in cache:
        cache[code] = IND.build(code)
    df = cache[code]
    if df is None:
        continue
    d = df.set_index("date")
    if t["entry_date"] not in d.index:
        continue
    r = d.loc[t["entry_date"]]
    rng = r["high"] - r["low"]
    recs.append({
        "ret": t["ret"],
        "hold": t["hold_days"],
        "reason": t["reason"],
        # 진입 종가가 당일 봉의 어디쯤인가 (1.0 = 고가 마감)
        "close_pos": (r["close"] - r["low"]) / rng if rng > 0 else 0.5,
        # 당일 상승률
        "day_gain": r["close"] / r["prev_close"] - 1,
        # 고가 대비 종가가 얼마나 밀렸나
        "off_high": r["close"] / r["high"] - 1,
        # ATR 대비 상승 배수
        "atr_mult": r["gain"] / r["atr"] if r["atr"] > 0 else np.nan,
        # 거래대금 배수
        "val_mult": r["value"] / r["value_ma"],
        "year": t["entry_date"].year,
    })
x = pd.DataFrame(recs)

print("=" * 84)
print("1. 진입일 캔들 특성")
print("=" * 84)
print("  당일 상승률   : 평균 %.2f%%  중위 %.2f%%" % (x["day_gain"].mean() * 100, x["day_gain"].median() * 100))
print("  종가 위치     : 평균 %.2f (1.0=고가마감, 0.0=저가마감)" % x["close_pos"].mean())
print("  고가 대비 종가: 평균 %.2f%% (진입 시점에 이미 고점에서 밀린 정도)" % (x["off_high"].mean() * 100))
print("  ATR 배수      : 중위 %.2f배" % x["atr_mult"].median())
print("  거래대금 배수 : 중위 %.2f배" % x["val_mult"].median())

print()
print("=" * 84)
print("2. 진입일 종가 위치별 성과 — '고가에 물리는' 문제 확인")
print("=" * 84)
x["pos_bin"] = pd.cut(x["close_pos"], [0, 0.25, 0.5, 0.75, 1.0],
                      labels=["하단25%", "25~50%", "50~75%", "상단25%"])
g = x.groupby("pos_bin", observed=True).agg(
    건수=("ret", "size"), 승률=("ret", lambda s: (s > 0).mean()),
    평균수익률=("ret", "mean"), 평균보유일=("hold", "mean"))
g["승률"] = (g["승률"] * 100).round(1)
g["평균수익률"] = (g["평균수익률"] * 100).round(2)
g["평균보유일"] = g["평균보유일"].round(1)
print(g.to_string())

print()
print("=" * 84)
print("3. 당일 상승률 구간별 성과 — '너무 오른 날 사는' 문제 확인")
print("=" * 84)
x["gain_bin"] = pd.cut(x["day_gain"] * 100, [-100, 3, 6, 10, 15, 100],
                       labels=["~3%", "3~6%", "6~10%", "10~15%", "15%~"])
g = x.groupby("gain_bin", observed=True).agg(
    건수=("ret", "size"), 승률=("ret", lambda s: (s > 0).mean()),
    평균수익률=("ret", "mean"), 평균보유일=("hold", "mean"))
g["승률"] = (g["승률"] * 100).round(1)
g["평균수익률"] = (g["평균수익률"] * 100).round(2)
g["평균보유일"] = g["평균보유일"].round(1)
print(g.to_string())

print()
print("=" * 84)
print("4. 청산 사유별 상세")
print("=" * 84)
g = x.groupby("reason").agg(
    건수=("ret", "size"), 승률=("ret", lambda s: (s > 0).mean()),
    평균수익률=("ret", "mean"), 평균보유일=("hold", "mean"))
g["승률"] = (g["승률"] * 100).round(1)
g["평균수익률"] = (g["평균수익률"] * 100).round(2)
g["평균보유일"] = g["평균보유일"].round(1)
print(g.to_string())

print()
print("=" * 84)
print("5. 수익 기여도 — 상위 거래가 전체를 얼마나 먹여살리는가")
print("=" * 84)
s = tr.sort_values("pnl", ascending=False)
tot = s["pnl"].sum()
for k in (10, 20, 50, 100):
    print("  상위 {:3d}건 손익 합: {:+15,.0f}원  (전체 손익 {:+,.0f}원 대비 {:.0f}%)"
          .format(k, s["pnl"].head(k).sum(), tot, s["pnl"].head(k).sum() / tot * 100))
print("  수익 거래 {}건 합계: {:+,.0f}원".format(
    (tr["pnl"] > 0).sum(), tr[tr["pnl"] > 0]["pnl"].sum()))
print("  손실 거래 {}건 합계: {:+,.0f}원".format(
    (tr["pnl"] <= 0).sum(), tr[tr["pnl"] <= 0]["pnl"].sum()))

print()
print("=" * 84)
print("6. 연도별 진입 건수 vs 시그널 총량 (기회 손실)")
print("=" * 84)
ent = tr.groupby(tr["entry_date"].dt.year).size()
print(ent.to_string())

# -*- coding: utf-8 -*-
"""백테스트 결과 검증 — 개별 거래를 원본 일봉으로 되짚어 확인."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import engine
import indicators as IND

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 40)

tr = pd.read_csv(os.path.join(C.OUT, "trades.csv"), dtype={"code": str},
                 parse_dates=["entry_date", "exit_date"])
eq = pd.read_csv(os.path.join(C.OUT, "equity.csv"), parse_dates=["date"]).set_index("date")

print("=" * 80)
print("1. 기본 통계")
print("=" * 80)
print("  거래 수: %d" % len(tr))
print("  부분익절(+24%% 도달) 발생: %d건 (%.1f%%)"
      % (tr["partial_tp"].sum(), tr["partial_tp"].mean() * 100))
print("  청산사유 분포:\n%s" % tr["reason"].value_counts().to_string())
print("  보유일수: 평균 %.1f일 / 중위 %.0f일 / 최대 %d일"
      % (tr["hold_days"].mean(), tr["hold_days"].median(), tr["hold_days"].max()))
print("  수익률 분포: 최소 %.1f%% / 최대 %.1f%%" % (tr["ret"].min() * 100, tr["ret"].max() * 100))
print("  최종 자산: {:,.0f}원".format(eq["equity"].iloc[-1]))

print()
print("=" * 80)
print("2. 손실 거래 수익률 분포 (트레일링 스탑 정상 작동 확인)")
print("=" * 80)
loss = tr[tr["ret"] <= 0]["ret"] * 100
print(loss.describe().to_string())
print("\n  -10%% ~ -7%% 구간 비중: %.1f%%" % ((loss.between(-10, -7)).mean() * 100))
print("  -8.5%% 미만(더 큰 손실) 비중: %.1f%%" % ((loss < -8.5).mean() * 100))
worst = tr.nsmallest(5, "ret")[["code", "name", "entry_date", "exit_date", "ret", "reason"]]
print("\n  최대 손실 5건:")
print(worst.to_string(index=False))

print()
print("=" * 80)
print("3. 개별 거래 역추적 — 상위 수익 3건 / 최대 손실 2건")
print("=" * 80)
picks = pd.concat([tr.nlargest(3, "ret"), tr.nsmallest(2, "ret")])
for _, t in picks.iterrows():
    df = IND.build(t["code"])
    if df is None:
        continue
    d = df.set_index("date")
    seg = d.loc[t["entry_date"]:t["exit_date"]]
    ep = t["entry_px"]
    peak = seg["high"].max()
    stop_final = peak * (1 - C.TRAIL_PCT)
    print("\n  [%s %s] %s ~ %s  (%d일, %s)"
          % (t["code"], t["name"], t["entry_date"].date(), t["exit_date"].date(),
             len(seg), t["reason"]))
    print("     진입가 %.0f  기간중 최고가 %.0f (+%.1f%%)  최종 스탑선 %.0f"
          % (ep, peak, (peak / ep - 1) * 100, stop_final))
    print("     +24%% 목표가 %.0f  -> 도달 %s / 기록된 부분익절 %s"
          % (ep * 1.24, "O" if peak >= ep * 1.24 else "X",
             "O" if t["partial_tp"] else "X"))
    print("     최종 수익률 %.2f%%  (비용 차감 후)" % (t["ret"] * 100))
    tail = seg.tail(3)[["open", "high", "low", "close", "sma20"]]
    print("     청산 직전 3일:\n%s" % tail.to_string().replace("\n", "\n     "))

print()
print("=" * 80)
print("4. 미래참조 점검 — 진입일이 실제로 3조건을 만족했는가 (무작위 20건)")
print("=" * 80)
rs = np.random.RandomState(0)
sample = tr.sample(min(20, len(tr)), random_state=rs)
bad = 0
for _, t in sample.iterrows():
    df = IND.build(t["code"])
    if df is None:
        continue
    d = df.set_index("date")
    if t["entry_date"] not in d.index:
        print("  [!] %s %s 진입일 데이터 없음" % (t["code"], t["entry_date"].date()))
        bad += 1
        continue
    r = d.loc[t["entry_date"]]
    if not bool(r["signal"]):
        print("  [!] %s %s 시그널 False" % (t["code"], t["entry_date"].date()))
        bad += 1
    if abs(r["close"] - t["entry_px"]) > 0.01:
        print("  [!] %s %s 진입가 불일치 %.0f vs %.0f"
              % (t["code"], t["entry_date"].date(), r["close"], t["entry_px"]))
        bad += 1
print("  검사 %d건 중 이상 %d건" % (len(sample), bad))

print()
print("=" * 80)
print("5. 동시 보유 종목 수 / 현금 소진 점검")
print("=" * 80)
ev = []
for _, t in tr.iterrows():
    ev.append((t["entry_date"], 1))
    ev.append((t["exit_date"], -1))
ev = pd.DataFrame(ev, columns=["date", "d"]).groupby("date")["d"].sum().sort_index()
held = ev.cumsum()
print("  동시 보유 최대: %d  (한도 %d)" % (held.max(), C.MAX_POSITIONS))
print("  보유 종목 수 분포:\n%s"
      % held.reindex(eq.index, method="ffill").fillna(0).value_counts().sort_index().to_string())

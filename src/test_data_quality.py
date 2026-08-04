# -*- coding: utf-8 -*-
"""수집된 다음 데이터 품질 점검."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

files = sorted(os.listdir(C.DAUM_DIR))
print("파일 수: %d" % len(files))

rows, short, nocap, zero = [], 0, 0, 0
for f in files:
    d = pd.read_csv(os.path.join(C.DAUM_DIR, f), parse_dates=["date"])
    if len(d) < 250:
        short += 1
    if d["marcap"].max() < C.MIN_MARKET_CAP:
        nocap += 1
    if (d["close_r"] <= 0).any():
        zero += 1
    rows.append(len(d))

s = pd.Series(rows)
print("행 수: 평균 %.0f / 중위 %.0f / 최소 %d / 최대 %d" % (s.mean(), s.median(), s.min(), s.max()))
print("250행 미만 종목: %d개 (신규 상장 등)" % short)
print("한 번도 시총 1조 넘은 적 없는 종목: %d개" % nocap)
print("0값(거래정지) 포함 종목: %d개" % zero)
print("-> 유니버스 후보 최대: %d개" % (len(files) - nocap))

# 삼성전자 표본
d = pd.read_csv(os.path.join(C.DAUM_DIR, "005930.csv"), parse_dates=["date"])
print("\n[삼성전자 최근 3일]")
x = d.tail(3).copy()
x["marcap(조)"] = (x["marcap"] / 1e12).round(1)
x["value(억)"] = (x["value"] / 1e8).round(0)
print(x[["date", "close_r", "volume", "value(억)", "shares", "marcap(조)"]].to_string(index=False))

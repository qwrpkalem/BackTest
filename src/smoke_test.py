# -*- coding: utf-8 -*-
"""pykrx API 응답 형태와 호출 속도 확인용."""
import time
from pykrx import stock

t = time.time()
cap = stock.get_market_cap_by_ticker("20200630", market="ALL")
print("[cap] rows=%d  %.2fs" % (len(cap), time.time() - t))
print("[cap] cols =", list(cap.columns))
print(cap.head(3))

t = time.time()
ohlcv = stock.get_market_ohlcv_by_date("20200101", "20201231", "005930", adjusted=True)
print("\n[ohlcv] rows=%d  %.2fs" % (len(ohlcv), time.time() - t))
print("[ohlcv] cols =", list(ohlcv.columns))
print(ohlcv.head(3))

t = time.time()
names = {c: stock.get_market_ticker_name(c) for c in ["005930", "005935", "000660"]}
print("\n[name] %s  %.2fs" % (names, time.time() - t))

# -*- coding: utf-8 -*-
"""pykrx 동작 여부 진단."""
import traceback
from pykrx import stock
from pykrx.website import krx


def try_call(label, fn):
    try:
        r = fn()
        print("[OK ] %-28s -> %s" % (label, type(r).__name__), end=" ")
        try:
            print("len=%d cols=%s" % (len(r), list(r.columns)[:8]))
        except Exception:
            print(str(r)[:120])
        return r
    except Exception as e:
        print("[FAIL] %-27s -> %s: %s" % (label, type(e).__name__, str(e)[:100]))
        return None


print("pykrx version:", getattr(__import__("pykrx"), "__version__", "?"))

try_call("ticker_list(20200630)", lambda: stock.get_market_ticker_list("20200630"))
try_call("ohlcv_by_date 삼성전자", lambda: stock.get_market_ohlcv_by_date("20200101", "20200110", "005930"))
try_call("ohlcv_by_ticker(20200630)", lambda: stock.get_market_ohlcv_by_ticker("20200630", market="ALL"))
try_call("market_cap_by_date 삼성", lambda: stock.get_market_cap_by_date("20200101", "20200110", "005930"))

# 원본 응답 확인
print("\n--- raw MKD/ETC 응답 확인 ---")
try:
    raw = krx.market.core.시가총액상위(date="20200630", market="ALL")
    df = raw.fetch("20200630", "ALL") if hasattr(raw, "fetch") else raw
    print("raw type:", type(df))
    print(df.head() if hasattr(df, "head") else str(df)[:500])
except Exception:
    traceback.print_exc()

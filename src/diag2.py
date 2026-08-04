# -*- coding: utf-8 -*-
"""pykrx / FinanceDataReader 조합으로 필요한 데이터 3종 확보 가능한지 확인.

필요 데이터
  (1) 종목 리스트 (KOSPI+KOSDAQ 보통주)
  (2) 일봉 OHLCV + 거래대금 (수정주가)
  (3) 과거 시점 시가총액  <- 유니버스 필터에 필수
"""
import traceback

import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def show(label, fn):
    print("\n" + "=" * 70)
    print("[%s]" % label)
    try:
        r = fn()
        if isinstance(r, pd.DataFrame):
            print("  rows=%d  cols=%s" % (len(r), list(r.columns)))
            if len(r):
                print(r.head(3).to_string())
        else:
            print("  %s len=%s  %s" % (type(r).__name__, len(r), str(r)[:200]))
        return r
    except Exception:
        print("  FAILED:")
        traceback.print_exc(limit=2)
        return None


# ---------------- (1) 종목 리스트 ----------------
import FinanceDataReader as fdr

show("FDR StockListing KRX", lambda: fdr.StockListing("KRX"))
show("FDR StockListing KOSPI", lambda: fdr.StockListing("KOSPI"))

# ---------------- (2) 일봉 ----------------
show("FDR DataReader 005930", lambda: fdr.DataReader("005930", "2020-01-01", "2020-01-15"))

from pykrx import stock

show("pykrx ohlcv 삼성 (수정주가)",
     lambda: stock.get_market_ohlcv_by_date("20200101", "20200115", "005930", adjusted=True))

# ---------------- (3) 과거 시가총액 ----------------
show("pykrx cap_by_date 삼성 2020",
     lambda: stock.get_market_cap_by_date("20200101", "20200115", "005930"))
show("pykrx cap_by_date 삼성 2024",
     lambda: stock.get_market_cap_by_date("20240102", "20240115", "005930"))
show("pykrx cap_by_ticker 2024",
     lambda: stock.get_market_cap_by_ticker("20240102", market="ALL"))
show("pykrx ticker_list 2024", lambda: stock.get_market_ticker_list("20240102", market="ALL"))
show("pykrx ohlcv_by_ticker 2024",
     lambda: stock.get_market_ohlcv_by_ticker("20240102", market="ALL"))

# -*- coding: utf-8 -*-
"""실제 거래대금(accTradePrice)을 주는 소스 탐색."""
import io
import json
import traceback

import pandas as pd
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def sect(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


sect("A. 다음 금융 일별 시세 (accTradePrice = 거래대금)")
try:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": "https://finance.daum.net/quotes/A005930",
    })
    u = "https://finance.daum.net/api/quote/A005930/days"
    r = s.get(u, params={"symbolCode": "A005930", "page": 1, "perPage": 10,
                         "pagination": "true"}, timeout=30)
    print("  HTTP%s" % r.status_code)
    if r.status_code == 200:
        j = r.json()
        d = j.get("data", [])
        print("  rows=%d" % len(d))
        if d:
            print("  cols: %s" % list(d[0].keys()))
            print("  row0: %s" % json.dumps(d[0], ensure_ascii=False)[:400])
    else:
        print("  body: %r" % r.text[:200])
except Exception:
    traceback.print_exc(limit=2)

sect("B. 네이버 일별시세 HTML 페이지")
try:
    u = "https://finance.naver.com/item/sise_day.naver?code=005930&page=1"
    r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
    r.encoding = "euc-kr"
    t = pd.read_html(io.StringIO(r.text))[0].dropna(how="all")
    print("  cols=%s" % list(t.columns))
    print(t.head(3).to_string())
except Exception:
    traceback.print_exc(limit=2)

sect("C. 네이버 통합검색 API (거래대금 필드)")
try:
    u = ("https://m.stock.naver.com/api/stock/005930/price"
         "?pageSize=10&page=1")
    r = requests.get(u, headers={"User-Agent": UA}, timeout=30)
    print("  HTTP%s" % r.status_code)
    if r.status_code == 200:
        j = r.json()
        rows = j if isinstance(j, list) else j.get("priceInfos", j)
        if isinstance(rows, list) and rows:
            print("  rows=%d cols=%s" % (len(rows), list(rows[0].keys())))
            print("  row0: %s" % json.dumps(rows[0], ensure_ascii=False)[:400])
        else:
            print("  %s" % json.dumps(j, ensure_ascii=False)[:300])
    else:
        print("  body: %r" % r.text[:200])
except Exception:
    traceback.print_exc(limit=2)

sect("D. 네이버 siseJson - 미조정(원주가) 파라미터 탐색")
for rt in ("0", "1", "2"):
    try:
        u = ("https://api.finance.naver.com/siseJson.naver?symbol=005930&requestType=%s"
             "&startTime=20180425&endTime=20180510&timeframe=day" % rt)
        txt = requests.get(u, headers={"User-Agent": UA}, timeout=30).text.strip()
        head = txt.replace("\n", " ").replace("\t", "")[:230]
        print("  requestType=%s -> %s" % (rt, head))
    except Exception as e:
        print("  requestType=%s ERR %s" % (rt, str(e)[:60]))
